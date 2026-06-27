FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV RAG_DB_PATH=/app/output/30tian_chuhai.sqlite
ENV LLM_BASE_URL=https://api.deepseek.com
ENV LLM_MODEL=deepseek-chat

WORKDIR /app

COPY . /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/readyz', timeout=3)"

CMD python web_service.py --host 0.0.0.0 --port "$PORT" --db "$RAG_DB_PATH"
