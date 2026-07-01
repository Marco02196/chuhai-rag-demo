import argparse
import inspect
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Callable
from uuid import uuid4

from rag_answer import answer_question, retrieve_context


DEFAULT_DB_PATH = Path(__file__).parent / "output" / "30tian_chuhai.sqlite"
DEFAULT_LOG_PATH = Path(__file__).parent / "output" / "interaction_events.jsonl"
EVENT_LOG_LOCK = Lock()


def render_index_html() -> str:
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
<title>出海投放 AI 军师</title>
<style>
  /* ===========================================================
     设计令牌 —— 玻璃拟态 / 淡蓝主调
     =========================================================== */
  :root{
    --blue-50:#EFF6FF;
    --blue-100:#DCEBFF;
    --blue-200:#BFDBFE;
    --blue-300:#93C5FD;
    --blue-400:#60A5FA;
    --blue-500:#3B82F6;
    --blue-600:#2563EB;
    --blue-700:#1D4ED8;
    --ink-900:#0F2540;
    --ink-700:#274463;
    --ink-500:#5C7693;
    --ink-300:#8FA6BD;

    --glass-bg:rgba(255,255,255,0.55);
    --glass-bg-soft:rgba(255,255,255,0.38);
    --glass-bg-strong:rgba(255,255,255,0.72);
    --glass-border:rgba(255,255,255,0.6);
    --glass-border-blue:rgba(147,197,253,0.55);

    --teal:#0EA5A4;
    --teal-bg:rgba(14,165,164,0.12);
    --coral:#E2574C;
    --coral-bg:rgba(226,87,76,0.12);

    --radius-sm:8px;
    --radius-md:14px;
    --radius-lg:22px;
    --mono:'SF Mono','JetBrains Mono',Consolas,monospace;
    --sans:-apple-system, BlinkMacSystemFont, 'PingFang SC', 'Segoe UI', sans-serif;
    --shadow-glass:0 8px 32px rgba(59,130,246,0.12), 0 1.5px 4px rgba(15,37,64,0.04);
    --shadow-glass-lg:0 20px 60px rgba(59,130,246,0.18), 0 4px 12px rgba(15,37,64,0.06);
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  html,body{height:100%;}
  body{
    color:var(--ink-900);
    font-family:var(--sans);
    line-height:1.6;
    min-height:100vh;
    -webkit-font-smoothing:antialiased;
    position:relative;
    overflow-x:hidden;
    background:
      radial-gradient(ellipse 800px 500px at 8% -5%, rgba(147,197,253,0.55), transparent 60%),
      radial-gradient(ellipse 700px 600px at 95% 10%, rgba(191,219,254,0.65), transparent 55%),
      radial-gradient(ellipse 900px 700px at 50% 110%, rgba(219,234,254,0.8), transparent 60%),
      linear-gradient(180deg, #F4F9FF 0%, #EAF2FE 100%);
  }
  /* 装饰性光斑，营造玻璃景深 */
  body::before, body::after{
    content:'';
    position:fixed;
    border-radius:50%;
    filter:blur(60px);
    z-index:0;
    pointer-events:none;
  }
  body::before{
    width:420px;height:420px;
    background:radial-gradient(circle, rgba(96,165,250,0.35), transparent 70%);
    top:-120px; left:-100px;
  }
  body::after{
    width:380px;height:380px;
    background:radial-gradient(circle, rgba(147,197,253,0.4), transparent 70%);
    bottom:-100px; right:-80px;
  }

  /* 通用玻璃面板 */
  .glass{
    background:var(--glass-bg);
    backdrop-filter:blur(20px) saturate(160%);
    -webkit-backdrop-filter:blur(20px) saturate(160%);
    border:1px solid var(--glass-border);
    box-shadow:var(--shadow-glass);
  }

  /* 顶部条 */
  .topbar{
    position:sticky;top:0;z-index:30;
    margin:14px 16px 0;
    padding:12px 20px;
    border-radius:var(--radius-lg);
    display:flex;align-items:center;gap:12px;
  }
  .topbar .mark{
    width:36px;height:36px;border-radius:11px;
    background:linear-gradient(155deg,var(--blue-400),var(--blue-600));
    display:flex;align-items:center;justify-content:center;
    font-family:var(--mono);font-weight:700;font-size:13px;color:#fff;
    flex-shrink:0;
    box-shadow:0 4px 14px rgba(37,99,235,0.35);
  }
  .topbar h1{font-size:15px;font-weight:700;color:var(--ink-900);}
  .topbar .sub{font-size:11px;color:var(--ink-500);font-family:var(--mono);}
  .topbar-stats{margin-left:auto;display:flex;gap:18px;}
  .topbar-stat{text-align:right;}
  .topbar-stat b{display:block;font-size:14px;font-family:var(--mono);color:var(--blue-600);}
  .topbar-stat span{font-size:10px;color:var(--ink-500);}
  @media(max-width:640px){ .topbar-stats{display:none;} }

  .session-pill{
    margin-left:auto;
    display:flex;align-items:center;gap:6px;
    font-size:11px;color:var(--teal);
    background:var(--teal-bg);
    border:1px solid rgba(14,165,164,0.35);
    padding:5px 11px;border-radius:999px;
    font-family:var(--mono);
  }
  .session-pill .dot{width:6px;height:6px;border-radius:50%;background:var(--teal);}

  /* 主布局 */
  .shell{
    position:relative;z-index:1;
    max-width:1100px;margin:14px auto 24px;
    padding:0 16px;
    display:grid;grid-template-columns:300px 1fr;
    gap:16px;
    min-height:calc(100vh - 110px);
  }
  @media(max-width:860px){
    .shell{
      grid-template-columns:minmax(0,1fr);
      width:100%;
      min-width:0;
    }
    .control-panel,.chat-panel{min-width:0;}
  }

  /* 左侧诊断控制台 */
  .control-panel{
    border-radius:var(--radius-lg);
    padding:20px 18px;
    display:flex;flex-direction:column;gap:22px;
    align-self:start;
  }
  .panel-label{
    font-size:11px;font-family:var(--mono);letter-spacing:.06em;
    color:var(--ink-500);text-transform:uppercase;margin-bottom:10px;
  }
  .intent-grid{display:flex;flex-direction:column;gap:7px;}
  .intent-btn{
    text-align:left;
    background:var(--glass-bg-soft);
    border:1px solid var(--glass-border-blue);
    border-radius:var(--radius-md);
    padding:10px 12px;
    color:var(--ink-700);
    font-size:13px;
    cursor:pointer;
    transition:.18s;
  }
  .intent-btn strong{display:block;color:var(--ink-900);font-size:13px;font-weight:700;margin-bottom:2px;}
  .intent-btn span{font-size:11px;color:var(--ink-500);}
  .intent-btn:hover{background:var(--glass-bg);transform:translateY(-1px);}
  .intent-btn.active{
    border-color:var(--blue-400);
    background:linear-gradient(135deg, rgba(96,165,250,0.22), rgba(191,219,254,0.3));
    box-shadow:0 4px 14px rgba(59,130,246,0.18);
  }
  .intent-btn.active strong{color:var(--blue-700);}

  .chip-row{display:flex;flex-wrap:wrap;gap:6px;}
  @media(max-width:640px){
    .chip-row{flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px;scrollbar-width:none;}
    .chip-row::-webkit-scrollbar{display:none;}
    .chip{flex-shrink:0;}
  }
  .chip{
    font-size:12px;padding:6px 13px;border-radius:999px;
    border:1px solid var(--glass-border-blue);color:var(--ink-700);
    background:var(--glass-bg-soft);cursor:pointer;white-space:nowrap;
    transition:.15s;
  }
  .chip:hover{background:var(--glass-bg);}
  .chip.active{
    border-color:var(--teal);color:var(--teal);
    background:var(--teal-bg);
    font-weight:600;
  }

  .depth-row{display:flex;gap:6px;}
  .depth-btn{
    flex:1;padding:8px 0;text-align:center;font-size:12px;
    border:1px solid var(--glass-border-blue);border-radius:var(--radius-sm);
    background:var(--glass-bg-soft);color:var(--ink-700);cursor:pointer;
    transition:.15s;
  }
  .depth-btn:hover{background:var(--glass-bg);}
  .depth-btn.active{
    background:linear-gradient(135deg, var(--blue-400), var(--blue-600));
    border-color:var(--blue-600); color:#fff;font-weight:700;
    box-shadow:0 4px 14px rgba(37,99,235,0.3);
  }

  /* 场景入口 */
  .scenario-group{margin-bottom:4px;}
  .scenario-title{font-size:11px;color:var(--ink-500);margin:10px 0 6px;font-family:var(--mono);}
  .scenario-link{
    display:block;width:100%;text-align:left;
    background:none;border:none;color:var(--ink-700);
    font-size:12.5px;padding:6px 2px;cursor:pointer;
    border-bottom:1px dashed rgba(147,197,253,0.5);
    transition:.15s;
  }
  .scenario-link:hover{color:var(--blue-600);padding-left:6px;}

  /* 右侧对话区 */
  .chat-panel{
    border-radius:var(--radius-lg);
    display:flex;flex-direction:column;min-height:0;
    overflow:hidden;
  }
  .chat-scroll{flex:1;padding:24px 24px 0;overflow-y:auto;max-height:calc(100vh - 280px);}
  .empty-state{
    color:var(--ink-300);font-size:13px;text-align:center;
    padding:60px 20px;font-family:var(--mono);
  }

  .msg{margin-bottom:18px;}
  .msg-q{
    background:linear-gradient(135deg, rgba(96,165,250,0.16), rgba(191,219,254,0.22));
    border:1px solid var(--glass-border-blue);
    border-radius:var(--radius-md);padding:12px 16px;
    font-size:14px;color:var(--ink-900);margin-bottom:10px;
    max-width:88%;
  }
  .msg-a{
    border-left:2px solid var(--blue-400);
    padding:4px 0 4px 16px;
    font-size:14px;color:var(--ink-700);
  }
  .msg-a.loading{color:var(--ink-500);font-family:var(--mono);font-size:12.5px;}
  .skel{display:flex;flex-direction:column;gap:8px;padding:6px 0;}
  .skel-line{
    height:10px;border-radius:4px;
    background:linear-gradient(90deg, rgba(191,219,254,0.5) 0%, rgba(239,246,255,0.9) 50%, rgba(191,219,254,0.5) 100%);
    background-size:200% 100%;
    animation:shimmer 1.4s infinite;
  }
  @keyframes shimmer{0%{background-position:200% 0;}100%{background-position:-200% 0;}}
  .cold-start-note{margin-top:6px;font-size:11px;color:var(--ink-300);font-family:var(--mono);}

  /* 来源引用 */
  .sources{margin-top:10px;}
  .sources-toggle{
    font-size:11.5px;color:var(--teal);background:none;border:none;
    cursor:pointer;display:flex;align-items:center;gap:5px;
    font-family:var(--mono);padding:0;
  }
  .sources-toggle .chevron{transition:.15s;display:inline-block;}
  .sources-toggle.open .chevron{transform:rotate(90deg);}
  .sources-list{display:none;margin-top:8px;flex-direction:column;gap:6px;}
  .sources-list.open{display:flex;}
  .source-card{
    background:var(--glass-bg-strong);
    border:1px solid var(--glass-border-blue);border-radius:var(--radius-sm);
    padding:8px 10px;font-size:12px;
  }
  .source-card .meta{display:flex;justify-content:space-between;margin-bottom:4px;}
  .source-card .cat{color:var(--teal);font-family:var(--mono);font-size:10.5px;}
  .source-card .score{color:var(--ink-300);font-family:var(--mono);font-size:10.5px;}
  .source-card .excerpt{color:var(--ink-700);}

  .feedback-row{display:flex;gap:8px;margin-top:10px;}
  .fb-btn{
    width:26px;height:26px;border-radius:8px;border:1px solid var(--glass-border-blue);
    background:var(--glass-bg-soft);color:var(--ink-300);cursor:pointer;font-size:12px;
    display:flex;align-items:center;justify-content:center;
    transition:.15s;
  }
  .fb-btn:hover{background:var(--glass-bg);}
  .fb-btn.picked-up{border-color:var(--teal);color:var(--teal);background:var(--teal-bg);}
  .fb-btn.picked-down{border-color:var(--coral);color:var(--coral);background:var(--coral-bg);}

  /* 输入区 */
  .composer{
    padding:14px 24px 20px;
    border-top:1px solid var(--glass-border-blue);
    background:var(--glass-bg-soft);
  }
  .composer-row{display:flex;gap:10px;}
  .composer textarea{
    flex:1;resize:none;background:var(--glass-bg-strong);
    border:1px solid var(--glass-border-blue);border-radius:var(--radius-md);
    padding:11px 14px;color:var(--ink-900);font-size:14px;
    font-family:var(--sans);min-height:46px;max-height:120px;
  }
  .composer textarea::placeholder{color:var(--ink-300);}
  .composer textarea:focus{outline:none;border-color:var(--blue-400);box-shadow:0 0 0 3px rgba(96,165,250,0.18);}
  .send-btn{
    background:linear-gradient(135deg, var(--blue-400), var(--blue-600));
    border:none;border-radius:var(--radius-md);
    padding:0 20px;color:#fff;font-weight:700;font-size:13px;
    cursor:pointer;white-space:nowrap;
    box-shadow:0 6px 18px rgba(37,99,235,0.32);
    transition:.15s;
  }
  .send-btn:hover{box-shadow:0 8px 22px rgba(37,99,235,0.4); transform:translateY(-1px);}
  .send-btn:disabled{background:var(--ink-300);box-shadow:none;cursor:not-allowed;transform:none;}
  .composer-meta{display:flex;justify-content:space-between;margin-top:8px;}
  .composer-meta button{background:none;border:none;color:var(--ink-300);font-size:11.5px;cursor:pointer;}
  .composer-meta button:hover{color:var(--blue-600);}

  /* 访问码入口模态框 */
  .gate-overlay{
    position:fixed;inset:0;
    background:linear-gradient(160deg, rgba(191,219,254,0.6), rgba(239,246,255,0.75));
    backdrop-filter:blur(6px);
    display:flex;align-items:center;justify-content:center;z-index:100;
    padding:20px;
  }
  .gate-overlay.hidden{display:none;}
  .gate-card{
    background:var(--glass-bg-strong);
    backdrop-filter:blur(24px) saturate(160%);
    -webkit-backdrop-filter:blur(24px) saturate(160%);
    border:1px solid var(--glass-border);
    box-shadow:var(--shadow-glass-lg);
    border-radius:var(--radius-lg);padding:30px 28px;max-width:380px;width:100%;
  }
  .gate-card .mark{
    width:42px;height:42px;border-radius:13px;margin-bottom:14px;
    background:linear-gradient(155deg,var(--blue-400),var(--blue-600));
    display:flex;align-items:center;justify-content:center;
    font-family:var(--mono);font-weight:700;font-size:14px;color:#fff;
    box-shadow:0 6px 18px rgba(37,99,235,0.35);
  }
  .gate-card h2{font-size:17px;margin-bottom:6px;color:var(--ink-900);}
  .gate-card p{font-size:12.5px;color:var(--ink-500);margin-bottom:18px;}
  .gate-card input{
    width:100%;background:rgba(255,255,255,0.7);border:1px solid var(--glass-border-blue);
    border-radius:var(--radius-sm);padding:11px 14px;color:var(--ink-900);
    font-size:14px;font-family:var(--mono);letter-spacing:.08em;margin-bottom:10px;
  }
  .gate-card input:focus{outline:none;border-color:var(--blue-400);box-shadow:0 0 0 3px rgba(96,165,250,0.2);}
  .gate-error{font-size:12px;color:var(--coral);margin-bottom:10px;min-height:16px;}
  .gate-submit{
    width:100%;
    background:linear-gradient(135deg, var(--blue-400), var(--blue-600));
    border:none;border-radius:var(--radius-sm);
    padding:12px 0;color:#fff;font-weight:700;font-size:13.5px;cursor:pointer;
    box-shadow:0 6px 18px rgba(37,99,235,0.32);
  }
  .gate-submit:disabled{opacity:.5;cursor:not-allowed;}
  .gate-hint{font-size:11px;color:var(--ink-300);margin-top:12px;text-align:center;}
  @media(max-width:640px){
    .topbar{
      position:relative;
      top:auto;
      margin:8px 8px 0;
      padding:10px 12px;
    }
    .session-pill{display:none!important;}
    .shell{padding:0 8px;gap:10px;}
    .control-panel{padding:14px 12px;gap:16px;}
    .chat-scroll{max-height:56vh;padding:16px 14px 0;}
    .composer{padding:12px 14px 14px;}
    .composer-row{flex-direction:column;}
    .send-btn{min-height:42px;}
    .msg-q{max-width:100%;}
  }
</style>
</head>
<body>

  <!-- ============ 访问码入口 ============ -->
  <div class="gate-overlay" id="gateOverlay">
    <div class="gate-card">
      <div class="mark">军师</div>
      <h2>出海投放 AI 军师</h2>
      <p>30 天出海指挥部知识库 · 输入演示访问码以继续。访问码由项目负责人提供。</p>
      <input type="text" id="gateInput" placeholder="演示访问码" autocomplete="off" />
      <div class="gate-error" id="gateError"></div>
      <button class="gate-submit" id="gateSubmit">进入诊断台</button>
      <div class="gate-hint">提示：可使用 ?code=xxxx 的链接直接跳过此步</div>
    </div>
  </div>

  <div class="topbar glass">
    <div class="mark">军师</div>
    <div>
      <h1>出海投放 AI 军师</h1>
      <div class="sub">30天出海指挥部知识库 · 私有问答助手</div>
    </div>
    <div class="topbar-stats">
      <div class="topbar-stat"><b>381</b><span>知识片段</span></div>
      <div class="topbar-stat"><b>5</b><span>业务分类</span></div>
      <div class="topbar-stat"><b>AI</b><span>策略建议</span></div>
    </div>
    <div class="session-pill" id="sessionPill"><span class="dot"></span>已验证</div>
  </div>

  <div class="shell">

    <!-- ============ 左侧诊断控制台 ============ -->
    <div class="control-panel glass">
      <div>
        <div class="panel-label">你要解决哪类问题</div>
        <div class="intent-grid" id="intentGrid">
          <button class="intent-btn active" data-intent="综合诊断"><strong>综合诊断</strong><span>不确定原因时先选这个</span></button>
          <button class="intent-btn" data-intent="投放决策"><strong>投放决策</strong><span>预算、ROI、人群、放量</span></button>
          <button class="intent-btn" data-intent="素材文案"><strong>素材文案</strong><span>Hook、脚本、素材疲劳</span></button>
          <button class="intent-btn" data-intent="数据回传"><strong>数据回传</strong><span>Pixel、CAPI、落地页性能</span></button>
          <button class="intent-btn" data-intent="止损风控"><strong>止损风控</strong><span>空烧、封控、自动规则</span></button>
          <button class="intent-btn" data-intent="复盘归因"><strong>复盘归因</strong><span>亏损定位和日报复盘</span></button>
        </div>
      </div>

      <div>
        <div class="panel-label">知识库范围</div>
        <div class="chip-row" id="kbChips">
          <button class="chip active" data-kb="全部知识库">全部知识库</button>
          <button class="chip" data-kb="投放策略库">投放策略库</button>
          <button class="chip" data-kb="素材与文案库">素材与文案库</button>
          <button class="chip" data-kb="技术落地库">技术落地库</button>
          <button class="chip" data-kb="风控与踩坑库">风控与踩坑库</button>
          <button class="chip" data-kb="复盘案例库">复盘案例库</button>
        </div>
      </div>

      <div>
        <div class="panel-label">建议深度</div>
        <div class="depth-row" id="depthRow">
          <button class="depth-btn" data-depth="快速">快速</button>
          <button class="depth-btn active" data-depth="标准">标准</button>
          <button class="depth-btn" data-depth="深入">深入</button>
        </div>
      </div>

      <div>
        <div class="scenario-group">
          <div class="scenario-title">投放策略</div>
          <button class="scenario-link">烧钱没单怎么办？</button>
          <button class="scenario-link">ROI 低：关停还是降预算？</button>
          <button class="scenario-link">CTR 高但 CVR 低怎么排查？</button>
          <button class="scenario-link">漏斗人群排除怎么做？</button>
        </div>
        <div class="scenario-group">
          <div class="scenario-title">素材文案</div>
          <button class="scenario-link">FB 爆款文案五步法</button>
          <button class="scenario-link">Hook 如何改得更抓人？</button>
          <button class="scenario-link">素材疲劳看哪些信号？</button>
        </div>
        <div class="scenario-group">
          <div class="scenario-title">技术落地</div>
          <button class="scenario-link">Pixel/CAPI 回传怎么配置？</button>
          <button class="scenario-link">动态参数路由怎么拆？</button>
          <button class="scenario-link">页面性能超预算先修哪里？</button>
        </div>
        <div class="scenario-group">
          <div class="scenario-title">风控复盘</div>
          <button class="scenario-link">半夜空烧怎么拦截？</button>
          <button class="scenario-link">自动规则如何防误杀？</button>
          <button class="scenario-link">亏损复盘怎么归因？</button>
        </div>
      </div>
    </div>

    <!-- ============ 右侧对话区 ============ -->
    <div class="chat-panel glass">
      <div class="chat-scroll" id="chatScroll">
        <div class="empty-state" id="emptyState">等待提问 · 建议输入真实业务问题</div>
      </div>

      <div class="composer">
        <div class="composer-row">
          <textarea id="composerInput" placeholder="例如：FB 投放三天没出单，预算该砍还是该等？" rows="1"></textarea>
          <button class="send-btn" id="sendBtn">生成策略建议</button>
        </div>
        <div class="composer-meta">
          <button id="clearBtn">清除对话</button>
          <button id="copyBtn">复制最近回答</button>
        </div>
      </div>
    </div>

  </div>

<script>
/* =====================================================================
   配置区 —— 接入真实后端时只需要改这里
   ===================================================================== */
const CONFIG = {
  QUERY_ENDPOINT: '/api/ask',
  FEEDBACK_ENDPOINT: '/api/feedback',
  COLD_START_THRESHOLD_MS: 3000,
};

const CATEGORY_BY_LABEL = {
  '综合诊断': '',
  '全部知识库': '',
  '投放决策': 'ad_strategy',
  '投放策略库': 'ad_strategy',
  '素材文案': 'creative_copy',
  '素材与文案库': 'creative_copy',
  '数据回传': 'tech_execution',
  '技术落地库': 'tech_execution',
  '止损风控': 'risk_playbook',
  '风控与踩坑库': 'risk_playbook',
  '复盘归因': 'review_cases',
  '复盘案例库': 'review_cases',
};

const DEPTH_CONFIG = {
  '快速': { depth: 'quick', limit: 2 },
  '标准': { depth: 'standard', limit: 3 },
  '深入': { depth: 'deep', limit: 5 },
};

const SCENARIO_QUESTIONS = {
  '烧钱没单怎么办？': '钱一直烧但是不出单咋办？',
  'ROI 低：关停还是降预算？': 'ROI 小于 1 持续两天怎么办？应该关停还是降预算？',
  'CTR 高但 CVR 低怎么排查？': 'CTR 高但是 CVR 很低，应该优先排查素材、落地页还是人群？',
  '漏斗人群排除怎么做？': 'TOFU、MOFU、BOFU 分别应该怎么做人群排除？',
  'FB 爆款文案五步法': 'FB 爆款五步法文案怎么写？',
  'Hook 如何改得更抓人？': 'Hook 不够强，怎么改成更高 CTR 的开头？',
  '素材疲劳看哪些信号？': '素材疲劳应该看哪些信号？',
  'Pixel/CAPI 回传怎么配置？': 'Pixel、CAPI、事件回传应该怎么配置才干净？',
  '动态参数路由怎么拆？': '动态参数路由里的 pid、goal、segment 分别承担什么作用？',
  '页面性能超预算先修哪里？': 'LCP、CLS、TBT 超预算时先修哪里？',
  '半夜空烧怎么拦截？': '半夜空烧怎么设置自动拦截规则？',
  '自动规则如何防误杀？': '自动化规则怎么避免误杀好计划？',
  '亏损复盘怎么归因？': '今天亏损应该归因到素材、受众、落地页还是技术链路？',
};

const SCENARIO_KB_BY_GROUP = {
  '投放策略': '投放策略库',
  '素材文案': '素材与文案库',
  '技术落地': '技术落地库',
  '风控复盘': '风控与踩坑库',
};

const state = {
  intent: '综合诊断',
  kb: '全部知识库',
  depth: '标准',
  token: sessionStorage.getItem('access_code') || null,
  lastAnswerEl: null,
};

const gateOverlay = document.getElementById('gateOverlay');
const gateInput = document.getElementById('gateInput');
const gateError = document.getElementById('gateError');
const gateSubmit = document.getElementById('gateSubmit');
const sessionPill = document.getElementById('sessionPill');

function showGate(message){
  gateOverlay.classList.remove('hidden');
  if(message) gateError.textContent = message;
}
function hideGate(){
  gateOverlay.classList.add('hidden');
  sessionPill.style.display = 'flex';
}

async function verifyCode(code){
  gateSubmit.disabled = true;
  gateError.textContent = '';
  try{
    const cleanCode = code.trim();
    if(cleanCode.length < 4){ throw new Error('访问码格式不正确'); }
    state.token = cleanCode;
    sessionStorage.setItem('access_code', state.token);
    hideGate();
  }catch(err){
    gateError.textContent = err.message || '验证失败，请重试';
  }finally{
    gateSubmit.disabled = false;
  }
}

gateSubmit.addEventListener('click', () => verifyCode(gateInput.value));
gateInput.addEventListener('keydown', e => { if(e.key === 'Enter') verifyCode(gateInput.value); });

(function initGate(){
  const params = new URLSearchParams(window.location.search);
  const urlCode = params.get('code');
  if(state.token){
    hideGate();
  } else if(urlCode){
    gateInput.value = urlCode;
    verifyCode(urlCode);
  } else {
    showGate();
  }
})();

/* ============ 左侧控制面板交互 ============ */
document.getElementById('intentGrid').addEventListener('click', e => {
  const btn = e.target.closest('.intent-btn');
  if(!btn) return;
  document.querySelectorAll('.intent-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.intent = btn.dataset.intent;
});

document.getElementById('kbChips').addEventListener('click', e => {
  const chip = e.target.closest('.chip');
  if(!chip) return;
  document.querySelectorAll('#kbChips .chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');
  state.kb = chip.dataset.kb;
});

document.getElementById('depthRow').addEventListener('click', e => {
  const btn = e.target.closest('.depth-btn');
  if(!btn) return;
  document.querySelectorAll('.depth-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  state.depth = btn.dataset.depth;
});

document.querySelectorAll('.scenario-link').forEach(link => {
  link.addEventListener('click', () => {
    composerInput.value = SCENARIO_QUESTIONS[link.textContent.trim()] || link.textContent.trim();
    const groupTitle = link.closest('.scenario-group')?.querySelector('.scenario-title')?.textContent.trim();
    const targetKb = SCENARIO_KB_BY_GROUP[groupTitle];
    if(targetKb){
      state.kb = targetKb;
      document.querySelectorAll('#kbChips .chip').forEach(chip => {
        chip.classList.toggle('active', chip.dataset.kb === targetKb);
      });
    }
    composerInput.focus();
  });
});

/* ============ 对话区渲染 ============ */
const chatScroll = document.getElementById('chatScroll');
const emptyState = document.getElementById('emptyState');
const composerInput = document.getElementById('composerInput');
const sendBtn = document.getElementById('sendBtn');

function appendQuestion(text){
  emptyState.style.display = 'none';
  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = `<div class="msg-q">${escapeHtml(text)}</div>`;
  chatScroll.appendChild(div);
  chatScroll.scrollTop = chatScroll.scrollHeight;
  return div;
}

function appendLoadingAnswer(){
  const wrap = document.createElement('div');
  wrap.className = 'msg-a loading';
  wrap.innerHTML = `
    <div class="skel">
      <div class="skel-line" style="width:92%"></div>
      <div class="skel-line" style="width:78%"></div>
      <div class="skel-line" style="width:85%"></div>
    </div>
    <div class="cold-start-note" id="coldStartNote" style="display:none">知识库引擎启动中，首次请求可能需要 30 秒…</div>
  `;
  chatScroll.lastElementChild.appendChild(wrap);
  chatScroll.scrollTop = chatScroll.scrollHeight;
  return wrap;
}

function renderAnswer(container, answerText, sources, requestId){
  container.classList.remove('loading');
  container.dataset.requestId = requestId || '';
  const sourcesHtml = sources && sources.length ? `
    <div class="sources">
      <button class="sources-toggle"><span class="chevron">›</span> 查看 ${sources.length} 条引用来源</button>
      <div class="sources-list">
        ${sources.map(s => `
          <div class="source-card">
            <div class="meta"><span class="cat">${escapeHtml(s.category)}</span><span class="score">相关度 ${s.score}</span></div>
            <div class="excerpt">${escapeHtml(s.excerpt)}</div>
          </div>
        `).join('')}
      </div>
    </div>` : '';

  container.innerHTML = `
    <div class="answer-text">${escapeHtml(answerText)}</div>
    ${sourcesHtml}
    <div class="feedback-row">
      <button class="fb-btn" data-fb="up" title="有用">👍</button>
      <button class="fb-btn" data-fb="down" title="没用">👎</button>
    </div>
  `;

  const toggle = container.querySelector('.sources-toggle');
  if(toggle){
    toggle.addEventListener('click', () => {
      toggle.classList.toggle('open');
      toggle.nextElementSibling.classList.toggle('open');
    });
  }
  container.querySelectorAll('.fb-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('.fb-btn').forEach(b => b.classList.remove('picked-up','picked-down'));
      btn.classList.add(btn.dataset.fb === 'up' ? 'picked-up' : 'picked-down');
      recordFeedback(btn.dataset.fb, container.dataset.requestId);
    });
  });

  state.lastAnswerEl = container;
}

function escapeHtml(str){
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function recordFeedback(value, requestId){
  const answerText = state.lastAnswerEl?.querySelector('.answer-text')?.textContent || '';
  const items = JSON.parse(localStorage.getItem('rag_feedback') || '[]');
  items.push({ requestId, value, answerPreview: answerText.slice(0, 240), createdAt: new Date().toISOString() });
  localStorage.setItem('rag_feedback', JSON.stringify(items.slice(-50)));
  if(!requestId || !state.token) return;
  try{
    await fetch(CONFIG.FEEDBACK_ENDPOINT, {
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'Authorization':'Bearer '+state.token
      },
      body: JSON.stringify({
        request_id: requestId,
        feedback: value,
        answer_preview: answerText.slice(0, 240)
      })
    });
  }catch(err){
    // 本地 localStorage 已经留痕，后端失败不打断用户操作。
  }
}

/* ============ 提交问题 ============ */
async function submitQuestion(){
  const text = composerInput.value.trim();
  if(!text || sendBtn.disabled) return;
  if(!state.token){ showGate('请先输入访问码'); return; }

  appendQuestion(text);
  composerInput.value = '';
  sendBtn.disabled = true;

  const loadingEl = appendLoadingAnswer();
  const coldStartTimer = setTimeout(() => {
    const note = loadingEl.querySelector('#coldStartNote');
    if(note) note.style.display = 'block';
  }, CONFIG.COLD_START_THRESHOLD_MS);

  try{
    const depthConfig = DEPTH_CONFIG[state.depth] || DEPTH_CONFIG['标准'];
    const categoryKey = CATEGORY_BY_LABEL[state.kb] || CATEGORY_BY_LABEL[state.intent] || null;
    const res = await fetch(CONFIG.QUERY_ENDPOINT, {
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'Authorization':'Bearer '+state.token
      },
      body: JSON.stringify({
        question:text,
        category_key: categoryKey || null,
        limit: depthConfig.limit,
        depth: depthConfig.depth,
        use_llm: true
      })
    });
    const contentType = res.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await res.json() : { error: await res.text() };
    if(res.status === 401){
      state.token = null;
      sessionStorage.removeItem('access_code');
      showGate('访问码不正确，请重新输入');
      return;
    }
    if(!res.ok){ throw new Error(data.error || '生成失败，请稍后重试'); }
    data.sources = (data.sources || []).map(source => ({
      category: source.category || state.kb || '知识库',
      score: source.source_number ? '来源 ' + source.source_number : '命中',
      excerpt: [source.title, source.source_path].filter(Boolean).join(' · ') || '已命中相关知识片段'
    }));


    clearTimeout(coldStartTimer);
    renderAnswer(loadingEl, data.answer, data.sources, data.request_id);
  }catch(err){
    clearTimeout(coldStartTimer);
    loadingEl.classList.remove('loading');
    loadingEl.innerHTML = `<div style="color:var(--coral)">请求失败，请重试。${escapeHtml(err.message||'')}</div>`;
  }finally{
    sendBtn.disabled = false;
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }
}

