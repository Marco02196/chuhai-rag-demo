import json
import tempfile
import unittest
from pathlib import Path

from eval_questions import EvalCase, evaluate_case, run_eval
from local_retrieval import build_index


class EvalQuestionsTest(unittest.TestCase):
    def build_test_db(self, tmp_path: Path) -> Path:
        items = [
            {
                "id": "roi_case",
                "text": "ROI 连续低于目标时，先拆 CTR、CVR、加购和支付链路，再决定止损或降预算。",
                "metadata": {
                    "category": "投放策略库",
                    "category_key": "ad_strategy",
                    "title": "ROI 低的投放诊断",
                    "source_path": "demo.md",
                },
            },
            {
                "id": "pixel_case",
                "text": "Pixel 和 CAPI 双回传时要用 event_id 去重，否则 Purchase 会重复计算。",
                "metadata": {
                    "category": "技术落地库",
                    "category_key": "tech_execution",
                    "title": "事件去重",
                    "source_path": "demo.md",
                },
            },
        ]
        jsonl = tmp_path / "chunks.jsonl"
        db = tmp_path / "chunks.sqlite"
        jsonl.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items), encoding="utf-8")
        build_index(jsonl, db)
        return db

    def test_evaluate_case_passes_when_expected_keyword_is_retrieved(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self.build_test_db(Path(tmp))
            case = EvalCase("roi", "ROI 低怎么办", "ad_strategy", ("止损", "关停"))

            result = evaluate_case(db, case)

        self.assertTrue(result["passed"])
        self.assertIn("止损", result["matched_keywords"])

    def test_evaluate_case_fails_without_expected_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self.build_test_db(Path(tmp))
            case = EvalCase("roi", "ROI 低怎么办", "ad_strategy", ("审核",))

            result = evaluate_case(db, case)

        self.assertFalse(result["passed"])

    def test_run_eval_returns_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self.build_test_db(Path(tmp))

            report = run_eval(db, limit=3)

        self.assertIn("total", report)
        self.assertIn("pass_rate", report)
        self.assertGreater(report["total"], 0)


if __name__ == "__main__":
    unittest.main()
