import unittest

from tempfile import TemporaryDirectory
from pathlib import Path

from web_service import check_auth, check_readiness, handle_ask_payload, render_index_html


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
        self.assertIn("accessCode", html)
        self.assertIn("Authorization", html)
        self.assertIn("生成策略建议", html)
        self.assertIn("综合诊断", html)
        self.assertIn("投放决策", html)
        self.assertIn("建议深度", html)
        self.assertIn("data-limit=\"5\"", html)
        self.assertIn("sessionStorage", html)
        self.assertIn("result-shell", html)
        self.assertIn("诊断记录", html)
        self.assertIn("loading-box", html)
        self.assertIn("copyAnswer", html)
        self.assertIn("clearChat", html)
        self.assertIn("data-depth=\"deep\"", html)
        self.assertIn("ROI 小于 1 持续两天怎么办", html)
        self.assertIn("钱一直烧但是不出单咋办", html)
        self.assertIn("半夜空烧怎么设置自动拦截规则", html)
        self.assertIn("Pixel、CAPI、事件回传应该怎么配置才干净", html)

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
        self.assertEqual(response["sources"][0]["title"], "放量与止损看板")
        self.assertNotIn("contexts", response)

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

    def test_check_readiness_reports_missing_database(self):
        with TemporaryDirectory() as temp_dir:
            payload, status = check_readiness(Path(temp_dir) / "missing.sqlite")

        self.assertEqual(status, 503)
        self.assertFalse(payload["ok"])
        self.assertIn("database not found", payload["error"])


if __name__ == "__main__":
    unittest.main()
