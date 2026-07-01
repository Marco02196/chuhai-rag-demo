import argparse
import hashlib
import html
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


CATEGORY_KEYS = {
    "投放策略库": "ad_strategy",
    "素材与文案库": "creative_copy",
    "技术落地库": "tech_execution",
    "风控与踩坑库": "risk_playbook",
    "复盘案例库": "review_cases",
}


SOURCES = {
    "meta_pixel": {
        "url": "https://www.facebook.com/business/help/952192354843755",
        "category": "技术落地库",
        "fallback_title": "Meta Pixel 官方说明",
    },
    "meta_capi": {
        "url": "https://www.facebook.com/business/help/2041148702652965",
        "category": "技术落地库",
        "fallback_title": "Meta Conversions API 官方说明",
    },
    "meta_relevance": {
        "url": "https://www.facebook.com/business/help/403110480493160",
        "category": "投放策略库",
        "fallback_title": "Meta 广告相关性诊断官方说明",
    },
    "meta_learning": {
        "url": "https://www.facebook.com/business/help/112167992830700",
        "category": "投放策略库",
        "fallback_title": "Meta 广告学习期官方说明",
    },
    "tiktok_pixel": {
        "url": "https://ads.tiktok.com/help/article/create-pixel",
        "category": "技术落地库",
        "fallback_title": "TikTok Pixel 官方说明",
    },
    "tiktok_events_api": {
        "url": "https://ads.tiktok.com/help/article/events-api",
        "category": "技术落地库",
        "fallback_title": "TikTok Events API 官方说明",
    },
    "tiktok_ad_review": {
        "url": "https://ads.tiktok.com/help/article/ad-review-checklist",
        "category": "风控与踩坑库",
        "fallback_title": "TikTok 广告审核清单官方说明",
    },
    "tiktok_creative": {
        "url": "https://ads.tiktok.com/help/article/creative-best-practices",
        "category": "素材与文案库",
        "fallback_title": "TikTok 创意最佳实践官方说明",
    },
    "web_vitals": {
        "url": "https://web.dev/articles/vitals",
        "category": "技术落地库",
        "fallback_title": "Google Web Vitals 官方说明",
    },
    "web_lcp": {
        "url": "https://web.dev/articles/lcp",
        "category": "技术落地库",
        "fallback_title": "Google LCP 官方说明",
    },
    "web_cls": {
        "url": "https://web.dev/articles/cls",
        "category": "技术落地库",
        "fallback_title": "Google CLS 官方说明",
    },
    "web_inp": {
        "url": "https://web.dev/articles/inp",
        "category": "技术落地库",
        "fallback_title": "Google INP 官方说明",
    },
}


