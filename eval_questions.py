import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from local_retrieval import search_chunks


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    question: str
    category_key: str | None
    expected_any: tuple[str, ...]


EVAL_CASES = [
    EvalCase("ad_roi_stop_or_reduce", "ROI 连续低于 1，是直接关停还是先降预算？", "ad_strategy", ("ROI", "ROAS", "止损", "加购")),
    EvalCase("ad_burning_no_orders", "钱一直烧但是不出单，我该先查哪里？", None, ("烧钱", "不出单", "CTR", "CVR", "支付", "回传")),
    EvalCase("ad_high_ctr_low_cvr", "点击率挺高但没人买，是落地页问题吗？", "ad_strategy", ("CTR", "CVR", "落地页", "转化")),
    EvalCase("ad_low_ctr", "广告没人点，是素材不行还是人群不准？", "creative_copy", ("CTR", "Hook", "素材", "受众")),
    EvalCase("ad_learning_phase", "新广告跑两天数据忽上忽下，要不要重建？", "ad_strategy", ("学习期", "预算", "波动")),
    EvalCase("ad_budget_scale", "昨天赚钱了，今天能不能直接翻倍预算？", "ad_strategy", ("放量", "预算", "CPA", "ROAS")),
    EvalCase("ad_low_cpm_no_orders", "CPM 很低但是没有订单，还值得继续跑吗？", "ad_strategy", ("CPM", "不出单", "流量质量", "CVR")),
    EvalCase("ad_frequency_fatigue", "频次上来之后转化掉了怎么办？", "ad_strategy", ("频次", "素材疲劳", "受众", "CTR")),
    EvalCase("ad_retargeting_roi_down", "再营销一直追老用户，ROI 反而越来越差怎么办？", "ad_strategy", ("再营销", "已购买", "频次", "增量")),
    EvalCase("ad_audience_overlap", "多个广告组是不是在抢同一批人？", "ad_strategy", ("受众重叠", "广告组", "排除")),
    EvalCase("creative_tiktok_hook", "TikTok 视频前三秒留不住人，怎么改？", "creative_copy", ("TikTok", "Hook", "前三秒")),
    EvalCase("creative_fatigue", "素材跑几天后掉量掉转化，是不是疲劳了？", "creative_copy", ("素材疲劳", "频次", "CTR", "CPA")),
    EvalCase("creative_copy_flat", "广告文案很平，怎么写得更能卖？", "creative_copy", ("文案", "卖点", "结果", "CTA")),
    EvalCase("creative_ugc_conversion", "UGC 很真实但转化差，怎么优化？", "creative_copy", ("UGC", "真实", "转化", "CTA")),
    EvalCase("creative_next_ideas", "不知道下一批素材拍什么，怎么找选题？", "creative_copy", ("评论区", "选题", "购买阻力")),
    EvalCase("creative_duplicate_winner", "有条素材爆了，怎么复制下一条爆款？", "creative_copy", ("爆款", "Hook", "变量", "CTA")),
    EvalCase("creative_calendar", "素材更新很勤但没有方法论，怎么排测试？", "creative_copy", ("素材日历", "测试假设", "复盘")),
    EvalCase("tech_pixel_bad_data", "CPA 和 ROAS 看着不准，先检查什么？", "tech_execution", ("Pixel", "事件", "Purchase", "回传")),
    EvalCase("tech_capi_dedupe", "Pixel 和 CAPI 都开了，为什么转化数翻倍？", "tech_execution", ("event_id", "去重", "Pixel", "CAPI")),
    EvalCase("tech_capi_match", "CAPI 有回传但匹配质量低，怎么办？", "tech_execution", ("CAPI", "匹配质量", "用户参数")),
    EvalCase("tech_purchase_value", "订单数对得上，但 ROAS 金额不对怎么办？", "tech_execution", ("Purchase", "value", "currency", "ROAS")),
    EvalCase("tech_tiktok_events_api", "TikTok 数据回传不稳定，什么时候接 Events API？", "tech_execution", ("TikTok", "Events API", "服务端")),
    EvalCase("tech_checkout_drop", "加购很多但付款少，是广告问题还是网站问题？", "tech_execution", ("加购", "购买", "支付", "Checkout")),
    EvalCase("tech_success_page_missing", "用户付款成功了，广告后台却少记购买，为什么？", "tech_execution", ("支付成功页", "Purchase", "后端")),
    EvalCase("tech_utm_naming", "广告后台和 GA 数据对不上，复盘怎么做清楚？", "tech_execution", ("UTM", "命名", "GA", "复盘")),
    EvalCase("landing_mobile_first_screen", "手机端落地页转化差，首屏先改什么？", "tech_execution", ("移动端", "首屏", "CTA")),
    EvalCase("landing_slow_lcp", "落地页打开慢，先修哪里？", "tech_execution", ("LCP", "首屏", "图片", "CDN")),
    EvalCase("landing_cls_jump", "页面跳动会不会影响支付和表单转化？", "tech_execution", ("CLS", "视觉稳定", "支付", "表单")),
    EvalCase("landing_inp_slow", "用户点按钮没反应，技术上怎么排查？", "tech_execution", ("INP", "交互", "JS", "支付")),
    EvalCase("landing_plugins", "页面装了很多追踪和客服插件，会不会拖慢转化？", "tech_execution", ("第三方脚本", "LCP", "INP", "插件")),
    EvalCase("risk_rejected", "广告被拒，是素材违规还是落地页问题？", "risk_playbook", ("审核", "被拒", "落地页", "素材")),
    EvalCase("risk_before_submit", "广告上线前怎么减少被拒概率？", "risk_playbook", ("审核", "自检", "素材", "落地页")),
    EvalCase("risk_appeal_or_rebuild", "广告被拒后应该申诉还是重做？", "risk_playbook", ("拒审", "申诉", "修改")),
    EvalCase("risk_consistency", "没写违规词为什么还是过不了审？", "risk_playbook", ("审核", "一致性", "商品承诺")),
    EvalCase("risk_sensitive_category", "保健美容金融这类敏感品怎么投更稳？", "risk_playbook", ("敏感品类", "审核", "资质")),
    EvalCase("review_daily_first", "每天复盘第一步应该看什么？", "review_cases", ("日复盘", "数据可信", "事件健康")),
    EvalCase("review_performance_table", "怎么判断亏损是不是落地页性能导致的？", "review_cases", ("复盘", "页面性能", "CVR", "LCP")),
    EvalCase("review_change_timeline", "昨天改了页面后广告数据突然变差，怎么定位？", "review_cases", ("时间线", "变更日志", "页面发布")),
    EvalCase("review_boss_question", "老板问钱怎么一直烧没单，我怎么拆成指标？", "review_cases", ("烧钱没单", "指标拆解", "CTR", "CVR")),
]


