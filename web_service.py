import argparse
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from rag_answer import answer_question, retrieve_context


DEFAULT_DB_PATH = Path(__file__).parent / "output" / "30tian_chuhai.sqlite"


def render_index_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>出海投放 AI 军师</title>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f4f7fb;
      color: #182230;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f7fb; color: #182230; }
    button, textarea, select, input { font: inherit; }
    button { cursor: pointer; }
    .shell { min-height: 100vh; }
    .topbar {
      border-bottom: 1px solid #d9e0ea;
      background: rgba(255,255,255,.92);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    .topbar-inner {
      max-width: 1240px;
      margin: 0 auto;
      padding: 14px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .mark {
      width: 38px;
      height: 38px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: #fff;
      font-weight: 900;
      background: linear-gradient(135deg, #0f766e, #2563eb);
    }
    h1 { font-size: 20px; line-height: 1.2; margin: 0; letter-spacing: 0; }
    .subline { margin-top: 3px; color: #667085; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .status { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .pill {
      border: 1px solid #d0d9e6;
      background: #fff;
      border-radius: 999px;
      padding: 7px 10px;
      font-size: 13px;
      color: #344054;
    }
    main { max-width: 1240px; margin: 0 auto; padding: 22px 20px 42px; }
    .summary {
      display: grid;
      grid-template-columns: 1.4fr repeat(3, minmax(150px, .5fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .intro, .stat, .workspace-panel {
      background: #fff;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      box-shadow: 0 12px 34px rgba(24,34,48,.06);
    }
    .intro { padding: 16px 18px; }
    .intro strong { display: block; font-size: 17px; margin-bottom: 4px; }
    .intro span { color: #667085; line-height: 1.55; font-size: 14px; }
    .stat { padding: 15px; }
    .stat strong { display: block; font-size: 24px; color: #101828; }
    .stat span { color: #667085; font-size: 13px; }
    .workspace {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 360px;
      gap: 16px;
      align-items: start;
    }
    .workspace-panel { padding: 18px; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    h2 { font-size: 18px; margin: 0; letter-spacing: 0; }
    .panel-note { color: #667085; font-size: 13px; }
    textarea {
      width: 100%;
      min-height: 156px;
      resize: vertical;
      padding: 15px;
      border: 1px solid #c9d3e1;
      border-radius: 8px;
      background: #fbfdff;
      color: #182230;
      line-height: 1.6;
      outline: none;
    }
    textarea:focus, select:focus, input:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.12); }
    .controls {
      display: grid;
      gap: 14px;
      margin-top: 14px;
    }
    .field-label {
      display: block;
      color: #667085;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: .04em;
      margin-bottom: 8px;
      text-transform: uppercase;
    }
    .category-cards {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .category-card {
      min-height: 70px;
      padding: 12px;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #fff;
      color: #344054;
      text-align: left;
      box-shadow: 0 1px 2px rgba(16,24,40,.04);
    }
    .category-card strong {
      display: block;
      color: #182230;
      font-size: 14px;
      line-height: 1.25;
    }
    .category-card span {
      display: block;
      margin-top: 5px;
      color: #667085;
      font-size: 12px;
      line-height: 1.35;
    }
    .category-card.active {
      border-color: #0f766e;
      background: #effaf6;
      box-shadow: inset 0 0 0 1px #0f766e, 0 6px 16px rgba(15,118,110,.10);
    }
    .ask-options {
      display: grid;
      grid-template-columns: 1fr minmax(180px, .72fr) 170px;
      gap: 10px;
      align-items: end;
    }
    .depth-toggle {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      min-height: 44px;
      padding: 4px;
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #f7faff;
    }
    .depth-toggle button {
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: #475467;
      font-weight: 800;
    }
    .depth-toggle button.active {
      background: #fff;
      color: #0f766e;
      box-shadow: 0 1px 3px rgba(16,24,40,.10);
    }
    select, input {
      width: 100%;
      min-height: 44px;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid #c9d3e1;
      background: #fff;
      color: #182230;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    .primary {
      min-height: 44px;
      border: 0;
      border-radius: 8px;
      background: #0f766e;
      color: #fff;
      font-weight: 800;
      box-shadow: 0 10px 20px rgba(15,118,110,.18);
    }
    .primary:hover { background: #115e59; }
    .primary:disabled { opacity: .72; cursor: wait; box-shadow: none; }
    .hint { margin-top: 10px; color: #667085; font-size: 13px; }
    .result-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; margin-top: 14px; }
    .answer, .sources {
      border: 1px solid #d9e0ea;
      border-radius: 8px;
      background: #fbfdff;
      padding: 16px;
      min-height: 58px;
      line-height: 1.75;
    }
    .answer { white-space: pre-wrap; color: #182230; }
    .sources { color: #344054; overflow-wrap: anywhere; }
    .source-card {
      border-top: 1px solid #e4eaf2;
      padding-top: 10px;
      margin-top: 10px;
    }
    .source-card:first-of-type { border-top: 0; margin-top: 8px; padding-top: 0; }
    .source-title { font-weight: 800; color: #182230; }
    .source-path { color: #667085; font-size: 12px; margin-top: 4px; }
    .sidebar { display: grid; gap: 12px; }
    .sample-group { border-top: 1px solid #e4eaf2; padding-top: 13px; }
    .sample-group:first-of-type { border-top: 0; padding-top: 0; }
    .sample-group h3 { margin: 0 0 8px; color: #475467; font-size: 13px; font-weight: 800; }
    .samples button {
      display: block;
      width: 100%;
      text-align: left;
      margin: 7px 0;
      padding: 11px 12px;
      border: 1px solid #e4eaf2;
      border-radius: 8px;
      background: #f7faff;
      color: #1d2939;
      font-weight: 720;
    }
    .samples button:hover { border-color: #b7c6db; background: #eef6ff; }
    .tag-row { display: flex; gap: 7px; flex-wrap: wrap; margin-top: 10px; }
    .tag { font-size: 12px; color: #475467; background: #eef2f7; border-radius: 999px; padding: 5px 8px; }
    .error { color: #b42318; font-weight: 700; }
    @media (max-width: 980px) {
      .summary, .workspace { grid-template-columns: 1fr; }
      .category-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .ask-options { grid-template-columns: 1fr 1fr; }
      .primary { grid-column: 1 / -1; }
    }
    @media (max-width: 620px) {
      .topbar-inner, main { padding-left: 14px; padding-right: 14px; }
      .topbar-inner { align-items: flex-start; flex-direction: column; }
      .status { justify-content: flex-start; }
      .category-cards, .ask-options { grid-template-columns: 1fr; }
      .workspace-panel, .intro, .stat { padding: 14px; }
      h1 { font-size: 18px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <div class="mark">AI</div>
          <div>
            <h1>出海投放 AI 军师</h1>
            <div class="subline">30天出海指挥部知识库 · DeepSeek RAG</div>
          </div>
        </div>
        <div class="status">
          <span class="pill">私有试点</span>
          <span class="pill">来源可追溯</span>
          <span class="pill">访问码保护</span>
        </div>
      </div>
    </header>

    <main>
      <section class="summary">
        <div class="intro">
          <strong>投放问题诊断台</strong>
          <span>把 SOP、复盘、素材规则和踩坑经验整理成可检索的策略建议，适合做客户试点和团队内部培训。</span>
        </div>
        <div class="stat"><strong>381</strong><span>知识片段</span></div>
        <div class="stat"><strong>5</strong><span>业务分类</span></div>
        <div class="stat"><strong>DeepSeek</strong><span>回答模型</span></div>
      </section>

      <section class="workspace">
      <div class="workspace-panel">
        <div class="panel-head">
          <h2>策略问答</h2>
          <span class="panel-note">建议输入真实业务问题</span>
        </div>
        <textarea id="question" placeholder="例如：ROI 下滑但 CTR 没变，是落地页问题还是事件回传问题？"></textarea>
        <div class="controls">
          <div>
            <label class="field-label">你要解决哪类问题</label>
            <div class="category-cards" role="listbox" aria-label="问题类型">
              <button type="button" class="category-card active" data-category="">
                <strong>综合诊断</strong><span>不确定原因时先选这个</span>
              </button>
              <button type="button" class="category-card" data-category="ad_strategy">
                <strong>投放决策</strong><span>预算、ROI、人群、放量</span>
              </button>
              <button type="button" class="category-card" data-category="creative_copy">
                <strong>素材文案</strong><span>Hook、脚本、素材疲劳</span>
              </button>
              <button type="button" class="category-card" data-category="tech_execution">
                <strong>数据回传</strong><span>Pixel、CAPI、落地页性能</span>
              </button>
              <button type="button" class="category-card" data-category="risk_playbook">
                <strong>止损风控</strong><span>空烧、封控、自动规则</span>
              </button>
              <button type="button" class="category-card" data-category="review_cases">
                <strong>复盘归因</strong><span>亏损定位和日报复盘</span>
              </button>
            </div>
            <select id="category" class="sr-only" aria-label="问题类型">
              <option value="">全部知识库</option>
              <option value="ad_strategy">投放策略库</option>
              <option value="creative_copy">素材与文案库</option>
              <option value="tech_execution">技术落地库</option>
              <option value="risk_playbook">风控与踩坑库</option>
              <option value="review_cases">复盘案例库</option>
            </select>
          </div>
          <div class="ask-options">
            <div>
              <label class="field-label">建议深度</label>
              <div class="depth-toggle" aria-label="建议深度">
                <button type="button" data-limit="2">快速</button>
                <button type="button" class="active" data-limit="3">标准</button>
                <button type="button" data-limit="5">深入</button>
              </div>
              <input id="limit" class="sr-only" type="number" min="1" max="8" value="3" />
            </div>
            <div>
              <label class="field-label" for="accessCode">演示访问码</label>
              <input id="accessCode" type="password" placeholder="输入访问码" autocomplete="current-password" />
            </div>
            <button id="ask" class="primary">生成策略建议</button>
          </div>
        </div>
        <div class="hint">请输入演示访问码后生成建议。访问码由项目负责人提供。</div>
        <div class="result-grid">
          <div id="answer" class="answer">等待提问。</div>
          <div id="sources" class="sources"></div>
        </div>
      </div>
      <aside class="workspace-panel samples">
        <div class="panel-head">
          <h2>场景入口</h2>
          <span class="panel-note">点击填入问题</span>
        </div>
        <div class="sample-group">
          <h3>投放策略</h3>
          <button data-q="钱一直烧但是不出单咋办？" data-cat="">烧钱没单怎么办？</button>
          <button data-q="ROI 小于 1 持续两天怎么办？应该关停还是降预算？" data-cat="ad_strategy">ROI 低：关停还是降预算？</button>
          <button data-q="CTR 高但是 CVR 很低，应该优先排查素材、落地页还是人群？" data-cat="ad_strategy">CTR 高但 CVR 低怎么排查？</button>
          <button data-q="TOFU、MOFU、BOFU 分别应该怎么做人群排除？" data-cat="ad_strategy">漏斗人群排除怎么做？</button>
        </div>
        <div class="sample-group">
          <h3>素材文案</h3>
          <button data-q="FB 爆款五步法文案怎么写？" data-cat="creative_copy">FB 爆款文案五步法</button>
          <button data-q="Hook 不够强，怎么改成更高 CTR 的开头？" data-cat="creative_copy">Hook 如何改得更抓人？</button>
          <button data-q="素材疲劳应该看哪些信号？" data-cat="creative_copy">素材疲劳看哪些信号？</button>
        </div>
        <div class="sample-group">
          <h3>技术落地</h3>
          <button data-q="Pixel、CAPI、事件回传应该怎么配置才干净？" data-cat="tech_execution">Pixel/CAPI 回传怎么配置？</button>
          <button data-q="动态参数路由里的 pid、goal、segment 分别承担什么作用？" data-cat="tech_execution">动态参数路由怎么拆？</button>
          <button data-q="LCP、CLS、TBT 超预算时先修哪里？" data-cat="tech_execution">页面性能超预算先修哪里？</button>
        </div>
        <div class="sample-group">
          <h3>风控复盘</h3>
          <button data-q="半夜空烧怎么设置自动拦截规则？" data-cat="risk_playbook">半夜空烧怎么拦截？</button>
          <button data-q="自动化规则怎么避免误杀好计划？" data-cat="risk_playbook">自动规则如何防误杀？</button>
          <button data-q="今天亏损应该归因到素材、受众、落地页还是技术链路？" data-cat="review_cases">亏损复盘怎么归因？</button>
        </div>
        <div class="tag-row">
          <span class="tag">ROI</span>
          <span class="tag">素材疲劳</span>
          <span class="tag">Pixel/CAPI</span>
          <span class="tag">风控熔断</span>
        </div>
      </aside>
    </section>
    </main>
  </div>
  <script>
    const answerEl = document.getElementById("answer");
    const sourcesEl = document.getElementById("sources");
    const askBtn = document.getElementById("ask");
    function setCategory(value) {
      document.getElementById("category").value = value || "";
      document.querySelectorAll("[data-category]").forEach(btn => {
        btn.classList.toggle("active", (btn.dataset.category || "") === (value || ""));
      });
    }
    document.querySelectorAll("[data-category]").forEach(btn => {
      btn.addEventListener("click", () => setCategory(btn.dataset.category || ""));
    });
    document.querySelectorAll("[data-limit]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.getElementById("limit").value = btn.dataset.limit;
        document.querySelectorAll("[data-limit]").forEach(item => item.classList.toggle("active", item === btn));
      });
    });
    document.querySelectorAll("[data-q]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.getElementById("question").value = btn.dataset.q;
        setCategory(btn.dataset.cat || "");
      });
    });
    askBtn.addEventListener("click", async () => {
      const question = document.getElementById("question").value.trim();
      if (!question) return;
      askBtn.disabled = true;
      askBtn.textContent = "正在分析...";
      answerEl.textContent = "正在分析知识库...";
      sourcesEl.textContent = "";
      try {
        const accessCode = document.getElementById("accessCode").value.trim();
        const headers = {"Content-Type": "application/json"};
        if (accessCode) headers["Authorization"] = `Bearer ${accessCode}`;
        const res = await fetch("/api/ask", {
          method: "POST",
          headers,
          body: JSON.stringify({
            question,
            category_key: document.getElementById("category").value || null,
            limit: Number(document.getElementById("limit").value || 3),
            use_llm: true
          })
        });
        const data = await res.json();
        if (!res.ok) {
          const message = res.status === 401 ? "访问码不正确，请重新输入。" : (data.error || "请求失败");
          throw new Error(message);
        }
        answerEl.textContent = data.answer;
        if (data.sources.length) {
          sourcesEl.innerHTML = "<strong>引用来源</strong>" + data.sources.map(s => (
            '<div class="source-card"><div class="source-title">[' +
            s.source_number + "] " + s.title +
            '</div><div class="source-path">' + s.source_path + '</div></div>'
          )).join("");
        } else {
          sourcesEl.innerHTML = '<strong>引用来源</strong><div class="source-path">暂无命中来源</div>';
        }
      } catch (err) {
        answerEl.innerHTML = `<span class="error">${err.message}</span>`;
      } finally {
        askBtn.disabled = false;
        askBtn.textContent = "生成策略建议";
      }
    });
  </script>
</body>
</html>
"""


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
) -> tuple[dict, int]:
    question = str(payload.get("question") or "").strip()
    if not question:
        return {"error": "question is required"}, 400
    limit = int(payload.get("limit") or 5)
    limit = max(1, min(limit, 8))
    category_key = payload.get("category_key") or None
    use_llm = bool(payload.get("use_llm", True))

    contexts = retriever(db_path=Path(db_path), question=question, limit=limit, category_key=category_key)
    answer = answerer(question, contexts, use_llm=use_llm)
    response = {
        "answer": answer,
        "sources": [source_payload(context) for context in contexts],
    }
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
        if self.path != "/api/ask":
            self.send_json({"error": "not found"}, status=404)
            return
        if not check_auth(normalized_headers(self), getattr(self.server, "api_key", "")):
            self.send_json({"error": "unauthorized"}, status=401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            response, status = handle_ask_payload(payload, db_path=getattr(self.server, "db_path"))
            self.send_json(response, status=status)
        except Exception as exc:
            print(f"request_error path={self.path} type={type(exc).__name__}", flush=True)
            self.send_json({"error": "internal server error"}, status=500)

    def log_message(self, format: str, *args) -> None:
        print(
            f"access remote={self.client_address[0]} method={self.command} path={self.path} message={format % args}",
            flush=True,
        )


def run_server(host: str, port: int, db_path: Path, api_key: str = "") -> None:
    readiness, status = check_readiness(db_path)
    if status != 200:
        raise RuntimeError(readiness["error"])
    server = ThreadingHTTPServer((host, port), RAGRequestHandler)
    server.db_path = db_path
    server.api_key = api_key
    print(f"Serving 30天出海指挥部 RAG on http://{host}:{port}")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the 30天出海指挥部 RAG web app.")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", default=int(os.environ.get("PORT", "8000")), type=int)
    parser.add_argument("--db", default=os.environ.get("RAG_DB_PATH", str(DEFAULT_DB_PATH)), type=Path)
    parser.add_argument("--api-key", default=os.environ.get("APP_API_KEY", ""))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_server(args.host, args.port, args.db, api_key=args.api_key)


if __name__ == "__main__":
    main()
