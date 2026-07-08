import json
import os
import urllib.error
import urllib.request
from typing import Any


ASK_TABLE = "interaction_events"
FEEDBACK_TABLE = "feedback_events"
DEFAULT_SUPABASE_URL = "https://dxzptxgykrvciihixdbj.supabase.co"
DEFAULT_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_pBtiO73Xaa_oouH5W5lwsA_U3X2xvhw"


def truncate_value(value: Any, max_length: int = 2000) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


class SupabaseEventClient:
    def __init__(self, url: str, api_key: str, timeout_seconds: float = 8.0) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "SupabaseEventClient | None":
        url = os.environ.get("SUPABASE_URL", "").strip() or DEFAULT_SUPABASE_URL
        api_key = (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.environ.get("SUPABASE_ANON_KEY", "").strip()
            or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
            or DEFAULT_SUPABASE_PUBLISHABLE_KEY
        )
        if not url or not api_key:
            return None
        timeout = float(os.environ.get("SUPABASE_EVENT_TIMEOUT_SECONDS", "8") or "8")
        return cls(url=url, api_key=api_key, timeout_seconds=timeout)

    def record_event(self, event: dict) -> None:
        table, payload = supabase_payload_for_event(event)
        if not table:
            return
        self.insert(table, payload)

    def fetch_admin_analytics(self, limit: int = 20) -> dict:
        safe_limit = max(1, min(int(limit or 20), 50))
        body = json.dumps({"p_limit": safe_limit}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/rest/v1/rpc/northstar_admin_analytics",
            data=body,
            method="POST",
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8") or "{}")

    def insert(self, table: str, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}/rest/v1/{table}",
            data=body,
            method="POST",
            headers={
                "apikey": self.api_key,
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "Prefer": "return=minimal",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds):
            return


def supabase_payload_for_event(event: dict) -> tuple[str | None, dict]:
    event_type = str(event.get("event") or "").strip().lower()
    if event_type == "ask":
        return ASK_TABLE, {
            "request_id": truncate_value(event.get("request_id"), 120),
            "question": truncate_value(event.get("question")),
            "category_key": truncate_value(event.get("category_key"), 80) or None,
            "depth": truncate_value(event.get("depth"), 40) or None,
            "retrieval_limit": event.get("limit"),
            "use_llm": event.get("use_llm"),
            "elapsed_ms": event.get("elapsed_ms"),
            "answer_length": event.get("answer_length"),
            "source_count": event.get("source_count"),
            "source_titles": event.get("source_titles") or [],
            "source_categories": event.get("source_categories") or [],
            "created_at": event.get("created_at"),
        }
    if event_type == "feedback":
        return FEEDBACK_TABLE, {
            "request_id": truncate_value(event.get("request_id"), 120),
            "feedback": truncate_value(event.get("feedback"), 20),
            "answer_preview": truncate_value(event.get("answer_preview"), 240),
            "created_at": event.get("created_at"),
        }
    return None, {}


def record_supabase_event(event_sink: Any, event: dict) -> None:
    if not event_sink:
        return
    try:
        event_sink.record_event(event)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        print(f"supabase_event_error type={type(exc).__name__}", flush=True)
