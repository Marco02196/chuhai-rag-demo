# Northstar Private Pilot Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the deployed Northstar RAG safe and usable for a controlled 3-10 customer pilot without adding multi-tenant product scope.

**Architecture:** Keep the current single-process Python HTTP service and standalone HTML client. Add one authenticated session-verification endpoint, an in-memory per-IP sliding-window limiter, early question-length validation, and narrowly scoped responsive CSS. Preserve the existing SQLite retrieval, DeepSeek gateway, Supabase events, feedback, and admin analytics flows.

**Tech Stack:** Python 3 standard library, `ThreadingHTTPServer`, `unittest`, standalone HTML/CSS/JavaScript, Render, GitHub.

## Global Constraints

- Do not add new runtime dependencies.
- Keep local development unauthenticated when `APP_API_KEY` is empty.
- Accept only the configured `APP_API_KEY`; do not retain a hardcoded legacy code.
- Limit authenticated/public POST traffic to 12 requests per client IP per 60 seconds.
- Reject questions longer than 1000 characters before retrieval or LLM work.
- Preserve the desktop visual direction and all existing RAG/Supabase behavior.
- Do not add accounts, billing, multi-tenancy, a simulated dashboard, or distributed rate limiting.

## File Map

- Modify `web_service.py`: authentication, session verification, rate limiter, question validation, response headers.
- Modify `web_app.html`: real gate verification, URL cleanup, rate-limit/validation errors, mobile layout.
- Modify `test_web_service.py`: unit and HTML contract coverage for every new behavior.
- No database, Supabase schema, model gateway, or Render environment-variable changes are required.

---

### Task 1: Remove the Legacy Access Code and Add Real Session Verification

**Files:**
- Modify: `test_web_service.py:1-115`
- Modify: `web_service.py:1090-1130, 1240-1345`
- Modify: `web_app.html:1-10, 629-710`

**Interfaces:**
- Produces: `POST /api/session/verify` returning `{"ok": true}` for a valid bearer token.
- Produces: `check_auth(headers: dict[str, str], expected_api_key: str | None) -> bool` with no legacy-code fallback.
- Consumes: existing `Authorization: Bearer <code>` convention.

- [ ] **Step 1: Write failing authentication and HTML contract tests**

Add these tests to `WebServiceTest`:

```python
def test_check_auth_rejects_hardcoded_legacy_code_when_config_changes(self):
    headers = {"authorization": "Bearer fb300"}

    self.assertFalse(check_auth(headers, expected_api_key="new-secret"))

def test_render_app_html_verifies_session_and_scrubs_code_from_url(self):
    html = render_app_html()

    self.assertIn("VERIFY:'/api/session/verify'", html)
    self.assertIn("history.replaceState", html)
    self.assertIn('name="referrer" content="no-referrer"', html)
```

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```powershell
python -m unittest test_web_service.WebServiceTest.test_check_auth_rejects_hardcoded_legacy_code_when_config_changes test_web_service.WebServiceTest.test_render_app_html_verifies_session_and_scrubs_code_from_url
```

Expected: the legacy-code test fails because `fb300` is still allowed, and the HTML contract test fails because the verification endpoint and URL scrubbing are absent.

- [ ] **Step 3: Restrict `check_auth` to the configured key**

Replace the allow-list logic with:

```python
def check_auth(headers: dict[str, str], expected_api_key: str | None) -> bool:
    expected_api_key = (expected_api_key or "").strip()
    if not expected_api_key:
        return True
    authorization = headers.get("authorization", "").strip()
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip() == expected_api_key
    return headers.get("x-api-key", "").strip() == expected_api_key
```

- [ ] **Step 4: Add the authenticated verification route**

Include `/api/session/verify` in the POST route set. After authentication and before reading a body, return:

```python
if path == "/api/session/verify":
    self.send_json({"ok": True})
    return
```

This endpoint must use the same `check_auth` call as `/api/ask` and must not invoke retrieval, the LLM, logging, or Supabase.

