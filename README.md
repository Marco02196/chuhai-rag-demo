# 30天出海指挥部 RAG 预处理

这个目录用于把 Notion 导出的 Markdown/CSV 知识库清洗成 RAG 可入库的 JSONL。

## 输入

当前输入目录：

```text
C:\Users\kaco_\Desktop\工作流\notion_30_export\part1
```

## 输出

当前已生成：

```text
C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai_chunks.jsonl
C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\manifest.json
```

`30tian_chuhai_chunks.jsonl` 每行是一条知识片段：

```json
{
  "id": "751e89e748e5b420",
  "text": "知识片段正文",
  "metadata": {
    "kb_name": "30天出海指挥部",
    "category": "投放策略库",
    "module": "「情绪曲线」",
    "title": "页面标题",
    "source_path": "Notion 导出相对路径",
    "content_type": "markdown"
  }
}
```

## 重跑命令

```powershell
python rag_preprocess\preprocess_notion_export.py `
  --input "C:\Users\kaco_\Desktop\工作流\notion_30_export\part1" `
  --output "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai_chunks.jsonl" `
  --max-chars 900
```

## 测试命令

```powershell
python -m unittest discover -s rag_preprocess -p "test_*.py"
```

## 当前统计

- 总 chunks：446
- Markdown chunks：265
- CSV row chunks：116
- 公开诊断卡：52
- 视频拆解卡：5
- 原始投流经验笔记：8

分类：

- 投放策略库：280
- 技术落地库：74
- 风控与踩坑库：44
- 素材与文案库：29
- 复盘案例库：16
- 通用知识库：3

## 问题诊断地图

已整理一份面向演示和销售试点的问题入口：

```text
rag_preprocess\问题诊断地图.md
```

它把可问问题分成投放策略、素材文案、技术落地、风控踩坑、复盘分析和组合诊断。做客户 Demo 时，建议先用这些高频问题按钮引导客户，而不是让客户一上来完全自由提问。

检索前还有一层口语扩展，位置在：

```text
rag_preprocess\local_retrieval.py
```

例如“钱一直烧但是不出单咋办”会被扩展到 `ROI`、`CVR`、`空烧`、`止损` 等业务词，再进入 SQLite FTS 检索。后续试点时，把客户真实问法继续补到 `COLLOQUIAL_EXPANSIONS`，识别面会越来越宽。

## 后续接向量库

下一步可以把 JSONL 每一行送入 embedding 模型，并写入 Qdrant 或 Supabase。

推荐字段映射：

- `text`：生成 embedding 的正文
- `id`：向量点 ID 或业务 ID
- `metadata`：作为 payload 保存，用于来源引用和分类过滤

## 本地检索原型

在没有 OpenAI/Qdrant 凭据前，可以先用 SQLite FTS 做本地检索验证。

### 建索引

```powershell
python rag_preprocess\local_retrieval.py build `
  --chunks "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai_chunks.jsonl" `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite"
```

### 查询示例

```powershell
python rag_preprocess\local_retrieval.py query `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite" `
  --q "ROI 小于 1 持续两天怎么办" `
  --category-key ad_strategy `
  --limit 3
```

```powershell
python rag_preprocess\local_retrieval.py query `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite" `
  --q "动态参数路由 Pixel pid goal segment 怎么实现" `
  --category-key tech_execution `
  --limit 3
```

```powershell
python rag_preprocess\local_retrieval.py query `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite" `
  --q "FB 爆款文案五步法 Hook Body CTA" `
  --category-key creative_copy `
  --limit 3
```

### 分类 key

- `ad_strategy`：投放策略库
- `creative_copy`：素材与文案库
- `tech_execution`：技术落地库
- `risk_playbook`：风控与踩坑库
- `review_cases`：复盘案例库
- `general`：通用知识库

### 说明

这个本地检索层不是最终的向量检索，但它可以先验证：

- chunk 是否切得合理
- 来源引用是否完整
- 常见问题能否命中正确资料
- 哪些表格/页面还需要继续清洗

## 公开资料定向爬取与清洗

`crawl_public_knowledge.py` 会抓取一批公开官方资料，并清洗成中文诊断知识卡后合并进 `output/30tian_chuhai_chunks.jsonl`。

```powershell
python rag_preprocess\crawl_public_knowledge.py