CARDS = [
    {
        "source": "meta_relevance",
        "title": "CTR 高但 CVR 低时先拆相关性与落地承接",
        "category": "投放策略库",
        "question": "CTR 高但 CVR 很低，是素材、人群还是落地页问题？",
        "scenario": "广告点击率看起来不错，但加购、提交表单或购买转化偏低。",
        "diagnosis": "先把问题拆成三层：素材是否吸引了正确人群、点击后落地页是否承接了承诺、转化事件是否被正确记录。CTR 高只能说明入口有吸引力，不能直接证明流量质量好。",
        "actions": [
            "对比同受众下不同素材的 CVR，判断是否标题党或承诺过度。",
            "检查落地页首屏卖点、加载速度、价格/运费/支付信任信息。",
            "核对 Pixel、CAPI 或 Events API 的关键事件是否重复、漏传或延迟。",
        ],
        "risk": "不要只因为 CTR 高就继续加预算；如果 CVR 长时间低，放量会放大亏损。",
        "keywords": "CTR CVR 转化 落地页 相关性 事件回传",
    },
    {
        "source": "meta_relevance",
        "title": "低 CTR 先看素材吸引力与受众匹配",
        "category": "素材与文案库",
        "question": "广告没人点，先改素材还是调人群？",
        "scenario": "曝光正常但点击率低，CPM 未必异常。",
        "diagnosis": "低 CTR 通常说明素材、Hook、首屏利益点或受众匹配存在问题。先用同受众测试不同 Hook，再用同素材测试不同受众，避免一次改太多变量。",
        "actions": [
            "保留一个基准受众，只换首 3 秒 Hook、主图或标题。",
            "把卖点写成具体结果、痛点或使用场景，减少泛泛描述。",
            "观察点击率、停留时长和评论反馈，判断是否只是噱头点击。",
        ],
        "risk": "只扩受众不改素材，可能让系统更快把预算花到低意图人群。",
        "keywords": "CTR Hook 素材 受众 点击率",
    },
    {
        "source": "meta_learning",
        "title": "学习期内不要频繁大改预算和受众",
        "category": "投放策略库",
        "question": "广告刚跑两天数据波动大，要不要马上重建？",
        "scenario": "新广告组刚启动，转化数量少，成本和 ROAS 波动明显。",
        "diagnosis": "学习期内系统仍在探索人群和出价空间，短时间内的 CPA 或 ROAS 波动不一定代表模型失效。频繁改预算、受众、优化事件或创意组合，会让系统重新探索。",
        "actions": [
            "先确认花费是否已经达到足够判断量，不要只看几个点击或一两单。",
            "必要调整时优先小幅调整预算，避免同时改受众、素材和事件。",
            "把学习期计划和成熟计划分开复盘，避免用同一阈值误杀。",
        ],
        "risk": "过早关停可能错过系统学习后的回正；但无点击质量和无加购信号的计划仍要止损。",
        "keywords": "学习期 预算 调整 关停 放量",
    },
    {
        "source": "meta_pixel",
        "title": "Pixel 异常会让投放诊断失真",
        "category": "技术落地库",
        "question": "CPA、ROAS 或转化数据看起来不准，先查什么？",
        "scenario": "广告后台、站内订单、GA 或 CRM 数据对不上。",
        "diagnosis": "Pixel 是前端事件采集基础。如果 PageView、ViewContent、AddToCart、Purchase 等事件漏传、重复或参数缺失，投放系统会基于错误信号优化。",
        "actions": [
            "逐个检查关键页面是否触发对应事件。",
            "核对 purchase value、currency、content_id 等参数是否稳定。",
            "用测试事件工具或浏览器调试检查重复触发和触发时机。",
        ],
        "risk": "数据不准时不要只按广告后台 CPA 做关停决策，要和订单系统交叉验证。",
        "keywords": "Pixel CPA ROAS 事件 回传 Purchase AddToCart",
    },
    {
        "source": "meta_capi",
        "title": "CAPI 用来补强浏览器事件丢失，不是替代所有前端检查",
        "category": "技术落地库",
        "question": "接了 CAPI 以后为什么数据还是不准？",
        "scenario": "已经接入服务端回传，但广告平台事件质量或归因仍异常。",
        "diagnosis": "服务端回传可以降低浏览器限制、网络拦截和 Cookie 损耗带来的数据丢失，但仍需要做好去重、事件 ID、用户匹配参数和事件命名一致性。",
        "actions": [
            "确保浏览器事件和服务端事件使用同一个 event_id 去重。",
            "检查 email、phone、external_id、IP、UA 等匹配参数是否合规且稳定。",
            "对照订单系统抽样核查 Purchase 数量和金额。",
        ],
        "risk": "CAPI 配错会造成重复转化或虚高 ROAS，反而误导预算分配。",
        "keywords": "CAPI Conversions API 去重 event_id 匹配质量",
    },
    {
        "source": "tiktok_pixel",
        "title": "TikTok Pixel 先保证基础事件链路完整",
        "category": "技术落地库",
        "question": "TikTok 投放没法优化购买，像素应该怎么查？",
        "scenario": "TikTok 广告有点击但优化事件少，系统难以学习。",
        "diagnosis": "先确认 Pixel 安装和基础事件是否覆盖完整漏斗。只装 PageView 不足以支持购买优化，必须让 ViewContent、AddToCart、InitiateCheckout、Purchase 等关键事件稳定触发。",
        "actions": [
            "从落地页到支付成功页逐步测试事件触发。",
            "检查事件命名和参数是否与广告平台配置一致。",
            "对比广告平台事件数和站内订单数，定位丢失环节。",
        ],
        "risk": "事件链路不完整时强行放量，会让系统用弱信号学习，导致花费效率下降。",
        "keywords": "TikTok Pixel Purchase AddToCart 事件优化",
    },
    {
        "source": "tiktok_events_api",
        "title": "Events API 适合补齐服务端转化信号",
        "category": "技术落地库",
        "question": "TikTok 数据回传不稳，什么时候要接 Events API？",
        "scenario": "浏览器事件容易丢、支付成功页跳转不稳定、移动端 WebView 转化难追踪。",
        "diagnosis": "Events API 可以从服务端发送关键转化事件，提高信号完整性。它更适合承接订单、支付、线索提交等后端确认事件。",
        "actions": [
            "优先把 Purchase、CompletePayment 或 Lead 等强转化事件接到服务端。",
            "做好事件去重和用户匹配参数，避免重复计数。",
            "用小流量灰度验证事件数量、金额和时间延迟。",
        ],
        "risk": "不要在前后端同时上报却没有去重，否则会把转化效果算高。",
        "keywords": "TikTok Events API 服务端回传 去重 购买事件",
    },
    {
        "source": "tiktok_creative",
        "title": "TikTok 素材疲劳优先看前段吸引力和重复曝光",
        "category": "素材与文案库",
        "question": "素材跑几天后掉量掉转化，是不是疲劳了？",
        "scenario": "同一素材初期表现好，随后 CTR、CVR 或 CPA 变差。",
        "diagnosis": "素材疲劳通常表现为用户对同一创意的反应下降。先看 CTR、完播/停留、频次、评论反馈和 CPA 趋势，而不是只看一天 ROAS。",
        "actions": [
            "保留核心卖点，替换开头 3 秒、镜头顺序、字幕和 CTA。",
            "把爆款素材拆成多个变体，分别测试 Hook、证明点和使用场景。",
            "对高频曝光人群做排除或扩展新受众。",
        ],
        "risk": "只复制爆款不改结构，容易短期复刻点击但无法维持转化。",
        "keywords": "TikTok 素材疲劳 Hook 频次 CTR CPA",
    },
    {
        "source": "tiktok_ad_review",
        "title": "广告审核问题先拆素材、落地页和商品承诺",
        "category": "风控与踩坑库",
        "question": "广告被拒，是素材违规还是落地页问题？",
        "scenario": "广告审核不通过、账户风险升高或素材频繁被拒。",
        "diagnosis": "审核不只看视频或图片，也会看文案、商品承诺、落地页一致性、禁限品和夸大表达。先按素材、文案、落地页、商品资质四类排查。",
        "actions": [
            "删除夸大收益、绝对化承诺、前后对比过度和敏感词。",
            "确保广告承诺与落地页价格、功能、配送、退款信息一致。",
            "对高风险品类准备资质、免责声明和更保守的表达。",
        ],
        "risk": "反复提交相同违规素材可能影响账户资产稳定性。",
        "keywords": "广告审核 被拒 风控 落地页 素材违规",
    },
    {
        "source": "web_vitals",
        "title": "落地页体验要纳入投放诊断",
        "category": "技术落地库",
        "question": "广告点击不少但转化低，页面性能要不要查？",
        "scenario": "CTR 正常，CVR 低，移动端用户跳出高。",
        "diagnosis": "页面体验会影响用户是否继续浏览和完成转化。核心网页指标可以帮助判断加载、交互和视觉稳定性是否拖累广告转化。",
        "actions": [
            "先看移动端 LCP、INP、CLS，再看页面首屏是否承接广告承诺。",
            "压缩首屏图片和脚本，优先保证商品信息、价格和 CTA 可见。",
            "把页面性能变化和广告 CVR、跳出率放在同一天对照。",
        ],
        "risk": "只优化广告素材不修落地页，会把更多流量导入低转化页面。",
        "keywords": "Core Web Vitals LCP INP CLS 落地页 CVR",
    },
    {
        "source": "web_lcp",
        "title": "LCP 差优先处理首屏最大内容",
        "category": "技术落地库",
        "question": "落地页打开慢，先修哪里？",
        "scenario": "移动端首屏加载慢，广告点击后用户快速退出。",
        "diagnosis": "LCP 关注首屏最大内容出现速度。电商落地页常见问题是大图过重、首屏脚本阻塞、服务器响应慢或字体/组件加载拖延。",
        "actions": [
            "压缩并预加载首屏主图，使用合适尺寸和现代图片格式。",
            "延后非关键脚本，减少首屏第三方标签阻塞。",
            "检查 CDN、缓存和服务器响应时间。",
        ],
        "risk": "只看桌面速度没有意义，出海投放要优先按目标市场移动网络测试。",
        "keywords": "LCP 首屏 加载速度 图片 CDN 落地页",
    },
    {
        "source": "web_cls",
        "title": "CLS 高会破坏支付和表单体验",
        "category": "技术落地库",
        "question": "页面视觉跳动会影响转化吗？",
        "scenario": "用户点击按钮时页面元素移动，表单或支付入口错位。",
        "diagnosis": "CLS 衡量视觉稳定性。图片未预留尺寸、广告位后加载、字体切换或动态组件插入，都可能让用户误点或放弃操作。",
        "actions": [
            "给图片、视频、广告位和嵌入组件预留固定尺寸。",
            "避免在用户即将操作区域上方突然插入内容。",
            "检查移动端弹窗、优惠条和信任徽章是否造成布局跳动。",
        ],
        "risk": "CLS 问题不一定会直接显示在广告后台，但会体现在 CVR 和支付完成率下降。",
        "keywords": "CLS 布局偏移 视觉稳定 支付 表单",
    },
    {
        "source": "web_inp",
        "title": "INP 差说明页面交互响应慢",
        "category": "技术落地库",
        "question": "用户点按钮没反应，投放诊断里怎么处理？",
        "scenario": "落地页首屏能打开，但加购、规格选择、支付按钮响应慢。",
        "diagnosis": "INP 关注用户交互响应。大量脚本、复杂组件、第三方追踪标签或主线程阻塞，会让页面看起来已加载但操作迟钝。",
        "actions": [
            "减少首屏非必要 JS，拆分复杂组件。",
            "优化加购、支付、表单提交等关键交互路径。",
            "在低端手机和目标地区网络下复测。",
        ],
        "risk": "交互慢会让用户误以为页面坏了，导致加购和支付漏斗掉点。",
        "keywords": "INP 交互响应 JS 主线程 加购 支付",
    },
    {
        "source": "meta_relevance",
        "title": "ROI 低不要只看结果，要拆点击质量和转化承接",
        "category": "投放策略库",
        "question": "ROI 连续低于 1，应该直接关停吗？",
        "scenario": "广告已经跑出一定花费，ROAS/ROI 低于目标，但仍有点击或少量加购。",
        "diagnosis": "先判断亏损来自入口质量、转化承接还是数据回传。CTR 低且 CPM 高偏素材或受众；CTR 高 CVR 低偏落地页、价格、支付或回传；有加购无购买偏信任、运费、支付链路。",
        "actions": [
            "把广告组按无点击、无加购、有加购无购买、有购买四类分层。",
            "无有效行为且花费达到阈值的广告组先止损。",
            "有加购或高质量点击的广告组降预算观察，并同步查落地页和事件。",
        ],
        "risk": "只按一天 ROI 关停容易误杀学习期计划；只因为有点击继续烧钱也会扩大亏损。",
        "keywords": "ROI ROAS 止损 点击质量 加购 购买",
    },
    {
        "source": "meta_learning",
        "title": "预算调整要避免让系统频繁重新探索",
        "category": "投放策略库",
        "question": "广告表现忽上忽下，预算要怎么调？",
        "scenario": "广告组有转化但成本波动大，团队想频繁加减预算。",
        "diagnosis": "预算是系统学习的重要信号。过于频繁或大幅度调整，会让算法重新探索，导致短期波动更大。成熟计划可以小幅调，探索计划要先看样本量。",
        "actions": [
            "对成熟且稳定的计划做小幅预算调整，而不是一次翻倍。",
            "对学习期计划先积累足够转化样本，再判断是否扩量。",
            "预算变化后至少观察一个完整投放周期，再做下一次动作。",
        ],
        "risk": "把学习期波动当成失败，可能导致账户一直停留在重建和探索状态。",
        "keywords": "预算 学习期 波动 放量 降预算",
    },
    {
        "source": "meta_relevance",
        "title": "广告诊断先固定变量，避免同时改素材和受众",
        "category": "投放策略库",
        "question": "投放效果差，能不能素材、人群、预算一起改？",
        "scenario": "广告效果不达标，团队想快速大改多个设置。",
        "diagnosis": "同时改多个变量会让复盘失去结论。诊断时应一次只改变一个关键变量，先确认素材吸引力、受众匹配或落地页承接中的主要矛盾。",
        "actions": [
            "素材测试时固定受众和预算，只换创意版本。",
            "受众测试时固定素材和落地页，只换人群包或兴趣条件。",
            "落地页测试时保持广告入口一致，观察 CVR 和跳出变化。",
        ],
        "risk": "多变量同时变动会让短期结果看似改善，但无法沉淀 SOP。",
        "keywords": "变量控制 A/B测试 素材 受众 预算",
    },
    {
        "source": "tiktok_creative",
        "title": "TikTok 创意要把卖点前置到开头几秒",
        "category": "素材与文案库",
        "question": "TikTok 视频前几秒留不住人怎么办？",
        "scenario": "视频有曝光但完播、点击或互动偏低。",
        "diagnosis": "短视频广告需要快速交代痛点、结果或冲突。前几秒如果只是品牌铺垫、慢节奏展示或信息密度低，用户很容易划走。",
        "actions": [
            "开头直接放痛点、结果对比、强场景或用户问题。",
            "把产品利益点用字幕和画面同时表达。",
            "同一卖点测试三种开头：问题式、结果式、反差式。",
        ],
        "risk": "只追求夸张开头会带来低质量点击，后续必须用 CVR 验证。",
        "keywords": "TikTok Hook 前三秒 完播 CTR 素材",
    },
    {
        "source": "tiktok_creative",
        "title": "素材测试要拆 Hook、证明点和 CTA",
        "category": "素材与文案库",
        "question": "怎么系统化测试素材，而不是凭感觉换视频？",
        "scenario": "团队持续上新素材，但不知道哪个元素影响结果。",
        "diagnosis": "素材不是一个整体变量，应拆成 Hook、痛点、产品证明、使用场景、信任背书、CTA。每轮测试只改一个主要模块，才能沉淀可复用结论。",
        "actions": [
            "先固定主体脚本，批量测试 3-5 个不同 Hook。",
            "找到高点击 Hook 后，再测试证明点和 CTA。",
            "记录每个素材的 CTR、CVR、CPA、频次和评论反馈。",
        ],
        "risk": "只记录素材文件名不记录结构，后续无法复用爆款规律。",
        "keywords": "素材测试 Hook CTA 证明点 脚本",
    },
    {
        "source": "tiktok_creative",
        "title": "UGC 素材要保留真实感但不能牺牲信息清晰度",
        "category": "素材与文案库",
        "question": "UGC 素材真实但转化差，怎么优化？",
        "scenario": "达人口播或用户感视频有互动，但购买转化不稳定。",
        "diagnosis": "UGC 的优势是真实和信任，但转化仍依赖清楚的痛点、产品证据、使用结果和 CTA。如果只是生活化展示，用户可能看完但不知道为什么买。",
        "actions": [
            "口播脚本按痛点、解决方案、证据、优惠、行动五段压缩。",
            "用字幕强化价格、功能、适用人群和购买理由。",
            "在视频中加入真实使用前后、评价截图或场景证明。",
        ],
        "risk": "过度包装会破坏真实感；过度真实又可能缺少销售力。",
        "keywords": "UGC 口播 真实感 转化 CTA",
    },
    {
        "source": "tiktok_ad_review",
        "title": "审核前先做素材风险自检",
        "category": "风控与踩坑库",
        "question": "广告上线前怎么减少被拒概率？",
        "scenario": "新素材准备上线，担心审核被拒或账户风险累积。",
        "diagnosis": "审核风险常来自夸大承诺、敏感品类、前后对比、医疗/金融等高风险表达、落地页信息不一致。上线前用清单自检比被拒后反复修改更稳。",
        "actions": [
            "检查是否有绝对化、保证收益、夸大效果或误导性表述。",
            "核对落地页价格、功能、配送、退款和资质信息。",
            "高风险词替换为更保守、可证明、场景化的表达。",
        ],
        "risk": "反复被拒不仅影响素材，还可能拖累账户和资产稳定性。",
        "keywords": "审核 被拒 风控 素材 落地页",
    },
    {
        "source": "tiktok_ad_review",
        "title": "被拒素材先改风险点，不要原样反复提交",
        "category": "风控与踩坑库",
        "question": "广告被拒后是申诉还是重做？",
        "scenario": "素材或落地页审核失败，团队想快速重新提交。",
        "diagnosis": "如果是明显违规或承诺过度，优先修改素材和落地页；如果判断为误判，再准备证据申诉。原样反复提交会增加资产风险。",
        "actions": [
            "先定位拒审原因属于素材、文案、商品、落地页还是资质。",
            "能明确修改的先改，不能判断的保留截图和资质再申诉。",
            "建立拒审原因表，沉淀高风险词和高风险画面。",
        ],
        "risk": "把申诉当万能解法会拖慢投放节奏，也可能积累负面审核记录。",
        "keywords": "拒审 申诉 修改 素材风险 账户资产",
    },
    {
        "source": "meta_pixel",
        "title": "Purchase 金额和币种错误会直接误导 ROAS",
        "category": "技术落地库",
        "question": "订单数对得上，但 ROAS 不对，可能是什么问题？",
        "scenario": "购买事件数量接近真实订单，但广告后台收入或 ROAS 异常。",
        "diagnosis": "购买事件不仅要数量准确，还要 value、currency、订单去重和退款/取消处理准确。金额或币种错误会让系统误判高价值人群。",
        "actions": [
            "抽样对比订单系统金额和广告事件 value。",
            "确认币种统一，避免 USD、CNY 或本地币混用。",
            "检查同一订单是否重复触发 Purchase。",
        ],
        "risk": "ROAS 虚高会让系统继续给错误计划分配预算。",
        "keywords": "Purchase value currency ROAS 金额 币种",
    },
    {
        "source": "meta_capi",
        "title": "事件去重是前后端双回传的核心",
        "category": "技术落地库",
        "question": "Pixel 和 CAPI 都开了，为什么转化翻倍？",
        "scenario": "浏览器和服务端同时回传购买事件，后台转化数偏高。",
        "diagnosis": "双回传必须通过 event_id 等机制去重。没有去重时，同一笔订单可能被浏览器和服务端各算一次。",
        "actions": [
            "为同一用户动作生成一致的 event_id。",
            "确保前端 Pixel 和后端 CAPI 事件名称一致。",
            "抽样核对一批订单在广告平台里的事件数量。",
        ],
        "risk": "重复转化会让系统误以为广告效果更好，导致错误放量。",
        "keywords": "event_id 去重 Pixel CAPI 重复转化",
    },
    {
        "source": "tiktok_events_api",
        "title": "服务端回传要关注延迟和事件顺序",
        "category": "技术落地库",
        "question": "服务端事件有回传，但优化还是慢，怎么排查？",
        "scenario": "Events API 已接入，但平台学习和归因效果不稳定。",
        "diagnosis": "服务端事件如果延迟过长、事件时间不准、顺序混乱或用户匹配弱，仍会影响平台学习。强转化信号要尽量及时、准确、可匹配。",
        "actions": [
            "检查 event_time 是否使用真实事件发生时间。",
            "监控从支付成功到事件入平台的延迟。",
            "补齐合规用户匹配字段，提高匹配质量。",
        ],
        "risk": "延迟事件适合补账，但不适合完全依赖它做实时优化判断。",
        "keywords": "Events API 延迟 event_time 匹配质量",
    },
    {
        "source": "web_lcp",
        "title": "广告落地页首屏图不能只追求高清",
        "category": "技术落地库",
        "question": "落地页首屏大图很好看，为什么转化低？",
        "scenario": "设计图精美，但移动端加载慢或 CTA 出现晚。",
        "diagnosis": "首屏大图通常是 LCP 关键元素。图片过大、未压缩、未按设备分发或阻塞加载，会让用户在看到产品卖点前离开。",
        "actions": [
            "按移动端实际展示尺寸输出图片，不上传超大原图。",
            "首屏核心图使用预加载，非首屏图延迟加载。",
            "把 CTA、价格和核心卖点放在首屏可见区域。",
        ],
        "risk": "视觉精致但加载慢，会让投放成本转化为跳出。",
        "keywords": "首屏大图 LCP 图片压缩 CTA 移动端",
    },
    {
        "source": "web_vitals",
        "title": "页面性能问题要和广告指标同表复盘",
        "category": "复盘案例库",
        "question": "怎么判断亏损是不是落地页性能导致的？",
        "scenario": "同一素材在不同日期 CVR 波动，页面或服务器也有改动。",
        "diagnosis": "把广告指标和页面指标放在同一天复盘：CTR、CVR、CPA、LCP、INP、CLS、错误率、支付成功率。若 CTR 稳定但 CVR 随页面指标恶化同步下降，落地页嫌疑更高。",
        "actions": [
            "建立日报字段：CTR、CVR、CPA、ROAS、LCP、INP、CLS。",
            "标记每次页面发布、脚本新增、支付组件变更。",
            "用日期对齐判断广告问题还是页面问题。",
        ],
        "risk": "只看广告后台会把技术问题误判为素材或受众问题。",
        "keywords": "复盘 日报 页面性能 CVR LCP INP CLS",
    },
    {
        "source": "web_cls",
        "title": "优惠条和弹窗不能破坏关键操作区",
        "category": "技术落地库",
        "question": "优惠弹窗会不会影响购买？",
        "scenario": "落地页加入优惠条、弹窗、倒计时或信任徽章后转化变差。",
        "diagnosis": "促销组件可能提升紧迫感，也可能造成布局偏移、遮挡 CTA 或打断支付。要同时看点击率、加购率、CLS 和用户路径。",
        "actions": [
            "优惠条固定高度，避免加载后把内容往下挤。",
            "弹窗不要覆盖规格选择、加购和支付按钮。",
            "A/B 测试促销组件对 CVR 和客诉的影响。",
        ],
        "risk": "促销组件短期提高点击，却可能降低最终付款率。",
        "keywords": "优惠弹窗 CLS CTA 加购 支付",
    },
    {
        "source": "web_inp",
        "title": "支付和表单交互慢要优先于普通动画优化",
        "category": "技术落地库",
        "question": "页面很炫但用户不付款，技术上先查什么？",
        "scenario": "落地页动画多、组件复杂，用户在表单或支付阶段流失。",
        "diagnosis": "投放落地页的关键交互是规格选择、加购、表单提交和支付。普通动画可以后置，关键交互响应慢会直接损失转化。",
        "actions": [
            "优先压缩影响加购和支付路径的 JS。",
            "移除首屏不必要动画和第三方组件。",
            "监控表单错误率、按钮点击后响应时间和支付跳转时间。",
        ],
        "risk": "只优化视觉流畅度，不优化购买路径，无法改善广告 ROI。",
        "keywords": "INP 支付 表单 加购 JS 动画",
    },
    {
        "source": "meta_learning",
        "title": "新计划前 48 小时要分清观察指标和决策指标",
        "category": "投放策略库",
        "question": "新计划前两天看什么，哪些指标不能急着下结论？",
        "scenario": "新广告刚上线，转化还少，团队想快速判断是否保留。",
        "diagnosis": "早期转化少时，ROAS 和 CPA 可能波动很大。更适合先看曝光、点击、CTR、加购、页面停留和事件链路，确认是否有继续观察的信号。",
        "actions": [
            "前期用点击质量、加购和关键事件作为观察指标。",
            "达到花费或转化样本阈值后，再用 CPA/ROAS 做决策。",
            "无点击、无加购、无关键事件的计划优先止损。",
        ],
        "risk": "太早用 ROAS 做唯一指标，容易误判高潜计划。",
        "keywords": "新计划 48小时 观察指标 决策指标 ROAS",
    },
    {
        "source": "tiktok_pixel",
        "title": "TikTok 优化事件要和真实业务目标一致",
        "category": "投放策略库",
        "question": "TikTok 是优化点击、加购还是购买？",
        "scenario": "账户转化少，团队纠结优化事件应该选哪个。",
        "diagnosis": "优化事件越接近真实业务目标，信号越有价值；但如果购买事件太少，系统可能学不动。可以阶段性从弱事件过渡到强事件。",
        "actions": [
            "冷启动时先保证 ViewContent/AddToCart/Purchase 链路完整。",
            "有足够购买事件后优先转向 Purchase 或 CompletePayment 优化。",
            "不要长期只优化点击，否则容易获得低意图流量。",
        ],
        "risk": "优化事件太弱会带来表面便宜的流量，但最终 ROAS 不稳定。",
        "keywords": "TikTok 优化事件 点击 加购 购买 冷启动",
    },
    {
        "source": "meta_capi",
        "title": "数据回传质量要进入每日投放巡检",
        "category": "复盘案例库",
        "question": "每日复盘除了广告指标，还要看哪些技术指标？",
        "scenario": "团队每天看 CTR、CPA、ROAS，但忽略事件链路健康。",
        "diagnosis": "广告优化依赖事件质量。每日应检查关键事件数量、匹配质量、去重状态、金额币种和平台告警，避免数据坏了还继续按坏数据决策。",
        "actions": [
            "日报增加 Pixel/CAPI 或 Events API 健康检查项。",
            "把订单系统购买数和广告平台购买数做比例监控。",
            "出现突变时先查发布、支付、埋点和服务端日志。",
        ],
        "risk": "事件坏了当天仍然放量，可能让算法学习到错误信号。",
        "keywords": "每日复盘 数据回传 Pixel CAPI 事件质量",
    },
]