def result_text(result: dict) -> str:
    metadata = result.get("metadata", {})
    fields = [
        result.get("text", ""),
        metadata.get("title", ""),
        metadata.get("category", ""),
        metadata.get("source_path", ""),
    ]
    return "\n".join(str(field) for field in fields)


def evaluate_case(db_path: Path, case: EvalCase, limit: int = 5) -> dict:
    results = search_chunks(db_path, case.question, limit=limit, category_key=case.category_key)
    combined = "\n".join(result_text(result) for result in results).lower()
    matched = [keyword for keyword in case.expected_any if keyword.lower() in combined]
    return {
        "id": case.case_id,
        "question": case.question,
        "category_key": case.category_key,
        "passed": bool(results) and bool(matched),
        "matched_keywords": matched,
        "expected_any": list(case.expected_any),
        "top_results": [
            {
                "id": result.get("id"),
                "title": result.get("metadata", {}).get("title"),
                "category": result.get("metadata", {}).get("category"),
                "score": result.get("score"),
            }
            for result in results[:3]
        ],
    }


def run_eval(db_path: Path, limit: int = 5) -> dict:
    cases = [evaluate_case(db_path, case, limit=limit) for case in EVAL_CASES]
    passed = sum(1 for case in cases if case["passed"])
    failed = len(cases) - passed
    return {
        "db": str(db_path.resolve()),
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / len(cases), 4) if cases else 0,
        "failures": [case for case in cases if not case["passed"]],
        "cases": cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate local RAG retrieval against common ad-ops questions.")
    parser.add_argument("--db", default=Path("output/30tian_chuhai.sqlite"), type=Path)
    parser.add_argument("--report", default=Path("output/eval_report.json"), type=Path)
    parser.add_argument("--limit", default=5, type=int)
    parser.add_argument("--min-pass-rate", default=0.0, type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_eval(args.db, limit=args.limit)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("total", "passed", "failed", "pass_rate")}, ensure_ascii=False, indent=2))
    if report["pass_rate"] < args.min_pass_rate:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
