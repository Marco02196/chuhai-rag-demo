import hashlib
import json
from collections import Counter
from pathlib import Path


CHUNKS_PATH = Path("output/30tian_chuhai_chunks.jsonl")
DB_PATH = Path("output/30tian_chuhai.sqlite")
MANIFEST_PATH = Path("output/manifest.json")
CARDS_DIR = Path("raw_experience_cards")
RAW_PREFIX = "raw_web_"


def stable_id(parts: list[str]) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")


def load_raw_cards() -> list[dict]:
    cards: list[dict] = []
    for path in sorted(CARDS_DIR.glob("*.json")):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"{path} must contain a JSON array")
        for item in loaded:
            item["_source_file"] = path.as_posix()
            cards.append(item)
    return cards


def card_to_chunk(card: dict, index: int) -> dict:
    source_urls = card.get("source_urls", [])
    source_lines = "\n".join(f"- {url}" for url in source_urls)
    keywords = card.get("keywords", "")
    text = "\n".join(
        part
        for part in [
            card["text"].strip(),
            f"\n关键词：{keywords}" if keywords else "",
            "\n来源链接：\n" + source_lines if source_lines else "",
        ]
        if part
    )
    title = card["title"]
    category = card["category"]
    return {
        "id": f"{RAW_PREFIX}{stable_id([title, text])}",
        "text": text,
        "metadata": {
            "kb_name": "30天出海指挥部",
            "source_type": "public_web_raw_note",
            "category": category,
            "category_key": card["category_key"],
            "module": "公开投流经验原始笔记",
            "title": title,
            "chunk_index": index,
            "content_type": "raw_experience_note",
            "source_path": card["_source_file"],
            "source_urls": source_urls,
        },
    }


def update_manifest(items: list[dict]) -> dict:
    categories = Counter(item.get("metadata", {}).get("category", "未分类") for item in items)
    content_types = Counter(item.get("metadata", {}).get("content_type", "unknown") for item in items)
    report = {
        "source_root": "notion_30_export/part1",
        "output": str(CHUNKS_PATH.resolve()),
        "chunks": len(items),
        "categories": dict(categories),
        "content_types": dict(content_types),
        "database": str(DB_PATH.resolve()),
    }
    MANIFEST_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    existing = [item for item in load_jsonl(CHUNKS_PATH) if not str(item.get("id", "")).startswith(RAW_PREFIX)]
    raw_cards = load_raw_cards()
    raw_chunks = [card_to_chunk(card, index) for index, card in enumerate(raw_cards)]
    combined = existing + raw_chunks
    write_jsonl(CHUNKS_PATH, combined)
    report = update_manifest(combined)
    print(json.dumps({"raw_cards": len(raw_chunks), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