EXTRA_CARDS = [
    {
        "source": "meta_learning",
        "title": "冷启动预算先买到足够信号，再谈放量",
        "category": "投放策略库",
        "question": "新广告刚开跑，预算到底要给多少才不算瞎烧？",
        "scenario": "新计划没有历史转化，团队既担心预算太小学不动，也担心一开始就花太猛。",
        "diagnosis": "冷启动不是越省越安全，也不是越砸越快。预算要围绕目标事件的学习信号来设，至少让系统有机会获得点击、加购或购买样本；但在信号不足前，不应因为一两小时数据好坏就频繁改预算。",
        "actions": [
            "先定义冷启动观察窗口，例如 24-48 小时或达到一组最低点击/加购样本。",
            "预算按可承受测试成本设置，不用第一天就追求盈利。",
            "只在完全无点击、无加购、事件异常或审核风险时提前止损。",
        ],
        "risk": "预算太小会导致没有学习信号；预算太大又会在错误素材或错误事件上快速放大亏损。",
        "keywords": "冷启动 预算 学习期 信号 点击 加购 放量",
    },
    {
        "source": "meta_learning",
        "title": "放量要看边际成本，而不是只看昨天 ROAS",
        "category": "投放策略库",
        "question": "广告昨天赚钱了，今天能不能直接翻倍预算？",
        "scenario": "某个广告组短期 ROAS 好转，团队想快速扩大预算。",
        "diagnosis": "放量判断要看连续性、样本量和边际成本。单日 ROAS 好不代表受众空间足够，也不代表素材疲劳不会马上出现。成熟计划适合渐进加预算，并同步观察 CPA、频次、CTR 和 CVR 是否劣化。",
        "actions": [
            "先确认不是单笔大额订单或归因延迟造成的偶然好看。",
            "分阶段小幅增加预算，观察至少一个完整投放周期。",
            "如果 CPA 上升、频次上升且 CTR 下降，优先补素材或扩受众，而不是继续硬加预算。",
        ],
        "risk": "直接翻倍预算可能让系统重新探索，短期成本抬升，甚至把原本可盈利计划推成亏损。",
        "keywords": "放量 扩量 加预算 ROAS CPA 频次 素材疲劳",
    },
    {
        "source": "meta_relevance",
        "title": "低 CPM 不等于便宜流量，先看转化质量",
        "category": "投放策略库",
        "question": "CPM 很低但不出单，是不是还能继续跑？",
        "scenario": "广告展示成本便宜，点击也有，但加购和购买表现弱。",
        "diagnosis": "低 CPM 只能说明曝光便宜，不等于流量有购买意图。如果低 CPM 同时伴随低 CTR、低停留、低加购，可能是系统拿到了低竞争但低价值的人群。",
        "actions": [
            "把 CPM、CTR、CVR、加购率和购买率放在一起看。",
            "检查素材是否吸引了泛娱乐点击而不是购买人群。",
            "如果便宜曝光没有关键行为，应止损或换目标事件/人群。",
        ],
        "risk": "迷恋低 CPM 会让预算流向低意图流量，表面便宜，实际更贵。",
        "keywords": "CPM 低 不出单 流量质量 CTR CVR 购买意图",
    },
    {
        "source": "meta_relevance",
        "title": "高频曝光后效果变差，要拆受众饱和与素材疲劳",
        "category": "投放策略库",
        "question": "广告频次上来了，转化掉了怎么办？",
        "scenario": "同一批受众反复看到广告，CTR 或 CVR 开始下降，CPA 升高。",
        "diagnosis": "频次升高后效果变差，常见原因是受众池变窄、素材看腻、优惠吸引力下降或竞价环境变化。先判断是点击掉了还是点击后转化掉了。",
        "actions": [
            "CTR 掉得明显时优先换 Hook、首图、前三秒和主卖点。",
            "CTR 稳定但 CVR 掉时检查落地页、价格、库存、支付和信任信息。",
            "对高频已触达人群做排除或分层再营销。",
        ],
        "risk": "只扩大预算不扩素材和受众，会把疲劳问题放大。",
        "keywords": "频次 素材疲劳 受众饱和 CTR CVR CPA",
    },
    {
        "source": "tiktok_creative",
        "title": "爆款素材要拆成可复制变量，而不是只复制视频",
        "category": "素材与文案库",
        "question": "有条素材爆了，怎么复制出下一条爆款？",
        "scenario": "某条视频短期效果好，团队想快速批量生产同类素材。",
        "diagnosis": "爆款不能只复制外壳，要拆出真正有效的变量：开头冲突、痛点表述、产品证明、使用场景、评论反馈、优惠和 CTA。复制结构比复制画面更稳定。",
        "actions": [
            "把爆款拆成 Hook、场景、证明点、转折、CTA 五段。",
            "每次只替换一个模块，保留其余结构做对照。",
            "记录每个变体的 CTR、CVR、CPA 和评论关键词。",
        ],
        "risk": "照抄原视频容易快速疲劳，也可能因为语境变化导致转化不稳定。",
        "keywords": "爆款 素材复制 Hook 变量 CTR CVR CTA",
    },
    {
        "source": "tiktok_creative",
        "title": "素材评论区是低成本选题库",
        "category": "素材与文案库",
        "question": "不知道下一批素材拍什么，能从哪里找选题？",
        "scenario": "团队素材灵感不足，投放反馈分散在评论、私信和客服问题里。",
        "diagnosis": "评论区经常暴露用户的真实疑虑、使用场景、价格阻力和竞品对比。把评论整理成素材选题，比凭感觉写脚本更接近真实需求。",
        "actions": [
            "每周整理高频评论：质疑、想要、担心、对比、吐槽。",
            "把每类评论改写成一个视频 Hook 或口播问题。",
            "优先拍能回答购买阻力的问题，例如价格、效果、适用人群和售后。",
        ],
        "risk": "只看点赞高的评论会偏娱乐化，要同时看是否和购买阻力相关。",
        "keywords": "评论区 素材选题 用户疑虑 购买阻力 Hook",
    },
    {
        "source": "tiktok_creative",
        "title": "文案先讲具体结果，再讲产品功能",
        "category": "素材与文案库",
        "question": "广告文案总是很平，怎么写得更能卖？",
        "scenario": "文案堆功能、堆形容词，但用户不知道为什么要点进去。",
        "diagnosis": "投放文案要先让用户看到和自己有关的结果、痛点或场景，再解释产品功能。功能是证据，不是开头。越具体的结果越容易筛选正确人群。",
        "actions": [
            "把抽象卖点改成具体场景，例如省时、少踩坑、降低浪费。",
            "第一句优先写用户问题，不要先写品牌自夸。",
            "用数字、对比、步骤或真实场景增强可信度。",
        ],
        "risk": "结果承诺不能夸大，尤其健康、金融、收益类表达要保守。",
        "keywords": "文案 卖点 结果 功能 Hook CTA",
    },
    {
        "source": "tiktok_creative",
        "title": "素材日历要按假设排，而不是按拍摄日期排",
        "category": "素材与文案库",
        "question": "素材更新很勤，但还是不知道为什么有效，怎么办？",
        "scenario": "团队持续上新素材，但复盘时只知道哪条好，不知道好在哪里。",
        "diagnosis": "素材日历应该围绕测试假设组织：这周测 Hook，下周测证明点，再测优惠和 CTA。按假设排期，才能把投放结果沉淀成可复用经验。",
        "actions": [
            "每批素材只验证一个主假设，例如痛点开头是否优于结果开头。",
            "给素材命名加入变量标签，例如 hook_problem、proof_review、cta_offer。",
            "复盘时按变量汇总，而不是只按视频文件汇总。",
        ],
        "risk": "只按数量上新会形成素材流水线，但不会形成素材方法论。",
        "keywords": "素材日历 测试假设 Hook 证明点 CTA 复盘",
    },
    {
        "source": "meta_pixel",
        "title": "UTM 和广告命名要服务复盘，不只是方便投放",
        "category": "技术落地库",
        "question": "广告后台和 GA 看数据对不上，怎么做复盘更清楚？",
        "scenario": "广告平台、GA、店铺后台和表格命名不统一，复盘难以归因到素材或人群。",
        "diagnosis": "跨平台复盘需要统一命名和 UTM 规则。否则即使事件回传没问题，团队也很难判断哪条素材、哪个人群、哪个落地页带来了结果。",
        "actions": [
            "命名结构包含市场、渠道、目标、人群、素材变量和日期。",
            "UTM 参数和广告命名保持一一对应，避免手工随意填写。",
            "每周抽样检查广告后台、GA 和订单系统是否能通过命名串起来。",
        ],
        "risk": "没有统一命名时，复盘会停留在感觉层面，无法沉淀可复制结论。",
        "keywords": "UTM 命名 GA 复盘 归因 素材变量",
    },
    {
        "source": "meta_pixel",
        "title": "加购很多但购买少，要优先查支付和信任链路",
        "category": "技术落地库",
        "question": "加购不少但没人付款，是广告问题还是网站问题？",
        "scenario": "广告能带来 AddToCart 或 InitiateCheckout，但 Purchase 明显偏少。",
        "diagnosis": "加购到购买断层通常发生在价格、运费、优惠码、支付方式、库存、信任背书或页面技术问题上。广告已经把用户带到购买意图附近，下一步要查交易链路。",
        "actions": [
            "检查运费、税费、优惠码和最终价格是否在结账阶段突然变化。",
            "测试主流支付方式在目标市场是否可用、是否加载慢。",
            "补充退换货、配送时效、评价和安全支付信息。",
        ],
        "risk": "此时继续换素材可能掩盖真正的支付或信任问题。",
        "keywords": "加购 购买少 支付 运费 信任 Checkout Purchase",
    },
    {
        "source": "meta_capi",
        "title": "事件匹配质量下降时，先查用户参数完整性",
        "category": "技术落地库",
        "question": "CAPI 有回传但匹配质量低，该怎么排查？",
        "scenario": "服务端事件能发到平台，但匹配质量或归因效果不理想。",
        "diagnosis": "匹配质量依赖合规的用户标识和事件参数。邮箱、手机号、外部 ID、IP、UA、点击 ID 等字段缺失或格式不稳定，会降低平台识别同一用户行为的能力。",
        "actions": [
            "检查服务端是否稳定传递 email、phone、external_id、IP、UA 等合规字段。",
            "确认字段格式、哈希方式和空值处理一致。",
            "把匹配质量纳入每日技术巡检，而不是只看事件数量。",
        ],
        "risk": "只看事件发送成功，不看匹配质量，会高估回传系统的有效性。",
        "keywords": "CAPI 匹配质量 用户参数 external_id IP UA 归因",
    },
    {
        "source": "tiktok_events_api",
        "title": "支付成功页丢事件，要把购买事件放到后端确认",
        "category": "技术落地库",
        "question": "用户付款成功了，但广告后台少记购买，为什么？",
        "scenario": "用户支付后没有稳定回到成功页，或移动端 WebView 跳转丢失前端事件。",
        "diagnosis": "依赖支付成功页触发前端购买事件，容易因为跳转、网络、浏览器限制或用户关闭页面而丢失。更稳的做法是以后端订单确认为准发送购买事件。",
        "actions": [
            "用订单支付成功回调触发 Purchase 或 CompletePayment。",
            "前端事件和后端事件使用一致的 event_id 做去重。",
            "对比订单系统和广告平台购买事件差异，监控丢失率。",
        ],
        "risk": "只依赖成功页埋点，会让投放系统低估真实转化。",
        "keywords": "支付成功页 Purchase 后端确认 Events API CAPI 丢事件",
    },
    {
        "source": "web_vitals",
        "title": "移动端首屏要优先让用户看见商品、价格和行动按钮",
        "category": "技术落地库",
        "question": "落地页看起来很完整，但手机端转化差，先改哪里？",
        "scenario": "PC 页面信息完整，移动端首屏却看不到核心卖点或 CTA。",
        "diagnosis": "出海投放大多发生在移动端。首屏如果只有大图、品牌口号或装饰内容，用户可能在理解产品前就离开。移动端首屏要快速交代产品、利益点、价格/优惠和下一步动作。",
        "actions": [
            "用目标市场手机尺寸检查首屏，不只看桌面预览。",
            "把产品图、核心卖点、价格信号和 CTA 放到首屏可见区。",
            "减少首屏大面积装饰、过长标题和非必要弹窗。",
        ],
        "risk": "桌面端好看不代表移动端能卖，投放诊断要以主要流量设备为准。",
        "keywords": "移动端 首屏 落地页 CTA 价格 CVR",
    },
    {
        "source": "web_lcp",
        "title": "第三方脚本过多会拖慢投放页首屏",
        "category": "技术落地库",
        "question": "页面装了很多追踪和客服插件，会不会影响转化？",
        "scenario": "落地页加载了多个广告像素、客服、热力图、评论和营销插件。",
        "diagnosis": "第三方脚本会增加加载和主线程压力，影响 LCP 和 INP。投放页要区分必须脚本和锦上添花脚本，先保障首屏加载和购买路径。",
        "actions": [
            "列出所有第三方脚本，标记是否影响首屏和结账路径。",
            "延后加载非关键插件，例如热力图、评论浮窗和客服组件。",
            "上线脚本前后对比 LCP、INP、CVR 和支付完成率。",
        ],
        "risk": "追踪越多不一定复盘越好，脚本过重可能先把转化率拖垮。",
        "keywords": "第三方脚本 LCP INP 插件 落地页 CVR",
    },
    {
        "source": "tiktok_ad_review",
        "title": "素材、落地页、商品三者不一致会放大审核风险",
        "category": "风控与踩坑库",
        "question": "广告明明没写违规词，为什么还是过不了审？",
        "scenario": "素材文案看起来正常，但审核仍然失败或账户风险上升。",
        "diagnosis": "平台审核会看广告承诺、落地页内容、商品信息和用户体验是否一致。素材说免费，落地页变付费；素材说限时，页面没有说明；商品功效夸张但无证据，都会触发风险。",
        "actions": [
            "逐项核对素材承诺、落地页标题、价格、配送和退换货信息。",
            "删除无法证明的效果承诺和前后对比暗示。",
            "高风险品类准备资质、免责声明和更保守表达。",
        ],
        "risk": "只改素材不改落地页，可能反复被拒并累积账户风险。",
        "keywords": "审核 落地页一致性 商品承诺 风控 被拒",
    },
    {
        "source": "tiktok_ad_review",
        "title": "敏感品类先做保守版本测试，再逐步放开表达",
        "category": "风控与踩坑库",
        "question": "保健、美容、金融这类敏感品怎么投更稳？",
        "scenario": "产品所属行业容易触发平台审核，团队希望既能表达卖点又不伤账户。",
        "diagnosis": "敏感品类要先稳定资产，再追求激进转化。初期用事实、场景、用户体验和流程说明替代绝对化效果承诺，等账户和素材稳定后再测试更强表达。",
        "actions": [
            "准备保守素材模板，避免保证效果、夸大收益和身体羞辱表达。",
            "落地页补齐资质、免责声明、退换货和客服信息。",
            "用小预算测试审核稳定性，再扩大投放。",
        ],
        "risk": "一开始就用激进素材可能短期吸引点击，但长期伤账户资产。",
        "keywords": "敏感品类 保健 美容 金融 审核 风控 资质",
    },
    {
        "source": "meta_relevance",
        "title": "再营销要排除已购买和低价值重复触达",
        "category": "投放策略库",
        "question": "再营销一直追着老用户打，为什么 ROI 还下降？",
        "scenario": "再营销计划频次高，短期有转化，后续成本逐渐升高。",
        "diagnosis": "再营销不是无限追投。已购买用户、近期多次曝光但无行为用户、低价值访问用户需要分层处理。否则预算会消耗在重复触达和低增量转化上。",
        "actions": [
            "排除近期已购买用户，或单独做复购/交叉销售计划。",
            "按浏览、加购、结账、购买分层设置不同信息和窗口期。",
            "观察增量转化，而不是只看平台归因内的再营销 ROAS。",
        ],
        "risk": "再营销 ROAS 可能被自然回访和归因窗口美化，不能只看表面数字。",
        "keywords": "再营销 排除 已购买 频次 增量转化 ROAS",
    },
    {
        "source": "meta_relevance",
        "title": "受众重叠会让测试结果失真",
        "category": "投放策略库",
        "question": "多个广告组抢同一批人，会不会互相影响？",
        "scenario": "不同广告组使用相似兴趣、人群包或再营销窗口，数据波动明显。",
        "diagnosis": "受众重叠会让计划互相竞争，抬高成本，并让测试结论不清楚。测试不同素材或人群时，要尽量减少重叠或接受系统自动整合。",
        "actions": [
            "检查兴趣包、自定义人群和相似人群之间的重叠。",
            "同一测试目的下减少过多广告组拆分。",
            "用明确排除规则区分冷流量、暖流量和再营销人群。",
        ],
        "risk": "重叠严重时，胜出的不一定是素材或人群更好，可能只是竞价分配偶然更有利。",
        "keywords": "受众重叠 广告组 竞争 测试 人群 排除",
    },
    {
        "source": "meta_capi",
        "title": "日复盘先问数据可信不可信，再问广告好不好",
        "category": "复盘案例库",
        "question": "每天复盘第一步应该看什么？",
        "scenario": "团队每天直接看 ROI、CPA 和花费做决策，但偶尔遇到数据异常。",
        "diagnosis": "复盘第一步不是马上判断广告好坏，而是确认数据是否可信。事件是否正常、金额是否正确、归因是否突变、落地页是否发布过、支付是否异常，都会影响当天结论。",
        "actions": [
            "先看事件健康、订单对账、金额币种、支付成功率和页面错误。",
            "再看投放指标：花费、CTR、CVR、CPA、ROAS、频次。",
            "最后才做动作：关停、降预算、补素材、修页面或查回传。",
        ],
        "risk": "用坏数据做优化，比不优化更危险。",
        "keywords": "日复盘 数据可信 事件健康 订单对账 CPA ROAS",
    },
    {
        "source": "web_vitals",
        "title": "复盘要把投放动作、页面发布和技术变更放在同一时间线",
        "category": "复盘案例库",
        "question": "为什么昨天改了页面后广告数据突然变差？",
        "scenario": "投放、页面、埋点、支付或插件在同一天发生变化，团队难以归因。",
        "diagnosis": "跨团队变更如果没有时间线，投放复盘会误判。要把预算调整、素材上线、落地页发布、埋点改动、支付插件和库存变化放在同一张表里。",
        "actions": [
            "建立变更日志，记录时间、负责人、影响范围和回滚方式。",
            "数据异常时先对齐变更时间，再决定是否归因到广告。",
            "重大页面或埋点变更后保留回滚入口。",
        ],
        "risk": "没有变更日志时，团队容易把技术事故误判为素材衰退或人群不准。",
        "keywords": "复盘 时间线 变更日志 页面发布 埋点 支付",
    },
    {
        "source": "tiktok_creative",
        "title": "口语问题要被翻译成指标问题",
        "category": "复盘案例库",
        "question": "老板问钱怎么一直烧没单，我该怎么拆？",
        "scenario": "业务方用口语描述问题，投手需要转成可排查指标。",
        "diagnosis": "口语里的“烧钱没单”要拆成流量、点击、转化、支付和回传五层。先判断有没有曝光和点击，再看加购、结账、购买，最后确认数据是否被正确记录。",
        "actions": [
            "把问题翻译为：CTR 低、CVR 低、支付掉点、事件异常或样本不足。",
            "逐层排查曝光、点击、加购、结账、购买和回传。",
            "给业务方输出下一步动作，而不是只说继续观察。",
        ],
        "risk": "不做指标翻译，团队会在素材、人群、页面之间来回猜。",
        "keywords": "烧钱没单 口语问题 指标拆解 CTR CVR 支付 回传",
    },
]


