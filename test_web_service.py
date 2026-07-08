import unittest
import json

from tempfile import TemporaryDirectory
from pathlib import Path

from web_service import (
    check_auth,
    check_readiness,
    check_supabase_status,
    handle_admin_analytics,
    handle_admin_todo_payload,
    handle_ask_payload,
    handle_feedback_payload,
    render_admin_html,
    render_app_html,
    render_index_html,
)
from supabase_events import supabase_payload_for_event


class FakeEventSink:
    def __init__(self):
        self.events = []
        self.analytics = {"totals": {"questions": 1}, "recent_questions": []}

    def record_event(self, event):
        self.events.append(dict(event))

    def fetch_admin_analytics(self, limit=20):
        payload = dict(self.analytics)
        payload["limit"] = limit
        return payload

    def create_knowledge_todo(self, **payload):
        self.todo = dict(payload)
        return {"id": "todo-1", **payload}


class WebServiceTest(unittest.TestCase):
    def test_check_auth_allows_requests_when_no_api_key_configured(self):
        self.assertTrue(check_auth({}, expected_api_key=""))

    def test_check_auth_accepts_bearer_token(self):
        headers = {"authorization": "Bearer secret"}

        self.assertTrue(check_auth(headers, expected_api_key="secret"))

    def test_check_auth_accepts_x_api_key(self):
        headers = {"x-api-key": "secret"}

        self.assertTrue(check_auth(headers, expected_api_key="secret"))

    def test_check_auth_rejects_wrong_key(self):
        headers = {"authorization": "Bearer wrong"}

        self.assertFalse(check_auth(headers, expected_api_key="secret"))

    def test_render_index_html_includes_northstar_access_gate(self):
        html = render_index_html()

        self.assertIn("Northstar", html)
        self.assertIn("北极星", html)
        self.assertIn("开始导航", html)
        self.assertIn("515", html)
        self.assertIn("gateIn", html)
        self.assertIn("access_code", html)
        self.assertIn("/app?code=", html)
        self.assertIn("window.location.href", html)

    def test_render_app_html_includes_real_rag_chat_app(self):
        html = render_app_html()

        self.assertIn("Northstar", html)
        self.assertIn("北极星", html)
        self.assertIn("投放决策引擎", html)
        self.assertIn("DeepSeek RAG", html)
        self.assertIn("515 个知识片段", html)
        self.assertIn("gateIn", html)
        self.assertIn("access_code", html)
        self.assertIn("Authorization", html)
        self.assertIn("发送", html)
        self.assertIn("综合诊断", html)
        self.assertIn("投放决策", html)
        self.assertIn("回答深度", html)
        self.assertIn("QUERY:'/api/ask'", html)
        self.assertIn("FEEDBACK:'/api/feedback'", html)
        self.assertIn("sessionStorage", html)
        self.assertIn("chatArea", html)
        self.assertIn("id=\"input\"", html)
        self.assertIn("src-toggle", html)
        self.assertIn("fmtAnswer", html)
        self.assertIn("settingsBtn", html)
        self.assertIn("clearBtn", html)
        self.assertIn("CATEGORY_BY_LABEL", html)
        self.assertIn("DEPTH_CONFIG", html)
        self.assertIn("dr-scene", html)
        self.assertIn("data-depth=\"深入\"", html)
        self.assertIn("ROI 低：关停还是降预算", html)
        self.assertIn("烧钱没单怎么办", html)
        self.assertIn("半夜空烧怎么拦截", html)
        self.assertIn("Pixel/CAPI 回传怎么配置", html)

    def test_render_admin_html_includes_analytics_app(self):
        html = render_admin_html()

        self.assertIn("Northstar Analytics", html)
        self.assertIn("/api/admin/analytics", html)
        self.assertIn("/api/admin/todos", html)
        self.assertIn("Authorization", html)
        self.assertIn("recent_questions", html)
        self.assertIn("knowledge_todos", html)

    def test_handle_ask_payload_requires_question(self):
        response, status = handle_ask_payload(
            {},
            db_path="unused.sqlite",
            retriever=lambda **kwargs: [],
            answerer=lambda question, contexts, use_llm: "unused",
        )

        self.assertEqual(status, 400)
        self.assertIn("question", response["error"])

    def test_handle_ask_payload_returns_answer_sources_and_contexts(self):
        contexts = [
            {
                "source_number": 1,
                "id": "a",
                "text": "对应动作：Kill",
                "metadata": {"title": "放量与止损看板", "source_path": "x.csv"},
            }
        ]

        response, status = handle_ask_payload(
            {"question": "ROI 低怎么办", "category_key": "ad_strategy", "limit": 2, "use_llm": True},
            db_path="kb.sqlite",
            retriever=lambda **kwargs: contexts,
            answerer=lambda question, contexts, use_llm: "应该关停。[来源 1]",
        )

        self.assertEqual(status, 200)
        self.assertEqual(response["answer"], "应该关停。[来源 1]")
        self.assertIn("request_id", response)
        self.assertEqual(response["sources"][0]["title"], "放量与止损看板")
        self.assertNotIn("contexts", response)

    def test_handle_ask_payload_writes_question_log_without_secrets(self):
        contexts = [
            {
                "source_number": 1,
                "id": "a",
                "text": "对应动作：Kill",
                "metadata": {"title": "放量与止损看板", "category": "投放策略库", "source_path": "x.csv"},
            }
        ]

        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "events.jsonl"
            response, status = handle_ask_payload(
                {"question": "ROI 低怎么办", "category_key": "ad_strategy", "limit": 2, "use_llm": False},
                db_path="kb.sqlite",
                retriever=lambda **kwargs: contexts,
                answerer=lambda question, contexts, use_llm: "应该关停。[来源 1]",
                log_path=log_path,
            )
            records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(status, 200)
        self.assertEqual(records[0]["event"], "ask")
        self.assertEqual(records[0]["request_id"], response["request_id"])
        self.assertEqual(records[0]["question"], "ROI 低怎么办")
        self.assertEqual(records[0]["source_count"], 1)
        self.assertNotIn("authorization", records[0])
        self.assertNotIn("api_key", records[0])

    def test_handle_ask_payload_sends_event_to_optional_sink(self):
        sink = FakeEventSink()
        contexts = [
            {
                "source_number": 1,
                "id": "a",
                "text": "对应动作：Kill",
                "metadata": {"title": "放量与止损看板", "category": "投放策略库", "source_path": "x.csv"},
            }
        ]

        response, status = handle_ask_payload(
            {"request_id": "req-supa", "question": "ROI 低怎么办", "category_key": "ad_strategy", "limit": 2, "use_llm": False},
            db_path="kb.sqlite",
            retriever=lambda **kwargs: contexts,
            answerer=lambda question, contexts, use_llm: "应该先止损。[来源 1]",
            event_sink=sink,
        )

        self.assertEqual(status, 200)
        self.assertEqual(response["request_id"], "req-supa")
        self.assertEqual(sink.events[0]["event"], "ask")
        self.assertEqual(sink.events[0]["request_id"], "req-supa")
        self.assertIn("created_at", sink.events[0])

    def test_handle_ask_payload_passes_depth_to_answerer(self):
        contexts = [
            {
                "source_number": 1,
                "id": "a",
                "text": "对应动作：Kill",
                "metadata": {"title": "放量与止损看板", "source_path": "x.csv"},
            }
        ]
        seen = {}

        def answerer(question, contexts, use_llm, depth):
            seen["depth"] = depth
            return "快速回答。[来源 1]"

        response, status = handle_ask_payload(
            {"question": "ROI 低怎么办", "depth": "quick", "limit": 2, "use_llm": True},
            db_path="kb.sqlite",
            retriever=lambda **kwargs: contexts,
            answerer=answerer,
        )

        self.assertEqual(status, 200)
        self.assertEqual(seen["depth"], "quick")
        self.assertEqual(response["answer"], "快速回答。[来源 1]")

    def test_handle_ask_payload_can_include_contexts_for_debugging(self):
        contexts = [
            {
                "source_number": 1,
                "id": "a",
                "text": "对应动作：Kill",
                "metadata": {"title": "放量与止损看板", "source_path": "x.csv"},
            }
        ]

        response, status = handle_ask_payload(
            {"question": "ROI 低怎么办", "debug": True},
            db_path="kb.sqlite",
            retriever=lambda **kwargs: contexts,
            answerer=lambda question, contexts, use_llm: "应该关停。[来源 1]",
        )

        self.assertEqual(status, 200)
        self.assertEqual(response["contexts"][0]["id"], "a")

    def test_handle_feedback_payload_writes_feedback_event(self):
        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "events.jsonl"
            response, status = handle_feedback_payload(
                {"request_id": "req-1", "feedback": "up", "answer_preview": "不错"},
                log_path=log_path,
            )
            record = json.loads(log_path.read_text(encoding="utf-8").strip())

        self.assertEqual(status, 200)
        self.assertTrue(response["ok"])
        self.assertEqual(record["event"], "feedback")
        self.assertEqual(record["request_id"], "req-1")
        self.assertEqual(record["feedback"], "up")

    def test_handle_feedback_payload_sends_event_to_optional_sink(self):
        sink = FakeEventSink()
        response, status = handle_feedback_payload(
            {"request_id": "req-1", "feedback": "down", "reason": "太空泛", "answer_preview": "不够具体"},
            log_path=None,
            event_sink=sink,
        )

        self.assertEqual(status, 200)
        self.assertTrue(response["ok"])
        self.assertEqual(sink.events[0]["event"], "feedback")
        self.assertEqual(sink.events[0]["feedback"], "down")
        self.assertEqual(sink.events[0]["reason"], "太空泛")

    def test_handle_feedback_payload_validates_feedback(self):
        response, status = handle_feedback_payload({"request_id": "req-1", "feedback": "maybe"}, log_path=None)

        self.assertEqual(status, 400)
        self.assertIn("feedback", response["error"])

    def test_check_readiness_reports_missing_database(self):
        with TemporaryDirectory() as temp_dir:
            payload, status = check_readiness(Path(temp_dir) / "missing.sqlite")

        self.assertEqual(status, 503)
        self.assertFalse(payload["ok"])
        self.assertIn("database not found", payload["error"])

    def test_check_supabase_status_does_not_expose_secret_values(self):
        status = check_supabase_status(event_sink=FakeEventSink())

        self.assertTrue(status["ok"])
        self.assertTrue(status["enabled"])
        self.assertIn("url_configured", status)
        self.assertIn("service_role_key_configured", status)
        self.assertNotIn("service_role_key", status)
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", status)

    def test_handle_admin_analytics_requires_event_sink(self):
        response, status = handle_admin_analytics(event_sink=None)

        self.assertEqual(status, 503)
        self.assertIn("supabase", response["error"])

    def test_handle_admin_analytics_returns_payload_from_event_sink(self):
        response, status = handle_admin_analytics(event_sink=FakeEventSink(), limit=7)

        self.assertEqual(status, 200)
        self.assertEqual(response["totals"]["questions"], 1)
        self.assertEqual(response["limit"], 7)

    def test_handle_admin_todo_payload_requires_question(self):
        response, status = handle_admin_todo_payload({}, event_sink=FakeEventSink())

        self.assertEqual(status, 400)
        self.assertIn("question", response["error"])

    def test_handle_admin_todo_payload_creates_knowledge_todo(self):
        sink = FakeEventSink()
        response, status = handle_admin_todo_payload(
            {
                "request_id": "req-low",
                "question": "这个问题没有命中",
                "category_key": "ad_strategy",
                "source_count": 0,
                "priority": "high",
            },
            event_sink=sink,
        )

        self.assertEqual(status, 200)
        self.assertTrue(response["ok"])
        self.assertEqual(sink.todo["request_id"], "req-low")
        self.assertEqual(sink.todo["priority"], "high")

    def test_supabase_ask_payload_maps_to_interaction_events_without_secrets(self):
        table, payload = supabase_payload_for_event(
            {
                "event": "ask",
                "request_id": "req-1",
                "question": "ROI 低怎么办",
                "category_key": "ad_strategy",
                "depth": "standard",
                "limit": 3,
                "use_llm": True,
                "elapsed_ms": 1234,
                "answer_length": 88,
                "source_count": 2,
                "source_titles": ["止损卡"],
                "source_categories": ["投放策略库"],
                "authorization": "Bearer secret",
                "api_key": "secret",
                "created_at": "2026-07-08T00:00:00Z",
            }
        )

        self.assertEqual(table, "interaction_events")
        self.assertEqual(payload["retrieval_limit"], 3)
        self.assertEqual(payload["source_titles"], ["止损卡"])
        self.assertNotIn("authorization", payload)
        self.assertNotIn("api_key", payload)

    def test_supabase_feedback_payload_maps_to_feedback_events(self):
        table, payload = supabase_payload_for_event(
            {
                "event": "feedback",
                "request_id": "req-1",
                "feedback": "up",
                "reason": "没答到点",
                "answer_preview": "有帮助",
            }
        )

        self.assertEqual(table, "feedback_events")
        self.assertEqual(payload["feedback"], "up")
        self.assertEqual(payload["reason"], "没答到点")
        self.assertEqual(payload["answer_preview"], "有帮助")


if __name__ == "__main__":
    unittest.main()
