import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path


ASCII_RE = re.compile(r"[a-zA-Z0-9_]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")

COLLOQUIAL_EXPANSIONS = [
    (
        ("不出单", "没单", "没出单", "没转化", "没人买", "没成交", "单不来"),
        "ROI CVR 转化 成交 落地页 人群 支付 事件回传",
    ),
    (
        ("烧钱", "钱烧", "一直烧", "空烧", "花钱没效果", "亏钱", "止不住"),
        "空烧 止损 ROI 关停 Kill 拦截 自动化规则 ROI 破位",
    ),
    (
        ("跑不动", "没量", "掉量", "起不来", "量掉了", "不花钱", "花不出去"),
        "掉量 放量 预算 学习期 素材疲劳 受众 扩量",
    ),
    (
        ("点的人多", "点击多", "点了不买", "只点不买", "点击还行"),
        "CTR 高 CVR 低 落地页 标题党 转化 购买",
    ),
    (
        ("没人点", "不吸引", "开头不行", "文案不行", "素材不行"),
        "Hook CTR 素材 文案 爆款五步法 视觉风格 CTA",
    ),
    (
        ("封号", "被封", "账户异常", "号挂了", "户挂了", "资产异常", "限流"),
        "风控 账号 BM Pixel 代理 环境 资产 权重 踩坑",
    ),
    (
        ("数据不准", "回传不准", "像素乱", "归因乱", "事件乱", "capi", "pixel"),
        "Pixel CAPI 事件回传 数据清洗 降噪 归因 像素",
    ),
    (
        ("怎么复盘", "问题在哪", "哪里出问题", "怎么判断", "咋判断", "怎么查", "咋查"),
        "复盘 诊断 排查 指标 信号 原因 动作",
    ),
]


def expand_colloquial_query(text: str) -> str:
    additions: list[str] = []
    lowered = text.lower()
    for triggers, expansion in COLLOQUIAL_EXPANSIONS:
        if any(trigger.lower() in lowered for trigger in triggers):
            additions.append(expansion)
    if not additions:
        return text
    return f"{text} {' '.join(additions)}"


def search_tokens(text: str) -> list[str]:
    tokens: set[str] = set()
    lowered = text.lower()
    for match in ASCII_RE.findall(lowered):
        tokens.add(match)
    for phrase in CJK_RE.findall(text):
        if len(phrase) == 1:
            tokens.add(phrase)
            continue
        for size in (2, 3):
            for index in range(0, len(phrase) - size + 1):
                tokens.add(phrase[index : index + size])
    return sorted(tokens)


def search_document_text(text: str, metadata: dict) -> str:
    fields = [
        text,
        metadata.get("title", ""),
        metadata.get("category", ""),
        metadata.get("module", ""),
        metadata.get("source_path", ""),
    ]
    token_text = " ".join(search_tokens(" ".join(fields)))
    return f"{' '.join(fields)}\n{token_text}"


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def reset_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS chunks_fts;

        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            category TEXT,
            category_key TEXT,
            title TEXT,
            source_path TEXT
        );

        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            id UNINDEXED,
            search_text,
            tokenize='unicode61'
        );
        """
    )


def load_jsonl(path: Path) -> list[dict]:
    items = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
        if not item.get("id") or not item.get("text"):
            raise ValueError(f"Chunk at line {line_number} must include id and text")
        items.append(item)
    return items


def build_index(jsonl_path: Path, db_path: Path) -> dict:
    jsonl_path = jsonl_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    items = load_jsonl(jsonl_path)

    with closing(connect(db_path)) as connection:
        with connection:
            reset_schema(connection)
            for item in items:
                metadata = item.get("metadata", {})
                connection.execute(
                    """
                INSERT INTO chunks (id, text, metadata_json, category, category_key, title, source_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["text"],
                    json.dumps(metadata, ensure_ascii=False),
                    metadata.get("category"),
                    metadata.get("category_key"),
                    metadata.get("title"),
                    metadata.get("source_path"),
                ),
                )
                connection.execute(
                    "INSERT INTO chunks_fts (id, search_text) VALUES (?, ?)",
                    (item["id"], search_document_text(item["text"], metadata)),
                )

    categories = Counter(item.get("metadata", {}).get("category", "未分类") for item in items)
    return {
        "source": str(jsonl_path),
        "database": str(db_path.resolve()),
        "chunks": len(items),
        "categories": dict(sorted(categories.items())),
    }


def fts_query(text: str) -> str:
    tokens = search_tokens(expand_colloquial_query(text))
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens[:24])


def row_to_result(row: sqlite3.Row) -> dict:
    metadata = json.loads(row["metadata_json"])
    return {
        "id": row["id"],
        "score": row["score"],
        "text": row["text"],
        "metadata": metadata,
    }


def console_safe_text(text: str, encoding: str | None = None) -> str:
    target_encoding = encoding or getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(target_encoding, errors="replace").decode(target_encoding, errors="replace")


def safe_print(text: str = "") -> None:
    print(console_safe_text(text))


def search_chunks(
    db_path: Path,
    query: str,
    limit: int = 5,
    category: str | None = None,
    category_key: str | None = None,
) -> list[dict]:
    match = fts_query(query)
    if not match:
        return []
    params: list[object] = [match]
    category_clause = ""
    if category:
        category_clause = "AND chunks.category = ?"
        params.append(category)
    if category_key:
        category_clause += " AND chunks.category_key = ?"
        params.append(category_key)
    params.append(limit)

    sql = f"""
        SELECT
            chunks.id,
            chunks.text,
            chunks.metadata_json,
            bm25(chunks_fts) AS score
        FROM chunks_fts
        JOIN chunks ON chunks.id = chunks_fts.id
        WHERE chunks_fts MATCH ?
        {category_clause}
        ORDER BY score ASC
        LIMIT ?
    """
    with closing(connect(db_path)) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [row_to_result(row) for row in rows]


def print_results(results: list[dict]) -> None:
    if not results:
        safe_print("No matching chunks found.")
        return
    for index, result in enumerate(results, start=1):
        metadata = result["metadata"]
        safe_print(f"\n[{index}] {metadata.get('title', '')}")
        safe_print(f"Category: {metadata.get('category', '')}")
        safe_print(f"Source: {metadata.get('source_path', '')}")
        safe_print(f"Score: {result['score']:.4f}")
        preview = result["text"].replace("\n", " ")
        safe_print(preview[:500])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and query a local SQLite FTS index for RAG chunks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build SQLite index from chunks JSONL")
    build.add_argument("--chunks", required=True, type=Path)
    build.add_argument("--db", required=True, type=Path)

    query = subparsers.add_parser("query", help="Search local SQLite index")
    query.add_argument("--db", required=True, type=Path)
    query.add_argument("--q", required=True)
    query.add_argument("--limit", default=5, type=int)
    query.add_argument("--category")
    query.add_argument("--category-key")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "build":
        report = build_index(args.chunks, args.db)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "query":
        print_results(search_chunks(args.db, args.q, limit=args.limit, category=args.category, category_key=args.category_key))


if __name__ == "__main__":
    main()