- [ ] **Step 5: Make the gate verify against the server**

Extend the client configuration and replace the fake delay in `verify`:

```javascript
const CFG={VERIFY:'/api/session/verify',QUERY:'/api/ask',FEEDBACK:'/api/feedback',COLD_MS:3000,TIMEOUT_MS:60000};

const response=await fetch(CFG.VERIFY,{
  method:'POST',
  headers:{'Authorization':'Bearer '+v}
});
if(!response.ok){
  throw new Error(response.status===429
    ? '尝试次数过多，请稍后再试'
    : '访问码不正确，请重新输入');
}
S.token=v;
sessionStorage.setItem('access_code',S.token);
```

Add `<meta name="referrer" content="no-referrer"/>`. When loading a `code` query parameter, capture it and immediately remove it before verification:

```javascript
const url=new URL(location.href);
const p=url.searchParams.get('code');
if(p){
  url.searchParams.delete('code');
  history.replaceState(null,'',url.pathname+(url.search?'?'+url.searchParams.toString():'')+url.hash);
}
```

- [ ] **Step 6: Run authentication tests**

Run:

```powershell
python -m unittest test_web_service.WebServiceTest.test_check_auth_allows_requests_when_no_api_key_configured test_web_service.WebServiceTest.test_check_auth_accepts_bearer_token test_web_service.WebServiceTest.test_check_auth_accepts_x_api_key test_web_service.WebServiceTest.test_check_auth_rejects_wrong_key test_web_service.WebServiceTest.test_check_auth_rejects_hardcoded_legacy_code_when_config_changes test_web_service.WebServiceTest.test_render_app_html_verifies_session_and_scrubs_code_from_url
```

Expected: 6 tests pass.

---

### Task 2: Add Question Validation and Per-IP Rate Limiting

**Files:**
- Modify: `test_web_service.py:1-250`
- Modify: `web_service.py:1-20, 1190-1360`
- Modify: `web_app.html:850-900`

**Interfaces:**
- Produces: `SlidingWindowRateLimiter.allow(key: str) -> tuple[bool, int]` where the integer is retry seconds.
- Produces: `request_client_ip(handler: BaseHTTPRequestHandler) -> str` using the first `X-Forwarded-For` address, then `client_address[0]`.
- Produces: `send_json(..., headers: dict[str, str] | None = None)` for `Retry-After`.
- Consumes: server attribute `rate_limiter` initialized in `run_server`.

- [ ] **Step 1: Write failing question-length and limiter tests**

Import `SlidingWindowRateLimiter` and add:

```python
def test_handle_ask_payload_rejects_question_over_1000_chars_before_retrieval(self):
    def unexpected_retriever(**kwargs):
        raise AssertionError("retriever must not run")

    response, status = handle_ask_payload(
        {"question": "问" * 1001},
        db_path="unused.sqlite",
        retriever=unexpected_retriever,
        answerer=lambda *args, **kwargs: "unused",
    )

    self.assertEqual(status, 400)
    self.assertIn("1000", response["error"])

def test_sliding_window_rate_limiter_blocks_thirteenth_request(self):
    now = [100.0]
    limiter = SlidingWindowRateLimiter(limit=12, window_seconds=60, clock=lambda: now[0])

    for _ in range(12):
        self.assertEqual(limiter.allow("client-a"), (True, 0))
    allowed, retry_after = limiter.allow("client-a")

    self.assertFalse(allowed)
    self.assertEqual(retry_after, 60)

def test_sliding_window_rate_limiter_recovers_after_window(self):
    now = [100.0]
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    self.assertEqual(limiter.allow("client-a"), (True, 0))

    now[0] = 160.1

    self.assertEqual(limiter.allow("client-a"), (True, 0))
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run:

```powershell
python -m unittest test_web_service.WebServiceTest.test_handle_ask_payload_rejects_question_over_1000_chars_before_retrieval test_web_service.WebServiceTest.test_sliding_window_rate_limiter_blocks_thirteenth_request test_web_service.WebServiceTest.test_sliding_window_rate_limiter_recovers_after_window
```

Expected: import or assertion failures because validation and the limiter do not exist.

- [ ] **Step 3: Implement early question validation**

Define `MAX_QUESTION_LENGTH = 1000` near the other constants, then add immediately after the empty-question check:

```python
if len(question) > MAX_QUESTION_LENGTH:
    return {"error": f"question must be at most {MAX_QUESTION_LENGTH} characters"}, 400