CARDS.extend(EXTRA_CARDS)


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip = False
        self.title = ""
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = True
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip = False
        if tag == "title":
            self.in_title = False
        if tag in {"p", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", html.unescape(data)).strip()
        if not text:
            return
        if self.in_title:
            self.title = f"{self.title} {text}".strip()
            return
        if not self.skip:
            self.parts.append(text)

    def visible_text(self) -> str:
        text = " ".join(part for part in self.parts if part.strip())
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def stable_id(parts: list[str]) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def fetch_source(source: dict, timeout: int = 20) -> dict:
    url = source["url"]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ChuhaiRAGCrawler/1.0; +https://github.com/Marco02196/chuhai-rag-demo)"
    }
    try:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
        parser = VisibleTextParser()
        parser.feed(body)
        text = parser.visible_text()
        return {
            "url": url,
            "status": status,
            "title": parser.title or source["fallback_title"],
            "text_length": len(text),
            "domain": urlparse(url).netloc,
        }
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "status": None,
            "title": source["fallback_title"],
            "text_length": 0,
            "domain": urlparse(url).netloc,
            "error": str(exc),
        }


def card_text(card: dict, source_meta: dict) -> str:
    actions = "\n".join(f"{index}. {action}" for index, action in enumerate(card["actions"], start=1))
    return "\n".join(
        [
            f"问题：{card['question']}",
            f"适用场景：{card['scenario']}",
            f"判断逻辑：{card['diagnosis']}",
            "建议动作：",
            actions,
            f"风险提醒：{card['risk']}",
            f"关键词：{card['keywords']}",
            f"来源：{source_meta['title']} - {source_meta['url']}",
        ]
    )


