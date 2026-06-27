import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: int = 60
    temperature: float = 0.2
    max_tokens: int = 900


class LLMGatewayError(RuntimeError):
    pass


def missing_api_key_message() -> str:
    return "Missing API key. Set LLM_API_KEY or DEEPSEEK_API_KEY before using --llm."


def config_from_env() -> LLMConfig:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or ""
    return LLMConfig(
        api_key=api_key,
        base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        model=os.environ.get("LLM_MODEL", DEFAULT_MODEL),
        timeout=int(os.environ.get("LLM_TIMEOUT", "60")),
        temperature=float(os.environ.get("LLM_TEMPERATURE", "0.2")),
        max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "900")),
    )


def chat_completion(prompt: str, config: LLMConfig | None = None) -> str:
    config = config or config_from_env()
    if not config.api_key:
        raise LLMGatewayError(missing_api_key_message())

    base_url = config.base_url.rstrip("/")
    url = f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions"
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise LLMGatewayError(f"LLM HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise LLMGatewayError(f"LLM request failed: {exc}") from exc

    try:
        data = json.loads(body)
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise LLMGatewayError(f"Unexpected LLM response: {body[:500]}") from exc
