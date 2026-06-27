import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


DEFAULT_MAX_CHARS = 900
DEFAULT_MIN_CHARS = 20
PLACEHOLDER_VALUES = {"打开查看内容", "打开查看"}


CATEGORY_RULES = [
    ("万能 Prompt 库", "素材与文案库"),
    ("素材弹药库", "素材与文案库"),
    ("素材测试表", "素材与文案库"),
    ("性能预算", "技术落地库"),
    ("CAPI", "技术落地库"),
    ("Pixel", "技术落地库"),
    ("像素", "技术落地库"),
    ("动态参数", "技术落地库"),
    ("踩坑", "风控与踩坑库"),
    ("风控", "风控与踩坑库"),
    ("自动化规则", "风控与踩坑库"),
    ("投放复盘", "复盘案例库"),
    ("复盘日报", "复盘案例库"),
    ("放量", "投放策略库"),
    ("止损", "投放策略库"),
    ("受众策略", "投放策略库"),
    ("情绪曲线", "投放策略库"),
]

CATEGORY_KEYS = {
    "投放策略库": "ad_strategy",
    "素材与文案库": "creative_copy",
    "技术落地库": "tech_execution",
    "风控与踩坑库": "risk_playbook",
    "复盘案例库": "review_cases",
    "通用知识库": "general",
}


def should_skip_file(path: Path) -> bool:
    name = path.name
    if name.startswith("."):
        return True
    if name.lower().endswith("_all.csv"):
        return True
    return False


def classify_path(path: Path) -> str:
    path_text = str(path)
    for keyword, category in CATEGORY_RULES:
        if keyword in path_text:
            return category
    return "通用知识库"


def stable_id(parts: list[str]) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def strip_notion_id(title: str) -> str:
    title = re.sub(r"\s+[0-9a-f]{16,32}$", "", title, flags=re.IGNORECASE)
    return title.strip(" -_")


def clean_markdown(text: str) -> str:
    lines = []
    in_code = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith("创建时间:") or line.startswith("每日复盘:") or line.startswith("心情:"):
            continue
        if line.strip() in {"打开查看内容", "打开查看"}:
            continue
        line = re.sub(r"^(Prompt 内容:\s*)打开查看内容?$", "Prompt 内容:", line).rstrip()
        if re.fullmatch(r"\s*[-*]\s+\[[ xX]\]\s*.*", line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def split_long_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
        elif len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def heading_level(line: str) -> int | None:
    match = re.match(r"^(#{1,6})\s+(.+)$", line)
    if not match:
        return None
    return len(match.group(1))


def heading_text(line: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", line).strip()


def chunk_markdown(
    text: str,
    source_path: Path,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> list[dict]:
    cleaned = clean_markdown(text)
    if not cleaned:
        return []

    root_title = strip_notion_id(source_path.stem)
    heading_stack: list[tuple[int, str]] = []
    active_title = root_title
    buffer: list[str] = []
    chunks: list[dict] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n".join(buffer).strip()
        buffer = []
        if len(body) < min_chars:
            return
        for piece in split_long_text(body, max_chars=max_chars):
            if len(piece) < min_chars:
                continue
            chunks.append(
                {
                    "title": active_title,
                    "text": piece.strip(),
                    "metadata": {
                        "content_type": "markdown",
                        "source_path": str(source_path).replace("\\", "/"),
                    },
                }
            )

    for line in cleaned.splitlines():
        level = heading_level(line)
        if level is not None:
            flush()
            title = heading_text(line)
            heading_stack = [(lvl, txt) for lvl, txt in heading_stack if lvl < level]
            heading_stack.append((level, title))
            parts = [txt for _, txt in heading_stack]
            active_title = " > ".join(parts) if parts else root_title
            continue
        buffer.append(line)

    flush()
    return chunks


def effective_csv_headers(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    if not rows:
        return [], []
    first = [cell.strip() for cell in rows[0]]
    if len(rows) > 1 and any(cell.startswith("列 ") for cell in first):
        return [cell.strip() or f"列{i + 1}" for i, cell in enumerate(rows[1])], rows[2:]
    return first, rows[1:]


def csv_rows_to_documents(path: Path, root: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))
    headers, data_rows = effective_csv_headers(rows)
    documents = []
    source_path = path.relative_to(root)
    for index, row in enumerate(data_rows):
        pairs = []
        has_placeholder = False
        for header, value in zip(headers, row):
            header = header.strip()
            value = value.strip()
            if value in PLACEHOLDER_VALUES:
                has_placeholder = True
                continue
            if header and value:
                pairs.append(f"{header}：{value}")
        if has_placeholder and len(pairs) <= 2:
            continue
        text = "\n".join(pairs).strip()
        if len(text) < DEFAULT_MIN_CHARS:
            continue
        documents.append(
            {
                "title": strip_notion_id(path.stem),
                "text": text,
                "metadata": {
                    "content_type": "csv_row",
                    "source_path": str(source_path).replace("\\", "/"),
                    "row_index": index,
                },
            }
        )
    return documents


def enrich_document(document: dict, root: Path, index: int) -> dict:
    source_path = document["metadata"]["source_path"]
    path = Path(source_path)
    category = classify_path(path)
    module = path.parts[1] if len(path.parts) > 2 else path.parts[0] if path.parts else ""
    title = document["title"]
    chunk_id = stable_id([source_path, title, str(index), document["text"]])
    metadata = {
        "kb_name": "30天出海指挥部",
        "source_type": "notion_export",
        "category": category,
        "category_key": CATEGORY_KEYS.get(category, "general"),
        "module": strip_notion_id(module),
        "title": title,
        "chunk_index": index,
        **document["metadata"],
    }
    return {
        "id": chunk_id,
        "text": document["text"],
        "metadata": metadata,
    }


def iter_source_documents(root: Path, max_chars: int) -> list[dict]:
    documents = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or should_skip_file(path):
            continue
        suffix = path.suffix.lower()
        if suffix == ".md":
            source_path = path.relative_to(root)
            text = path.read_text(encoding="utf-8")
            documents.extend(chunk_markdown(text, source_path=source_path, max_chars=max_chars))
        elif suffix == ".csv":
            documents.extend(csv_rows_to_documents(path, root=root))
    return documents


def build_chunks(root: Path, output: Path, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    root = root.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    raw_documents = iter_source_documents(root, max_chars=max_chars)
    chunks = [enrich_document(document, root=root, index=index) for index, document in enumerate(raw_documents)]

    with output.open("w", encoding="utf-8", newline="\n") as file:
        for chunk in chunks:
            file.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    categories = Counter(chunk["metadata"]["category"] for chunk in chunks)
    content_types = Counter(chunk["metadata"]["content_type"] for chunk in chunks)
    report = {
        "source_root": str(root),
        "output": str(output.resolve()),
        "chunks": len(chunks),
        "categories": dict(sorted(categories.items())),
        "content_types": dict(sorted(content_types.items())),
    }

    manifest_path = output.with_name("manifest.json")
    manifest_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess Notion Markdown/CSV export into RAG JSONL chunks.")
    parser.add_argument("--input", required=True, type=Path, help="Notion export root directory")
    parser.add_argument("--output", required=True, type=Path, help="Output chunks.jsonl path")
    parser.add_argument("--max-chars", default=DEFAULT_MAX_CHARS, type=int, help="Maximum characters per chunk")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_chunks(args.input, args.output, max_chars=args.max_chars)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
