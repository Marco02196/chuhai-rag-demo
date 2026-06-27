import json
import tempfile
import unittest
from pathlib import Path

from local_retrieval import build_index, console_safe_text, expand_colloquial_query, search_chunks, search_tokens


class LocalRetrievalTest(unittest.TestCase):
    def write_jsonl(self, path: Path) -> None:
        items = [
            {
                "id": "roi_stop_loss",
                "text": "场景描述：ROI < 1, 持续 2 天\n诊断结果：逻辑失效\n对应动作：Kill (关停)",
                "metadata": {
                    "category": "投放策略库",
                    "title": "放量与止损看板",
                    "source_path": "放量与止损看板.csv",
                },
            },
            {
                "id": "dynamic_route",
                "text": "动态参数化路由使用 pid、goal、segment 参数分发 Pixel、优惠和页面组件。",
                "metadata": {
                    "category": "技术落地库",
                    "category_key": "tech_execution",
                    "title": "D12 流量指挥官",
                    "source_path": "D12.md",
                },
            },
            {
                "id": "hook_template",
                "text": "FB 爆款五步法包括 Hook、Body、Trust、CTA 和视觉风格。",
                "metadata": {
                    "category": "素材与文案库",
                    "title": "FB 爆款五步法文案生成",
                    "source_path": "prompt.md",
                },
            },
        ]
        path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in items),
            encoding="utf-8",
        )

    def test_search_tokens_include_chinese_bigrams_and_ascii_terms(self):
        tokens = search_tokens("ROI 小于 1 怎么办")

        self.assertIn("roi", tokens)
        self.assertIn("小于", tokens)
        self.assertIn("怎么", tokens)

    def test_expand_colloquial_query_adds_business_terms_for_casual_questions(self):
        expanded = expand_colloquial_query("钱一直烧但是不出单咋办")

        self.assertIn("ROI", expanded)
        self.assertIn("CVR", expanded)
        self.assertIn("空烧", expanded)
        self.assertIn("止损", expanded)

    def test_console_safe_text_replaces_unprintable_characters(self):
        safe = console_safe_text("触发警报 🚨", encoding="gbk")

        self.assertEqual(safe, "触发警报 ?")

    def test_build_index_and_search_returns_relevant_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl = tmp_path / "chunks.jsonl"
            db = tmp_path / "chunks.sqlite"
            self.write_jsonl(jsonl)

            report = build_index(jsonl, db)
            results = search_chunks(db, "ROI 小于 1 持续两天怎么办", limit=2)

        self.assertEqual(report["chunks"], 3)
        self.assertEqual(results[0]["id"], "roi_stop_loss")
        self.assertIn("Kill", results[0]["text"])

    def test_search_understands_colloquial_no_orders_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl = tmp_path / "chunks.jsonl"
            db = tmp_path / "chunks.sqlite"
            self.write_jsonl(jsonl)
            build_index(jsonl, db)

            results = search_chunks(db, "钱一直烧但是不出单咋办", limit=2)

        self.assertEqual(results[0]["id"], "roi_stop_loss")

    def test_search_supports_category_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl = tmp_path / "chunks.jsonl"
            db = tmp_path / "chunks.sqlite"
            self.write_jsonl(jsonl)
            build_index(jsonl, db)

            results = search_chunks(db, "动态参数路由 Pixel", category="技术落地库")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "dynamic_route")

    def test_search_supports_category_key_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl = tmp_path / "chunks.jsonl"
            db = tmp_path / "chunks.sqlite"
            self.write_jsonl(jsonl)
            build_index(jsonl, db)

            results = search_chunks(db, "动态参数路由 Pixel", category_key="tech_execution")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "dynamic_route")


if __name__ == "__main__":
    unittest.main()
