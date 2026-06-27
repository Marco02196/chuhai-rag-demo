import sqlite3
import tempfile
import unittest
from pathlib import Path

from local_retrieval import build_index
from test_local_retrieval import LocalRetrievalTest
from rag_answer import answer_question, build_rag_prompt, format_sources, local_draft_answer, retrieve_context


class RagAnswerTest(unittest.TestCase):
    def build_test_db(self, tmp_path: Path) -> Path:
        jsonl = tmp_path / "chunks.jsonl"
        db = tmp_path / "chunks.sqlite"
        LocalRetrievalTest().write_jsonl(jsonl)
        build_index(jsonl, db)
        return db

    def test_retrieve_context_returns_ranked_context_with_source_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self.build_test_db(Path(tmp))
            contexts = retrieve_context(db, "ROI 小于 1 持续两天怎么办", limit=2)

        self.assertEqual(contexts[0]["source_number"], 1)
        self.assertEqual(contexts[0]["id"], "roi_stop_loss")
        self.assertIn("Kill", contexts[0]["text"])

    def test_build_rag_prompt_requires_grounded_answer_and_sources(self):
        contexts = [
            {
                "source_number": 1,
                "text": "场景描述：ROI < 1, 持续 2 天\n对应动作：Kill (关停)",
                "metadata": {
                    "title": "放量与止损看板",
                    "source_path": "放量与止损看板.csv",
                },
            }
        ]

        prompt = build_rag_prompt("ROI 小于 1 持续两天怎么办", contexts)

        self.assertIn("你只能根据【资料】回答", prompt)
        self.assertIn("[来源 1]", prompt)
        self.assertIn("ROI 小于 1 持续两天怎么办", prompt)
        self.assertIn("放量与止损看板.csv", prompt)
        self.assertIn("问题类型判断", prompt)
        self.assertIn("可能原因拆解", prompt)

    def test_format_sources_lists_unique_sources(self):
        contexts = [
            {"source_number": 1, "metadata": {"title": "A", "source_path": "a.md"}},
            {"source_number": 2, "metadata": {"title": "A", "source_path": "a.md"}},
            {"source_number": 3, "metadata": {"title": "B", "source_path": "b.md"}},
        ]

        sources = format_sources(contexts)

        self.assertEqual(sources, ["[1] A - a.md", "[3] B - b.md"])

    def test_local_draft_answer_uses_context_and_cites_sources(self):
        contexts = [
            {
                "source_number": 1,
                "text": "场景描述：ROI < 1, 持续 2 天\n诊断结果：逻辑失效\n对应动作：Kill (关停)",
                "metadata": {"title": "放量与止损看板", "source_path": "x.csv"},
            }
        ]

        answer = local_draft_answer("ROI 小于 1 持续两天怎么办", contexts)

        self.assertIn("Kill", answer)
        self.assertIn("来源：", answer)
        self.assertIn("[1] 放量与止损看板", answer)

    def test_local_draft_answer_refuses_without_context(self):
        answer = local_draft_answer("不存在的问题", [])

        self.assertIn("根据当前知识库，我无法确认", answer)

    def test_answer_question_uses_llm_when_enabled(self):
        contexts = [
            {
                "source_number": 1,
                "text": "对应动作：Kill (关停)",
                "metadata": {"title": "放量与止损看板", "source_path": "x.csv"},
            }
        ]

        def fake_llm(prompt: str) -> str:
            self.assertIn("对应动作：Kill", prompt)
            return "应该关停该计划。[来源 1]"

        answer = answer_question("ROI 小于 1 怎么办", contexts, use_llm=True, llm_call=fake_llm)

        self.assertEqual(answer, "应该关停该计划。[来源 1]")

    def test_answer_question_falls_back_to_local_draft_when_llm_fails(self):
        contexts = [
            {
                "source_number": 1,
                "text": "对应动作：Kill (关停)",
                "metadata": {"title": "放量与止损看板", "source_path": "x.csv"},
            }
        ]

        def failing_llm(prompt: str) -> str:
            raise RuntimeError("missing key")

        answer = answer_question("ROI 小于 1 怎么办", contexts, use_llm=True, llm_call=failing_llm)

        self.assertIn("LLM 调用失败，已回落到本地草稿", answer)
        self.assertIn("Kill", answer)


if __name__ == "__main__":
    unittest.main()