def build_public_cards() -> tuple[list[dict], dict]:
    fetched = {key: fetch_source(source) for key, source in SOURCES.items()}
    chunks = []
    for index, card in enumerate(CARDS):
        source = SOURCES[card["source"]]
        source_meta = fetched[card["source"]]
        category = card.get("category") or source["category"]
        text = card_text(card, source_meta)
        source_path = f"public_web/{source_meta['domain']}/{card['source']}"
        chunks.append(
            {
                "id": f"web_{stable_id([card['source'], card['title'], text])}",
                "text": text,
                "metadata": {
                    "kb_name": "30天出海指挥部",
                    "source_type": "public_web_cleaned",
                    "category": category,
                    "category_key": CATEGORY_KEYS[category],
                    "module": "公开资料清洗卡",
                    "title": card["title"],
                    "chunk_index": index,
                    "content_type": "diagnosis_card",
                    "source_path": source_path,
                    "source_url": source_meta["url"],
                    "source_title": source_meta["title"],
                    "source_status": source_meta["status"],
                    "source_text_length": source_meta["text_length"],
                },
            }
        )
    report = {
        "sources": fetched,
        "cards": len(chunks),
        "categories": dict(Counter(chunk["metadata"]["category"] for chunk in chunks)),
    }
    return chunks, report


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")


def update_combined_chunks(base_chunks_path: Path, public_cards_path: Path, report_path: Path) -> dict:
    public_cards, report = build_public_cards()
    existing = [item for item in load_jsonl(base_chunks_path) if not str(item.get("id", "")).startswith("web_")]
    combined = existing + public_cards
    write_jsonl(public_cards_path, public_cards)
    write_jsonl(base_chunks_path, combined)
    report.update(
        {
            "base_chunks": len(existing),
            "combined_chunks": len(combined),
            "output": str(base_chunks_path.resolve()),
            "public_cards_output": str(public_cards_path.resolve()),
        }
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl public ad/landing-page sources and clean them into RAG cards.")
    parser.add_argument("--chunks", default=Path("output/30tian_chuhai_chunks.jsonl"), type=Path)
    parser.add_argument("--cards", default=Path("output/public_web_cards.jsonl"), type=Path)
    parser.add_argument("--report", default=Path("output/public_web_crawl_report.json"), type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = update_combined_chunks(args.chunks, args.cards, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