python rag_preprocess\local_retrieval.py build `
  --chunks "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai_chunks.jsonl" `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite"
```

当前第一批公开资料清洗卡：

- 来源：Meta Business Help、TikTok Ads Help、web.dev
- 输出：`output/public_web_cards.jsonl`
- 报告：`output/public_web_crawl_report.json`
- 合并后 chunks：412

注意：这一步不是把网页全文搬进知识库，而是生成“问题 / 场景 / 判断逻辑 / 建议动作 / 风险提醒 / 来源链接”的诊断卡，避免低质量网页内容污染检索结果。

## 本地问答原型

`rag_answer.py` 会先检索 Top K，再输出一个本地草稿答案和引用来源。

```powershell
python rag_preprocess\rag_answer.py `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite" `
  --q "ROI 小于 1 持续两天怎么办" `
  --category-key ad_strategy `
  --limit 3
```

输出示例会包含：

- 基于命中资料的草稿答案
- 引用来源列表

如果要查看可以交给大模型的完整 RAG prompt：

```powershell
python rag_preprocess\rag_answer.py `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite" `
  --q "动态参数路由怎么实现" `
  --category-key tech_execution `
  --limit 3 `
  --show-prompt
```

### 当前设计取舍

- Markdown 里的代码块默认不入库，避免 React/JS 代码污染投放策略问答。
- CSV 数据库按行转成知识片段，适合放量/止损表、素材测试表这类结构化内容。
- `_all.csv` 和“打开查看内容”占位行会被过滤。
- 本地问答只是练手原型；正式版本建议把检索结果交给 DeepSeek 或其他 OpenAI-compatible 网关生成自然语言答案。

## DeepSeek / OpenAI-Compatible 网关

现在已经支持 OpenAI-compatible 的大模型网关，默认按 DeepSeek 配置。

### 环境变量

PowerShell 临时设置：

```powershell
$env:DEEPSEEK_API_KEY="你的 DeepSeek API Key"
```

也可以用通用变量：

```powershell
$env:LLM_API_KEY="你的 API Key"
$env:LLM_BASE_URL="https://api.deepseek.com"
$env:LLM_MODEL="deepseek-chat"
```

默认值：

- `LLM_BASE_URL`: `https://api.deepseek.com`
- `LLM_MODEL`: `deepseek-chat`
- `LLM_TIMEOUT`: `60`
- `LLM_TEMPERATURE`: `0.2`
- `LLM_MAX_TOKENS`: `900`

### 调用 DeepSeek 生成正式回答

```powershell
python rag_preprocess\rag_answer.py `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite" `
  --q "ROI 小于 1 持续两天怎么办" `
  --category-key ad_strategy `
  --limit 3 `
  --llm
```

如果没有设置 API Key，程序不会崩，会提示 LLM 调用失败并回落到本地草稿答案。

### 换其他兼容模型

如果以后要换 Qwen、Kimi、其他 OpenAI-compatible 服务，只需要改：

```powershell
$env:LLM_BASE_URL="你的兼容接口地址"
$env:LLM_MODEL="你的模型名"
$env:LLM_API_KEY="你的 API Key"
```

业务代码不用改。

## 部署成 Web 服务

现在已经有一个可部署的 HTTP 服务：

```text
web_service.py
```

接口：

- `GET /`：网页问答界面
- `GET /health`：健康检查
- `GET /readyz`：就绪检查，会验证 SQLite 和 FTS 表是否可查
- `POST /api/ask`：问答 API

### 本地启动

