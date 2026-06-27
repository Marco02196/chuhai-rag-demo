# Render 部署步骤

当前目录已经准备好 Render Blueprint：

```text
render.yaml
```

## 1. 创建 GitHub 仓库

在 GitHub 新建一个仓库，建议名称：

```text
chuhai-rag-demo
```

仓库可以选 private。不要勾选自动生成 README、.gitignore 或 License，因为本地已经有这些文件。

## 2. 推送本地代码

在本目录执行，把 `<YOUR_REPO_URL>` 换成 GitHub 仓库地址：

```powershell
git remote add origin <YOUR_REPO_URL>
git push -u origin main
```

示例：

```powershell
git remote add origin https://github.com/your-name/chuhai-rag-demo.git
git push -u origin main
```

## 3. 用 Render Blueprint 创建服务

打开：

```text
https://dashboard.render.com/blueprint/new
```

选择刚刚推送的 GitHub 仓库。Render 会自动读取 `render.yaml` 并创建一个 Docker Web Service。

## 4. 填环境变量

Render 会要求填写两个 secret：

```text
DEEPSEEK_API_KEY
APP_API_KEY
```

建议：

- `DEEPSEEK_API_KEY`：填 DeepSeek 控制台拿到的 key。
- `APP_API_KEY`：自己生成一串访问码，发给试点客户。不要和 DeepSeek key 一样。

其余变量已经在 `render.yaml` 里写好：

```text
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
RAG_DB_PATH=/app/output/30tian_chuhai.sqlite
```

## 5. 部署后验证

部署完成后访问：

```text
https://你的-render域名/readyz
```

正常应该返回：

```json
{"ok": true, "chunks": 381, "chunks_fts": 381}
```

然后打开首页：

```text
https://你的-render域名/
```

在页面里填写 `APP_API_KEY` 作为访问码，再提问：

```text
钱一直烧但是不出单咋办？
```

如果能返回答案和引用来源，第一版公网试点就部署成功。
