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
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #0d1117; color: #f8fafc; }
    main { max-width: 1120px; margin: 0 auto; padding: 28px 18px 46px; }
    .hero { display: grid; grid-template-columns: 1.08fr .92fr; gap: 22px; align-items: end; padding: 26px 0 20px; }
    h1 { font-size: clamp(34px, 6vw, 64px); line-height: 1.02; margin: 0 0 14px; letter-spacing: 0; }
    h2 { font-size: 18px; margin: 0 0 12px; }
    p { color: #a8b3c7; line-height: 1.65; }
    .eyebrow { color: #62d58a; font-weight: 700; margin-bottom: 12px; }
    .panel { border: 1px solid #263040; background: #121821; border-radius: 8px; padding: 18px; }
    .metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 18px; }
    .metric { border: 1px solid #263040; border-radius: 8px; padding: 12px; background: #0f141c; }
    .metric strong { display: block; font-size: 22px; color: #ffffff; }
    .metric span { color: #95a3b8; font-size: 13px; }
    .app { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 16px; align-items: start; }
    textarea, select, input, button { font: inherit; }
    textarea { width: 100%; min-height: 150px; resize: vertical; box-sizing: border-box; padding: 14px; border: 1px solid #2b3546; border-radius: 8px; background: #0d121a; color: #fff; }
    .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin: 12px 0; }
    select, input { padding: 10px; border-radius: 8px; border: 1px solid #2b3546; background: #0d121a; color: #fff; }
    button { padding: 11px 18px; border: 0; border-radius: 8px; background: #62d58a; color: #07130c; font-weight: 800; cursor: pointer; }
    button:disabled { opacity: .65; cursor: wait; }
    .answer, .sources { margin-top: 14px; padding: 16px; border: 1px solid #263040; border-radius: 8px; background: #0d121a; white-space: pre-wrap; line-height: 1.72; }
    .sources { white-space: normal; color: #d4d4d8; overflow-wrap: anywhere; }
    .sample-group { margin-top: 14px; }
    .sample-group h3 { margin: 0 0 8px; color: #8ea0ba; font-size: 13px; font-weight: 700; }
    .samples button { display: block; width: 100%; text-align: left; margin: 8px 0; background: #182231; color: #dbeafe; font-weight: 650; }
    .hint { font-size: 13px; color: #8ea0ba; }
    .error { color: #fda4af; }
    @media (max-width: 820px) { .hero, .app { grid-template-columns: 1fr; } .metrics { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <div class="eyebrow">Private demo · DeepSeek RAG</div>
        <h1>出海投放 AI 军师</h1>
        <p>把团队的投放 SOP、复盘、素材规则和踩坑经验变成可问答的 AI 助手。它先检索知识库，再给出带来源的行动建议，适合用来做新人培训、投放诊断和复盘辅助。</p>
      </div>
      <div class="panel">
        <h2>当前 Demo 知识库</h2>
        <div class="metrics">
          <div class="metric"><strong>381</strong><span>知识片段</span></div>
          <div class="metric"><strong>5</strong><span>业务分类</span></div>
          <div class="metric"><strong>DeepSeek</strong><span>回答模型</span></div>
        </div>
      </div>
    </section>

    <section class="app">
      <div class="panel">
        <h2>问一个真实投放问题</h2>
        <textarea id="question" placeholder="例如：ROI 下滑但 CTR 没变，是落地页问题还是事件回传问题？"></textarea>
        <div class="row">
          <select id="category">
            <option value="">全部知识库</option>
            <option value="ad_strategy">投放策略库</option>
            <option value="creative_copy">素材与文案库</option>
            <option value="tech_execution">技术落地库</option>
            <option value="risk_playbook">风控与踩坑库</option>
            <option value="review_cases">复盘案例库</option>
          </select>
          <input id="limit" type="number" min="1" max="8" value="3" title="检索资料数" />
          <input id="accessCode" type="password" placeholder="访问码，可选" autocomplete="current-password" />
          <button id="ask">生成策略建议</button>
        </div>
        <div class="hint">部署到公网时，请设置 APP_API_KEY，并把访问码发给试点客户。</div>
        <div id="answer" class="answer">等待提问。</div>
        <div id="sources" class="sources"></div>
      </div>
      <aside class="panel samples">
        <h2>问题诊断入口</h2>
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
      </aside>
    </section>
  </main>
  <script>
    const answerEl = document.getElementById("answer");
    const sourcesEl = document.getElementById("sources");
    const askBtn = document.getElementById("ask");
    document.querySelectorAll("[data-q]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.getElementById("question").value = btn.dataset.q;
        document.getElementById("category").value = btn.dataset.cat || "";
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
        sourcesEl.innerHTML = "<strong>引用来源</strong><br>" + data.sources.map(s => `[${s.source_number}] ${s.title}<br><small>${s.source_path}</small>`).join("<br><br>");
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
