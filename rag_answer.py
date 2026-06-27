import argparse
from pathlib import Path

from llm_gateway import chat_completion
from local_retrieval import console_safe_text, search_chunks


def retrieve_context(
    db_path: Path,
    question: str,
    limit: int = 5,
    category_key: str | None = None,
) -> list[dict]:
    results = search_chunks(db_path, question, limit=limit, category_key=category_key)
    contexts = []
    for index, result in enumerate(results, start=1):
        contexts.append(
            {
                "source_number": index,
                "id": result["id"],
                "score": result["score"],
                "text": result["text"],
                "metadata": result["metadata"],
            }
        )
    return contexts


def format_sources(contexts: list[dict]) -> list[str]:
    sources = []
    seen = set()
    for context in contexts:
        metadata = context.get("metadata", {})
        title = metadata.get("title", "未命名资料")
        source_path = metadata.get("source_path", "")
        key = (title, source_path)
        if key in seen:
            continue
        seen.add(key)
        sources.append(f"[{context['source_number']}] {title} - {source_path}")
    return sources


def build_rag_prompt(question: str, contexts: list[dict]) -> str:
    source_blocks = []
    for context in contexts:
        metadata = context.get("metadata", {})
        source_blocks.append(
            "\n".join(
                [
                    f"[来源 {context['source_number']}]",
                    f"标题：{metadata.get('title', '未命名资料')}",
                    f"分类：{metadata.get('category', '')}",
                    f"路径：{metadata.get('source_path', '')}",
                    "内容：",
                    context["text"],
                ]
            )
        )
    joined_sources = "\n\n---\n\n".join(source_blocks) if source_blocks else "无可用资料"
    return f"""你是“30天出海指挥部”的投放策略问答助手。

规则：
1. 你只能根据【资料】回答，不要编造知识库没有的结论。
2. 如果资料不足，请回答“根据当前知识库，我无法确认”。
3. 回答要像投放诊断顾问，不要只回答单点结论。
4. 每个关键结论后面标注来源编号，例如：[来源 1]。
5. 最后列出“引用来源”。

请按这个结构回答：
- 问题类型判断：判断用户问题属于投放策略、素材文案、技术落地、风控踩坑、复盘分析中的哪一类；如果横跨多类，也要说出来。
- 可能原因拆解：列出 2-5 个最可能的原因；只能用资料中能支撑的原因。
- 优先排查动作：给出今天就能执行的动作，按优先级排序。
- 观察指标：说明接下来要看哪些指标或信号。
- 风险提醒：指出可能误判或需要人工复核的地方。
- 引用来源：列出用到的来源。

【用户问题】
{question}

【资料】
{joined_sources}

【回答】
"""


def local_draft_answer(question: str, contexts: list[dict]) -> str:
    if not contexts:
        return "根据当前知识库，我无法确认。\n\n引用来源：无"

    top = contexts[0]
    lines = [line.strip() for line in top["text"].splitlines() if line.strip()]
    evidence = "；".join(lines[:4])
    if len(evidence) > 360:
        evidence = evidence[:360].rstrip() + "..."

    answer = [
        f"根据当前命中的资料，建议先按以下依据处理：{evidence} [来源 {top['source_number']}]",
        "",
        "引用来源：",
        *format_sources(contexts),
    ]
    return "\n".join(answer)


def answer_question(
    question: str,
    contexts: list[dict],
    use_llm: bool = False,
    llm_call=chat_completion,
) -> str:
    if not use_llm:
        return local_draft_answer(question, contexts)
    prompt = build_rag_prompt(question, contexts)
    try:
        return llm_call(prompt)
    except Exception as exc:
        fallback = local_draft_answer(question, contexts)
        return f"LLM 调用失败，已回落到本地草稿：{exc}\n\n{fallback}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask the local 30天出海指挥部 RAG prototype.")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--q", required=True)
    parser.add_argument("--limit", default=5, type=int)
    parser.add_argument("--category-key")
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--llm", action="store_true", help="Call DeepSeek/OpenAI-compatible LLM gateway")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contexts = retrieve_context(args.db, args.q, limit=args.limit, category_key=args.category_key)
    print(console_safe_text(answer_question(args.q, contexts, use_llm=args.llm)))
    if args.show_prompt:
        print(console_safe_text("\n\n--- LLM Prompt ---\n"))
        print(console_safe_text(build_rag_prompt(args.q, contexts)))


if __name__ == "__main__":
    main()