```powershell
$env:DEEPSEEK_API_KEY="你的 DeepSeek API Key"

python rag_preprocess\web_service.py `
  --host 0.0.0.0 `
  --port 8000 `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite"
```

浏览器打开：

```text
http://localhost:8000
```

### API 调用

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/ask" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"question":"ROI 小于 1 持续两天怎么办","category_key":"ad_strategy","limit":3,"use_llm":true}'
```

### 可选访问密钥

如果部署到公网，建议设置 `APP_API_KEY`：

```powershell
$env:APP_API_KEY="你自己的访问密钥"
```

请求时加 header：

```text
Authorization: Bearer 你自己的访问密钥
```

或者：

```text
X-API-Key: 你自己的访问密钥
```

网页里填写“访问码”后，会自动用 `Authorization: Bearer ...` 调用接口。建议把 `APP_API_KEY` 和 `DEEPSEEK_API_KEY` 分开，不要复用。

### Docker 构建

在 `rag_preprocess` 目录执行：

```powershell
docker build -t chuhai-rag .
```

运行：

```powershell
docker run -p 8000:8000 `
  -e DEEPSEEK_API_KEY="你的 DeepSeek API Key" `
  -e APP_API_KEY="你自己的访问密钥" `
  chuhai-rag
```

镜像启动时会读取 `PORT` 和 `RAG_DB_PATH`，适配 Render、Railway 等会动态注入端口的平台。容器内置健康检查会访问 `/readyz`。

### 服务器部署建议

最简单的公网部署方式：

1. 买一台国内或香港云服务器。
2. 安装 Docker。
3. 上传 `rag_preprocess` 目录。
4. `docker build -t chuhai-rag .`
5. 用 `docker run` 启动。
6. 用 Nginx 反向代理到 `localhost:8000`。
7. 配 HTTPS。

生产环境至少设置：

```text
DEEPSEEK_API_KEY
APP_API_KEY
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
RAG_EVENT_LOG_PATH=output/interaction_events.jsonl
```

不要把 API Key 写进源码、README、Dockerfile 或 JSON 文件。

## 真实问题与反馈收集

Web 服务现在会把每次 `/api/ask` 的提问和命中情况追加写入 JSONL 日志，默认位置：

```text
output/interaction_events.jsonl
```

每条提问事件会记录：

- 用户问题
- 分类、深度、limit
- 回答耗时
- 命中来源数量、来源标题、来源分类
- 回答长度

用户点击 👍 / 👎 时，会通过 `/api/feedback` 追加反馈事件，并用 `request_id` 和对应提问关联。日志不会记录访问码，也不会记录 DeepSeek API Key。

后续每周可以直接分析这个文件，找出：

- 高频真实问法
- 没命中来源的问题
- 点踩较多的回答
- 需要补充的知识卡和口语扩展词

## 检索评测集

`eval_questions.py` 用来检查常见口语化投放问题能否命中正确知识片段。它不调用 DeepSeek，只评测本地 SQLite 检索层。

```powershell
python rag_preprocess\eval_questions.py `
  --db "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\30tian_chuhai.sqlite" `
  --report "C:\Users\kaco_\Desktop\工作流\rag_preprocess\output\eval_report.json" `
  --limit 5
```

当前评测覆盖 39 个高频问题，包括 ROI 低、烧钱不出单、CTR 高 CVR 低、素材疲劳、TikTok Hook、Pixel/CAPI、落地页性能、审核拒登和每日复盘。最近一次本地结果：

- 通过：39 / 39
- 通过率：100%
- 报告：`output/eval_report.json`

## 当前知识库规模

第二批公开资料清洗卡已合并入主知识库。当前规模：

- 总 chunks：446
- Markdown chunks：265
- CSV row chunks：116
- 公开诊断卡：52
- 视频拆解卡：5
- 原始投流经验笔记：8

分类分布：

- 投放策略库：280
- 技术落地库：74
- 风控与踩坑库：44
- 素材与文案库：29
- 复盘案例库：16
- 通用知识库：3
