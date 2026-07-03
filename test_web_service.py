import unittest
import json

from tempfile import TemporaryDirectory
from pathlib import Path

from web_service import check_auth, check_readiness, handle_ask_payload, handle_feedback_payload, render_index_html


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

    def test_render_index_html_includes_demo_positioning_and_access_code_field(self):
        html = render_index_html()

        self.assertIn("出海投放 AI 军师", html)
        self.assertIn("DeepSeek RAG", html)
        self.assertIn("433 个知识片段", html)
        self.assertIn("gateIn", html)
        self.assertIn("access_code", html)
        self.assertIn("Authorization", html)
        self.assertIn("生成建议", html)
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


if __name__ == "__main__":
    unittest.main()