sendBtn.addEventListener('click', submitQuestion);
composerInput.addEventListener('keydown', e => {
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); submitQuestion(); }
});
composerInput.addEventListener('input', () => {
  composerInput.style.height = 'auto';
  composerInput.style.height = Math.min(composerInput.scrollHeight, 120) + 'px';
});

document.getElementById('clearBtn').addEventListener('click', () => {
  chatScroll.innerHTML = '';
  chatScroll.appendChild(emptyState);
  emptyState.style.display = 'block';
});

document.getElementById('copyBtn').addEventListener('click', async () => {
  if(!state.lastAnswerEl) return;
  const text = state.lastAnswerEl.querySelector('.answer-text')?.textContent || '';
  await navigator.clipboard.writeText(text);
});
</script>
</body>
</html>

"""


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def truncate_text(text: str, max_length: int = 2000) -> str:
    text = str(text or "").replace("\x00", "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def append_event(log_path: str | Path | None, event: dict) -> None:
    if not log_path:
        return
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event)
    record.setdefault("created_at", utc_timestamp())
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with EVENT_LOG_LOCK:
        with path.open("a", encoding="utf-8") as file:
            file.write(line + "\n")


def ask_event_payload(
    *,
    request_id: str,
    question: str,
    category_key: str | None,
    depth: str,
    limit: int,
    use_llm: bool,
    contexts: list[dict],
    answer: str,
    elapsed_ms: int,
) -> dict:
    return {
        "event": "ask",
        "request_id": request_id,
        "question": truncate_text(question),
        "category_key": category_key,
        "depth": depth,
        "limit": limit,
        "use_llm": use_llm,
        "elapsed_ms": elapsed_ms,
        "answer_length": len(answer or ""),
        "source_count": len(contexts),
        "source_titles": [
            truncate_text(context.get("metadata", {}).get("title", ""), 120)
            for context in contexts[:5]
        ],
        "source_categories": [
            context.get("metadata", {}).get("category", "")
            for context in contexts[:5]
        ],
    }


def handle_feedback_payload(payload: dict, log_path: str | Path | None) -> tuple[dict, int]:
    request_id = str(payload.get("request_id") or "").strip()
    feedback = str(payload.get("feedback") or "").strip().lower()
    if not request_id:
        return {"error": "request_id is required"}, 400
    if feedback not in {"up", "down"}:
        return {"error": "feedback must be up or down"}, 400
    append_event(
        log_path,
        {
            "event": "feedback",
            "request_id": request_id,
            "feedback": feedback,
            "answer_preview": truncate_text(str(payload.get("answer_preview") or ""), 240),
        },
    )
    return {"ok": True}, 200


def normalized_headers(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    return {key.lower(): value for key, value in handler.headers.items()}


def check_auth(headers: dict[str, str], expected_api_key: str | None) -> bool:
    expected_api_key = (expected_api_key or "").strip()
    if not expected_api_key:
        return True
    authorization = headers.get("authorization", "").strip()
    if authorization == f"Bearer {expected_api_key}":
        return True
    return headers.get("x-api-key", "").strip() == expected_api_key


def source_payload(context: dict) -> dict:
    metadata = context.get("metadata", {})
    return {
        "source_number": context.get("source_number"),
        "title": metadata.get("title", ""),
        "category": metadata.get("category", ""),
        "category_key": metadata.get("category_key", ""),
        "source_path": metadata.get("source_path", ""),
    }


def check_readiness(db_path: str | Path) -> tuple[dict, int]:
    db_path = Path(db_path)
    if not db_path.exists():
        return {"ok": False, "error": f"database not found: {db_path}"}, 503
    try:
        with sqlite3.connect(db_path) as conn:
            chunk_count = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
            fts_count = conn.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
    except sqlite3.Error:
        return {"ok": False, "error": "database is not ready"}, 503
    return {"ok": True, "chunks": chunk_count, "chunks_fts": fts_count}, 200


def handle_ask_payload(
    payload: dict,
    db_path: str | Path,
    retriever: Callable[..., list[dict]] = retrieve_context,
    answerer: Callable[..., str] = answer_question,
    log_path: str | Path | None = None,
) -> tuple[dict, int]:
    started_at = time.perf_counter()
    request_id = str(payload.get("request_id") or uuid4())
    question = str(payload.get("question") or "").strip()
    if not question:
        return {"error": "question is required"}, 400
    limit = int(payload.get("limit") or 5)
    limit = max(1, min(limit, 8))
    category_key = payload.get("category_key") or None
    use_llm = bool(payload.get("use_llm", True))
    depth = str(payload.get("depth") or "standard")

    contexts = retriever(db_path=Path(db_path), question=question, limit=limit, category_key=category_key)
    signature = inspect.signature(answerer)
    accepts_depth = "depth" in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()
    )
    if accepts_depth:
        answer = answerer(question, contexts, use_llm=use_llm, depth=depth)
    else:
        answer = answerer(question, contexts, use_llm=use_llm)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    response = {
        "request_id": request_id,
        "answer": answer,
        "sources": [source_payload(context) for context in contexts],
    }
    append_event(
        log_path,
        ask_event_payload(
            request_id=request_id,
            question=question,
            category_key=category_key,
            depth=depth,
            limit=limit,
            use_llm=use_llm,
            contexts=contexts,
            answer=answer,
            elapsed_ms=elapsed_ms,
        ),
    )
    if bool(payload.get("debug", False)):
        response["contexts"] = contexts
    return response, 200


class RAGRequestHandler(BaseHTTPRequestHandler):
    server_version = "RAGPrototype/0.1"

    def send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json({"ok": True})
            return
        if self.path == "/readyz":
            response, status = check_readiness(getattr(self.server, "db_path"))
            self.send_json(response, status=status)
            return
        if self.path in {"/", "/index.html"}:
            body = render_index_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        if self.path not in {"/api/ask", "/api/feedback"}:
            self.send_json({"error": "not found"}, status=404)
            return
        if not check_auth(normalized_headers(self), getattr(self.server, "api_key", "")):
            self.send_json({"error": "unauthorized"}, status=401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            if self.path == "/api/feedback":
                response, status = handle_feedback_payload(payload, log_path=getattr(self.server, "log_path", None))
            else:
                response, status = handle_ask_payload(
                    payload,
                    db_path=getattr(self.server, "db_path"),
                    log_path=getattr(self.server, "log_path", None),
                )
            self.send_json(response, status=status)
        except Exception as exc:
            print(f"request_error path={self.path} type={type(exc).__name__}", flush=True)
            self.send_json({"error": "internal server error"}, status=500)

    def log_message(self, format: str, *args) -> None:
        print(
            f"access remote={self.client_address[0]} method={self.command} path={self.path} message={format % args}",
            flush=True,
        )


def run_server(host: str, port: int, db_path: Path, api_key: str = "", log_path: Path | None = DEFAULT_LOG_PATH) -> None:
    readiness, status = check_readiness(db_path)
    if status != 200:
        raise RuntimeError(readiness["error"])
    server = ThreadingHTTPServer((host, port), RAGRequestHandler)
    server.db_path = db_path
    server.api_key = api_key
    server.log_path = log_path
    print(f"Serving 30天出海指挥部 RAG on http://{host}:{port}")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the 30天出海指挥部 RAG web app.")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int)
    parser.add_argument("--db", default=os.environ.get("RAG_DB_PATH", str(DEFAULT_DB_PATH)), type=Path)
    parser.add_argument("--api-key", default=os.environ.get("APP_API_KEY", ""))
    parser.add_argument("--log-path", default=os.environ.get("RAG_EVENT_LOG_PATH", str(DEFAULT_LOG_PATH)), type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_server(args.host, args.port, args.db, api_key=args.api_key, log_path=args.log_path)


if __name__ == "__main__":
    main()
