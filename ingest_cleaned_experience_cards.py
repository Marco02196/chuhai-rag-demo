import hashlib
import json
from collections import Counter
from pathlib import Path


CHUNKS_PATH = Path("output/30tian_chuhai_chunks.jsonl")
DB_PATH = Path("output/30tian_chuhai.sqlite")
MANIFEST_PATH = Path("output/manifest.json")
CARDS_DIR = Path("cleaned_experience_cards")
REPLACE_PREFIXES = ("raw_web_", "cleaned_web_")
NEW_PREFIX = "cleaned_web_"


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


def load_cards() -> list[dict]:
    cards: list[dict] = []
    for path in sorted(CARDS_DIR.glob("*.json")):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"{path} must contain a JSON array")
        for item in loaded:
            item["_source_file"] = path.as_posix()
            cards.append(item)
    return cards


def card_text(card: dict) -> str:
    actions = "\n".join(f"{index}. {action}" for index, action in enumerate(card["actions"], start=1))
    source_lines = "\n".join(f"- {url}" for url in card.get("source_urls", []))
    return "\n".join(
        part
        for part in [
            f"问题：{card['question']}",
            f"适用场景：{card['scenario']}",
            f"判断逻辑：{card['diagnosis']}",
            "建议动作：",
            actions,
            f"风险提醒：{card['risk']}",
            f"关键词：{card.get('keywords', '')}",
            "来源链接：\n" + source_lines if source_lines else "",
        ]
        if part
    )


def card_to_chunk(card: dict, index: int) -> dict:
    text = card_text(card)
    title = card["title"]
    category = card["category"]
    return {
        "id": f"{NEW_PREFIX}{stable_id([title, text])}",
        "text": text,
        "metadata": {
            "kb_name": "30天出海指挥部",
            "source_type": "public_web_cleaned",
            "category": category,
            "category_key": card["category_key"],
            "module": "公开资料清洗卡",
            "title": title,
            "chunk_index": index,
            "content_type": "diagnosis_card",
            "source_path": card["_source_file"],
            "source_urls": card.get("source_urls", []),
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
    existing = [
        item
        for item in load_jsonl(CHUNKS_PATH)
        if not str(item.get("id", "")).startswith(REPLACE_PREFIXES)
    ]
    cards = load_cards()
    chunks = [card_to_chunk(card, index) for index, card in enumerate(cards)]
    combined = existing + chunks
    write_jsonl(CHUNKS_PATH, combined)
    report = update_manifest(combined)
    print(json.dumps({"cleaned_cards": len(chunks), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
