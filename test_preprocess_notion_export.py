import csv
import json
import tempfile
import unittest
from pathlib import Path

from preprocess_notion_export import (
    build_chunks,
    chunk_markdown,
    classify_path,
    csv_rows_to_documents,
    should_skip_file,
)


class PreprocessNotionExportTest(unittest.TestCase):
    def test_chunk_markdown_keeps_heading_context(self):
        text = """# D12 流量指挥官

创建时间: 2026年4月27日

## 1. 流量分发协议

- pid 是像素 ID。
- v 是页面版本。

## 2. 动态优惠协议

根据 goal 参数分发送礼或自用优惠。
"""

        chunks = chunk_markdown(
            text,
            source_path=Path("30天出海指挥部/情绪曲线/D12.md"),
            max_chars=120,
        )

        self.assertEqual(
            [chunk["title"] for chunk in chunks],
            [
                "D12 流量指挥官 > 1. 流量分发协议",
                "D12 流量指挥官 > 2. 动态优惠协议",
            ],
        )
        self.assertIn("pid 是像素 ID", chunks[0]["text"])
        self.assertEqual(chunks[0]["metadata"]["content_type"], "markdown")


    def test_csv_rows_to_documents_uses_headers_as_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = tmp_path / "放量与止损看板.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["标题", "列 1", "列 2", "列 3"])
                writer.writerow(["场景描述", "诊断结果", "对应动作", "优先等级"])
                writer.writerow(["ROI < 1, 持续 2 天", "逻辑失效", "Kill (关停)", "🚨"])

            docs = csv_rows_to_documents(path, root=tmp_path)

        self.assertEqual(len(docs), 1)
        self.assertIn("场景描述：ROI < 1, 持续 2 天", docs[0]["text"])
        self.assertIn("对应动作：Kill (关停)", docs[0]["text"])
        self.assertEqual(docs[0]["metadata"]["content_type"], "csv_row")

    def test_csv_rows_to_documents_skips_placeholder_relation_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = tmp_path / "万能 Prompt 库.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["咒语用途", "Prompt 内容", "分类"])
                writer.writerow(["FB 爆款五步法文案生成", "打开查看内容", "营销文案"])

            docs = csv_rows_to_documents(path, root=tmp_path)

        self.assertEqual(docs, [])


    def test_should_skip_duplicate_all_csv(self):
        self.assertTrue(should_skip_file(Path("素材弹药库_all.csv")))
        self.assertFalse(should_skip_file(Path("素材弹药库.csv")))


    def test_classify_path_assigns_domain_category(self):
        self.assertEqual(classify_path(Path("30天出海指挥部/「万能 Prompt 库」/foo.md")), "素材与文案库")
        self.assertEqual(classify_path(Path("30天出海指挥部/性能预算看板/foo.md")), "技术落地库")
        self.assertEqual(classify_path(Path("30天出海指挥部/「踩坑集锦」/foo.md")), "风控与踩坑库")


    def test_build_chunks_writes_stable_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "export"
            source.mkdir()
            (source / "D12.md").write_text(
                "# D12\n\n## 协议\n\n内容足够形成一个 chunk，并且保留来源路径用于后续引用。",
                encoding="utf-8",
            )

            output = tmp_path / "chunks.jsonl"
            report = build_chunks(source, output)

            lines = output.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(report["chunks"], 1)
        item = json.loads(lines[0])
        self.assertTrue(item["id"])
        self.assertEqual(item["text"], "内容足够形成一个 chunk，并且保留来源路径用于后续引用。")
        self.assertEqual(item["metadata"]["source_path"], "D12.md")


if __name__ == "__main__":
    unittest.main()