```

- [ ] **Step 4: Implement the thread-safe sliding-window limiter**

Add `from math import ceil` and:

```python
class SlidingWindowRateLimiter:
    def __init__(self, limit: int = 12, window_seconds: int = 60, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self._events: dict[str, list[float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            events = [timestamp for timestamp in self._events.get(key, []) if timestamp > cutoff]
            if len(events) >= self.limit:
                self._events[key] = events
                return False, max(1, ceil(self.window_seconds - (now - events[0])))
            events.append(now)
            self._events[key] = events
            return True, 0
```

- [ ] **Step 5: Apply the limiter to protected POST routes**

Initialize `server.rate_limiter = SlidingWindowRateLimiter()` in `run_server`. Resolve the client key from the first forwarded IP when present. Before authentication in `do_POST`, call `allow`; on rejection return:

```python
self.send_json(
    {"error": "too many requests"},
    status=429,
    headers={"Retry-After": str(retry_after)},
)
```

Extend `send_json` with an optional `headers` argument and emit those headers before `end_headers()`.

- [ ] **Step 6: Preserve retryable questions in the client**

When `/api/ask` returns 400 or 429, attach the HTTP status to the thrown error. In the catch block restore `text` into the textarea and display:

```javascript
const msg=e.status===429
  ? '请求过于频繁，请稍后再试。'
  : e.status===400
    ? (e.message||'问题内容不符合要求，请检查后重试。')
    : e.name==='AbortError'
      ? '等待超时，知识库或模型可能正在冷启动，请稍后重试。'
      : (e.message||'网络错误');
```

- [ ] **Step 7: Run limiter and full unit tests**

Run:

```powershell
python -m unittest discover -s . -p "test_*.py"
```

Expected: all existing tests plus the 3 new tests pass.

---

### Task 3: Fix Mobile Overflow Without Redesigning Desktop

**Files:**
- Modify: `test_web_service.py:70-115`
- Modify: `web_app.html:35-490`

**Interfaces:**
- Produces: a layout that remains within `document.documentElement.clientWidth` at 390px, 768px, and 1440px.
- Consumes: existing `.shell`, `.hdr`, `.empty`, `.quick-chips`, `.composer`, and drawer markup.

- [ ] **Step 1: Add an HTML contract test for mobile guards**

Add:

```python
def test_render_app_html_includes_mobile_overflow_guards(self):
    html = render_app_html()

    self.assertIn("overflow-x:hidden", html)
    self.assertIn("min-width:0", html)
    self.assertIn("safe-area-inset-bottom", html)
    self.assertIn("@media(max-width:560px)", html.replace(" ", ""))
```

- [ ] **Step 2: Run the contract test and confirm failure**

Run:

```powershell
python -m unittest test_web_service.WebServiceTest.test_render_app_html_includes_mobile_overflow_guards
```

Expected: failure because the mobile containment rules are absent.

- [ ] **Step 3: Add containment and wrapping rules**

Add these base rules while preserving existing colors and typography:

```css
html,body{height:100%;width:100%;overflow-x:hidden;}
.shell{width:100%;min-width:0;}
.hdr,.hdr-right,.chat-area,.empty,.quick-chips,.composer,.composer-box,.composer-footer{min-width:0;max-width:100%;}
.empty-sub,.bubble-user,.ai-text,.src-text{overflow-wrap:anywhere;}
.quick-chips{width:100%;}
```

Add a single responsive block:

```css
@media(max-width:560px){
  .shell{padding:0 14px;}
  .hdr{padding:14px 0 10px;gap:8px;}
  .hdr .logo{font-size:17px;}
  .hdr-right{gap:6px;}
  .sess-pill{padding:6px 10px;}
  .empty{min-height:50vh;gap:12px;padding:8px 0;}
  .empty-title{font-size:28px;}
  .empty-sub{font-size:11.5px;letter-spacing:0;}
  .quick-chips{gap:7px;margin-top:8px;}
  .qchip{padding:7px 12px;font-size:12px;}
  .msg{margin-bottom:22px;}
  .msg-ai{gap:10px;}
  .bubble-user{max-width:88%;padding:10px 14px;}
  .composer{padding:6px 0 calc(12px + env(safe-area-inset-bottom));}
  .composer-box{padding:13px 13px 10px;}
  .composer-footer{gap:8px;}
  .composer-left{min-width:0;gap:5px;}
  .hint-chip{padding:5px 9px;font-size:10.5px;}
  .send-btn{padding:9px 16px;}
  .drawer{width:min(300px,92vw);}
}
```

- [ ] **Step 4: Run the mobile contract and full tests**

Run:

```powershell
python -m unittest discover -s . -p "test_*.py"
```

Expected: all tests pass.

- [ ] **Step 5: Verify responsive screenshots and DOM width**

Start the local service with `APP_API_KEY=fb300`, then verify:

```javascript
document.documentElement.scrollWidth === document.documentElement.clientWidth
```

at 390x844, 768x1024, and 1440x1000. Capture desktop and mobile screenshots. Confirm the logo, verification status, quick questions, composer, and send button are fully visible.

---

### Task 4: Regression, Deployment, and Production Verification

**Files:**
- Verify: `web_service.py`
- Verify: `web_app.html`
- Verify: `test_web_service.py`
- No modifications expected unless verification exposes a defect.

**Interfaces:**
- Consumes: GitHub repository `Marco02196/chuhai-rag-demo` and Render auto-deploy.
- Produces: verified production endpoints `/readyz`, `/app`, `/api/session/verify`, and `/api/ask`.

- [ ] **Step 1: Run static and unit verification**

Run:

```powershell
python -m py_compile web_service.py
python -m unittest discover -s . -p "test_*.py"
git diff --check -- web_service.py web_app.html test_web_service.py
```

Expected: compilation succeeds, all tests pass, and diff check emits no errors.

- [ ] **Step 2: Review only the scoped diff**

Run:

```powershell
git diff -- web_service.py web_app.html test_web_service.py
```

Confirm the diff contains only access verification, limiter/validation, retry handling, and mobile containment. Preserve unrelated existing working-tree changes.

- [ ] **Step 3: Publish the three verified files**

Update `web_service.py`, `web_app.html`, and `test_web_service.py` in `Marco02196/chuhai-rag-demo` on `main` using their current GitHub content SHAs so existing remote work is not overwritten. Use commit message `feat: harden private pilot experience`.

- [ ] **Step 4: Wait for Render and verify health**

Poll `https://chuhai-rag-demo.onrender.com/readyz` until it returns HTTP 200 and `chunks: 515`. Do not print or expose any DeepSeek key.

- [ ] **Step 5: Verify production authentication and RAG**

Confirm:

- `POST /api/session/verify` with the configured pilot code returns 200.
- The same endpoint with a wrong code returns 401.
- `/app?code=<pilot-code>` removes the code from the address bar after load.
- A benign real question returns an answer and at least one source.
- A 1001-character question returns 400.
- The mobile production screenshot has no horizontal overflow.

- [ ] **Step 6: Hand off for customer approval**

Provide the customer URL and report: deployment status, unit-test count, desktop/mobile verification, authentication behavior, request duration, and any remaining limitation. State clearly that this is a controlled private pilot, not a multi-tenant paid product.
