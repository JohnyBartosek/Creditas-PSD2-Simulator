"""Open Kibana in a browser and follow X-Request-ID to X-B3-SpanId."""

from __future__ import annotations

import contextvars
import json
import re
import threading
from pathlib import Path

from Helpers.environment_config import PROJECT_ROOT, get_kibana_settings
from psd2_app.logic import kibana_request_kql, kibana_request_url, kibana_spans_kql, kibana_spans_url

_SPAN_RE = re.compile(
    r"X-B3-SpanId[\"'\s]*[:=]\s*\"?\[?\s*([0-9a-fA-F]{16})",
    re.IGNORECASE,
)
_COMPONENT_RE = re.compile(
    r"(?:In|Out)(?:Request|Response)\s+([A-Za-z][A-Za-z0-9_.-]*)",
)
_UPSTREAM_RE = re.compile(r'"(?:proxyUpstreamName|upstream)"\s*:\s*"([^"]+)"')
_PROFILE = PROJECT_ROOT / ".kibana-profile"
_LOCK = threading.Lock()
_STEP_SINK = contextvars.ContextVar("kibana_step_sink", default=None)


def _step(message: str) -> None:
    print(f"[Kibana] {message}", flush=True)
    sink = _STEP_SINK.get()
    if sink is None:
        return
    try:
        sink(message)
    except Exception:
        return

_SEARCH_JS = """
async ({ dataViewId, kql, size }) => {
  const headers = { "kbn-xsrf": "true", "content-type": "application/json" };
  let viewResponse = await fetch(`/api/data_views/data_view/${dataViewId}`, {
    headers: { ...headers, "elastic-api-version": "2023-10-31" },
  });
  if (!viewResponse.ok) {
    viewResponse = await fetch(`/api/data_views/data_view/${dataViewId}`, { headers });
  }
  const viewText = await viewResponse.text();
  if (!viewResponse.ok) {
    return { ok: false, status: viewResponse.status, body: viewText.slice(0, 500) };
  }
  const view = JSON.parse(viewText);
  const index = view.data_view && view.data_view.title;
  if (!index) {
    return { ok: false, status: viewResponse.status, body: "Data view has no title." };
  }
  const params = {
    index,
    body: {
      size: size || 500,
      query: { query_string: { query: kql } },
      sort: [{ "@timestamp": "desc" }],
      fields: ["message", "@timestamp"],
      _source: ["message", "@timestamp"],
    },
  };
  let payload = null;
  for (let attempt = 0; attempt < 8; attempt++) {
    const url = payload && payload.id
      ? `/internal/search/ese/${payload.id}`
      : "/internal/search/ese";
    const searchBody = JSON.stringify({ params });
    let response = await fetch(url, {
      method: "POST",
      headers: { ...headers, "elastic-api-version": "2023-10-31" },
      body: searchBody,
    });
    if (!response.ok) {
      response = await fetch(url, { method: "POST", headers, body: searchBody });
    }
    const text = await response.text();
    if (!response.ok) {
      return { ok: false, status: response.status, body: text.slice(0, 500) };
    }
    payload = JSON.parse(text);
    if (!payload.isRunning) {
      return { ok: true, body: text };
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  return { ok: true, body: JSON.stringify(payload || {}) };
}
"""


def _merge_span_ids(current: list[str], extra: list[str]) -> list[str]:
    merged = list(current)
    for span_id in extra:
        if span_id not in merged:
            merged.append(span_id)
    return merged


def span_ids_in_text(text: str) -> list[str]:
    found = []
    for match in _SPAN_RE.finditer(text or ""):
        span_id = match.group(1).lower()
        if span_id not in found:
            found.append(span_id)
    return found


def _strings(value, found: list[str]) -> None:
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _strings(item, found)
    elif isinstance(value, list):
        for item in value:
            _strings(item, found)


def span_ids_in_payload(payload: str) -> list[str]:
    texts = []
    try:
        _strings(json.loads(payload), texts)
    except json.JSONDecodeError:
        texts.append(payload or "")
    found = []
    for text in texts:
        for span_id in span_ids_in_text(text):
            if span_id not in found:
                found.append(span_id)
    return found


def _first_text(value) -> str:
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return ""
    if isinstance(value, str):
        return value.strip()
    return ""


def _nested_text(data: dict, path: tuple[str, ...]) -> str:
    current = data
    for part in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(part)
    return _first_text(current)


def component_from_message(message: str) -> str:
    """Name of the API or service that wrote the line."""
    match = _COMPONENT_RE.search(message or "")
    if match:
        return match.group(1)
    upstream = _UPSTREAM_RE.search(message or "")
    if upstream:
        return upstream.group(1)
    return ""


def component_from_hit(hit: dict, message: str) -> str:
    named = component_from_message(message)
    if named:
        return named
    fields = hit.get("fields") if isinstance(hit.get("fields"), dict) else {}
    source = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
    for key in ("service.name", "service", "component", "logger", "activityName"):
        text = _first_text(fields.get(key)) or _first_text(source.get(key))
        if text:
            return text
    for container in (fields, source):
        text = _nested_text(container, ("kubernetes", "container", "name"))
        if text:
            return text
    return ""


def _hit_message(hit: dict) -> str:
    source = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
    if source.get("message"):
        return str(source["message"])
    fields = hit.get("fields") if isinstance(hit.get("fields"), dict) else {}
    message = fields.get("message")
    if isinstance(message, list):
        return "\n".join(str(item) for item in message if item)
    if isinstance(message, str):
        return message
    return ""


def _hit_timestamp(hit: dict) -> str:
    fields = hit.get("fields") if isinstance(hit.get("fields"), dict) else {}
    source = hit.get("_source") if isinstance(hit.get("_source"), dict) else {}
    for container in (fields, source):
        for key in ("@timestamp", "timestamp"):
            value = container.get(key)
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str) and value:
                return value
    return ""


def documents_from_payload(payload: str) -> list[dict[str, str]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    found = []

    def walk(value) -> None:
        if isinstance(value, dict):
            hits = value.get("hits")
            rows = hits.get("hits") if isinstance(hits, dict) else None
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    message = _hit_message(row)
                    if not message:
                        continue
                    found.append({
                        "timestamp": _hit_timestamp(row),
                        "message": message,
                        "component": component_from_hit(row, message),
                    })
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    unique = []
    seen = set()
    for item in found:
        key = (item["timestamp"], item["message"])
        if key in seen:
            continue
        seen.add(key)
        preview = " ".join(item["message"].split())
        unique.append({
            "timestamp": item["timestamp"],
            "message": item["message"],
            "preview": preview[:180],
            "component": item.get("component") or "",
        })
    unique.sort(key=lambda item: item["timestamp"])
    return unique


def _page_span_ids(page) -> list[str]:
    try:
        text = page.locator("body").inner_text(timeout=5000)
    except Exception:
        return []
    return span_ids_in_text(text)


def _launch_browser(playwright, *, headless: bool):
    args = [] if headless else ["--start-minimized", "--window-position=-32000,-32000"]
    return playwright.chromium.launch_persistent_context(
        str(_PROFILE),
        headless=headless,
        ignore_https_errors=True,
        viewport={"width": 1400, "height": 900},
        args=args,
    )


def _hide_window(context, page) -> None:
    try:
        session = context.new_cdp_session(page)
        window_id = session.send("Browser.getWindowForTarget")["windowId"]
        session.send(
            "Browser.setWindowBounds",
            {"windowId": window_id, "bounds": {"windowState": "minimized"}},
        )
    except Exception:
        return


def _needs_login(page) -> bool:
    if "/app/discover" in (page.url or ""):
        return False
    try:
        text = page.locator("body").inner_text(timeout=3000)
    except Exception:
        text = ""
    lowered = text.lower()
    return (
        "/login" in (page.url or "").lower()
        or "welcome to elastic" in lowered
        or "log in with" in lowered
    )


def _wait_until_login_or_discover(page) -> None:
    page.wait_for_function(
        """() => {
            const url = location.href;
            const text = document.body ? document.body.innerText : "";
            return url.includes("/app/discover")
                || url.includes("/login")
                || text.includes("Welcome to Elastic")
                || text.includes("Log in with");
        }""",
        timeout=30000,
    )


def _choose_azure(page) -> None:
    locator = page.get_by_text(re.compile(r"Log in with Azure", re.I))
    try:
        locator.first.wait_for(state="visible", timeout=5000)
    except Exception:
        return
    locator.first.click()


def _show_window(context, page) -> None:
    try:
        session = context.new_cdp_session(page)
        window_id = session.send("Browser.getWindowForTarget")["windowId"]
        session.send(
            "Browser.setWindowBounds",
            {
                "windowId": window_id,
                "bounds": {
                    "left": 120,
                    "top": 80,
                    "width": 1280,
                    "height": 860,
                    "windowState": "normal",
                },
            },
        )
    except Exception:
        return


def _interactive_login(page) -> bool:
    url = (page.url or "").lower()
    return any(
        part in url
        for part in (
            "login.microsoftonline.com",
            "login.microsoft.com",
            "login.windows.net",
        )
    )


def _open_discover(playwright, request_url):
    """Stay headless through the Azure choice. Show a window only for the IdP login."""
    _step("Opening Kibana in the background")
    context = _launch_browser(playwright, headless=True)
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(request_url, wait_until="domcontentloaded", timeout=60000)
    try:
        _wait_until_login_or_discover(page)
    except Exception:
        pass
    if _needs_login(page):
        _step("Sign-in page detected, choosing Azure AD")
        _choose_azure(page)
        try:
            page.wait_for_url("**/app/discover**", timeout=20000)
        except Exception:
            pass
    if "/app/discover" in (page.url or ""):
        _step("Discover opened with the saved session")
        return context, page
    _step("Saved session is not enough, opening the sign-in window")
    context.close()
    context = _launch_browser(playwright, headless=False)
    page = context.pages[0] if context.pages else context.new_page()
    _hide_window(context, page)
    page.goto(request_url, wait_until="domcontentloaded", timeout=60000)
    _choose_azure(page)
    sign_in_shown = False
    for _ in range(90):
        if "/app/discover" in (page.url or ""):
            break
        if _interactive_login(page) and not sign_in_shown:
            _step("Waiting for Microsoft sign-in")
            _show_window(context, page)
            sign_in_shown = True
        page.wait_for_timeout(1000)
    else:
        page.wait_for_url("**/app/discover**", timeout=1000)
    _step("Discover opened, hiding the browser")
    _hide_window(context, page)
    return context, page


def _run_locked(func, *args, on_step=None) -> dict:
    token = _STEP_SINK.set(on_step)
    if not _LOCK.acquire(blocking=False):
        _step("Another Kibana trace is already running")
        _STEP_SINK.reset(token)
        return {"ok": False, "message": "Kibana is already open. Close that window before starting another trace."}
    try:
        return func(*args)
    finally:
        _LOCK.release()
        _STEP_SINK.reset(token)


def trace_request_in_kibana(request_id: str, on_step=None) -> dict:
    """Open Discover for the request id, then move the same window to its span id."""
    return _run_locked(_trace_request, request_id, on_step=on_step)


def trace_span_in_kibana(span_id: str, on_step=None) -> dict:
    """Download the X-B3-SpanId logs without searching for a request id first."""
    return _run_locked(_trace_span, span_id, on_step=on_step)


def _trace_request(request_id: str) -> dict:
    _step(f"Searching for {request_id}")
    request_url = kibana_request_url(request_id)
    if not request_url:
        _step("Kibana URL is not configured for this environment")
        return {"ok": False, "message": "Kibana URL is not configured for this environment."}
    settings = get_kibana_settings()
    data_view = settings["data_view"]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _step("Playwright is not installed")
        return {"ok": False, "message": "Playwright is not installed."}

    _PROFILE.mkdir(parents=True, exist_ok=True)
    span_ids = []
    documents = []
    wider_trace = False
    try:
        with sync_playwright() as playwright:
            context, page = _open_discover(playwright, request_url)
            captured = []

            def remember(response):
                if response.status != 200:
                    return
                if "/internal/search" in response.url or "/internal/bsearch" in response.url:
                    captured.append(response)

            page.on("response", remember)
            _step("Loading records that contain the request id")
            page.goto(request_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_url("**/app/discover**", timeout=180000)
            page.wait_for_timeout(2500)
            request_documents = []
            for response in captured:
                try:
                    body = response.text()
                except Exception:
                    continue
                span_ids = _merge_span_ids(span_ids, span_ids_in_payload(body))
                request_documents = _prefer_documents(request_documents, documents_from_payload(body))
            _step(
                f"Request search returned {len(request_documents)} record(s)"
                + (f", span {', '.join(span_ids)}" if span_ids else "")
            )
            if not span_ids:
                _step("Span id was not in that response, querying Elasticsearch")
                span_ids = _span_ids_from_kibana(page, data_view, request_id)
            if not span_ids:
                _step("Reading the Discover page for a span id")
                span_ids = _page_span_ids(page)
            if span_ids:
                _step(f"Found X-B3-SpanId {', '.join(span_ids)}")
                documents = _download_span_logs(page, captured, data_view, span_ids)
                wider_trace = bool(documents)
                if not documents:
                    _step("Wider trace is empty, keeping records that already contain the span")
                    documents = [
                        item for item in request_documents
                        if any(span_id in item["message"].lower() for span_id in span_ids)
                    ]
                    _step(f"Kept {len(documents)} record(s) from the request search")
            _step("Closing the browser")
            context.close()
    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__
        if "Timeout" in message and "discover" in message.lower():
            _step("Kibana did not open")
            return {"ok": False, "message": "Kibana did not open. Sign in in the browser window and try again.", "logs": []}
        _step(f"Trace failed: {message[:240]}")
        return {"ok": False, "message": f"Kibana trace failed. {message[:240]}", "logs": []}

    if not span_ids:
        _step("No X-B3-SpanId was found")
        return {
            "ok": False,
            "message": "No X-B3-SpanId was found in the X-Request-ID records.",
            "logs": [],
        }
    shown = ", ".join(span_ids)
    if not documents:
        _step(f"Span {shown} is indexed, but its records were not downloaded")
        return {
            "ok": False,
            "message": (
                f"Span {shown} is already in Elasticsearch, but the wider trace is not downloaded yet. "
                "The other services are often still waiting on Filebeat."
            ),
            "span_ids": span_ids,
            "logs": [],
        }
    if wider_trace:
        message = f"Downloaded {len(documents)} log record(s) for X-B3-SpanId {shown}."
    else:
        message = (
            f"Downloaded {len(documents)} record(s) that already contain span {shown}. "
            "The rest of the trace is not in Elasticsearch yet."
        )
    _step(message)
    return {
        "ok": True,
        "message": message,
        "span_ids": span_ids,
        "logs": documents,
    }


def _trace_span(span_id: str) -> dict:
    span_id = (span_id or "").strip()
    _step(f"Searching for X-B3-SpanId {span_id}")
    span_url = kibana_spans_url([span_id])
    if not span_url:
        _step("Kibana URL is not configured for this environment")
        return {"ok": False, "message": "Kibana URL is not configured for this environment."}
    settings = get_kibana_settings()
    data_view = settings["data_view"]
    discover_url = settings["discover_url"].split("#", 1)[0].strip()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _step("Playwright is not installed")
        return {"ok": False, "message": "Playwright is not installed."}

    _PROFILE.mkdir(parents=True, exist_ok=True)
    documents = []
    try:
        with sync_playwright() as playwright:
            context, page = _open_discover(playwright, discover_url or span_url)
            captured = []

            def remember(response):
                if response.status != 200:
                    return
                if "/internal/search" in response.url or "/internal/bsearch" in response.url:
                    captured.append(response)

            page.on("response", remember)
            documents = _download_span_logs(page, captured, data_view, [span_id])
            _step("Closing the browser")
            context.close()
    except Exception as exc:
        message = str(exc).strip() or exc.__class__.__name__
        if "Timeout" in message and "discover" in message.lower():
            _step("Kibana did not open")
            return {"ok": False, "message": "Kibana did not open. Sign in in the browser window and try again.", "logs": []}
        _step(f"Trace failed: {message[:240]}")
        return {"ok": False, "message": f"Kibana trace failed. {message[:240]}", "logs": []}

    if not documents:
        _step(f"No records found for span {span_id}")
        return {
            "ok": False,
            "message": (
                f"No log records were found for X-B3-SpanId {span_id}. "
                "They are often still waiting on Filebeat."
            ),
            "span_ids": [span_id],
            "logs": [],
        }
    message = f"Downloaded {len(documents)} log record(s) for X-B3-SpanId {span_id}."
    _step(message)
    return {
        "ok": True,
        "message": message,
        "span_ids": [span_id],
        "logs": documents,
    }


def _prefer_documents(current: list[dict[str, str]], extra: list[dict[str, str]]) -> list[dict[str, str]]:
    if len(extra) > len(current):
        return extra
    return current


def _merge_documents(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    unique = []
    seen = set()
    for group in groups:
        for item in group:
            key = (item.get("timestamp", ""), item.get("message", ""))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
    unique.sort(key=lambda item: item.get("timestamp", ""))
    return unique


def _with_span(documents: list[dict[str, str]], span_ids: list[str]) -> list[dict[str, str]]:
    needles = [span_id.lower() for span_id in span_ids if span_id]
    return [
        item for item in documents
        if any(span_id in (item.get("message") or "").lower() for span_id in needles)
    ]


def _download_span_logs(page, captured, data_view: str, span_ids: list[str]) -> list[dict[str, str]]:
    documents = []
    for attempt in range(3):
        _step(f"Downloading span logs, attempt {attempt + 1} of 3")
        captured.clear()
        page.goto(kibana_spans_url(span_ids), wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000 if attempt == 0 else 4000)
        page_documents = _with_span(_documents_from_responses(captured), span_ids)
        api_documents = []
        for span_id in span_ids:
            found = _documents_from_kibana(page, data_view, _span_kql([span_id]))
            if not found:
                found = _documents_from_kibana(page, data_view, _span_message_kql([span_id]))
            api_documents = _merge_documents(api_documents, _with_span(found, [span_id]))
        documents = _merge_documents(page_documents, api_documents)
        _step(
            f"Kept {len(documents)} record(s) for {len(span_ids)} span id(s). "
            f"Discover {len(page_documents)}, Elasticsearch {len(api_documents)}."
        )
        if documents:
            return documents
    return documents


def _span_kql(span_ids: list[str]) -> str:
    return kibana_spans_kql(span_ids)


def _span_message_kql(span_ids: list[str]) -> str:
    clauses = []
    for span_id in span_ids:
        span_id = (span_id or "").strip().replace("\\", "\\\\").replace('"', '\\"')
        if span_id:
            clauses.append(f'message: "*{span_id}*"')
    return " or ".join(clauses)


def _documents_from_responses(responses) -> list[dict[str, str]]:
    merged = []
    for response in responses:
        try:
            merged = _merge_documents(merged, documents_from_payload(response.text()))
        except Exception:
            continue
    return merged


def _search_body(page, data_view: str, kql: str) -> str:
    if not data_view or not kql:
        return ""
    try:
        result = page.evaluate(
            _SEARCH_JS,
            {"dataViewId": data_view, "kql": kql, "size": 500},
        )
    except Exception as exc:
        _step(f"Elasticsearch query failed: {exc}")
        return ""
    if not isinstance(result, dict) or not result.get("ok"):
        status = result.get("status") if isinstance(result, dict) else ""
        _step(f"Elasticsearch query failed{f' ({status})' if status else ''}")
        return ""
    return str(result.get("body") or "")


def _documents_from_kibana(page, data_view: str, kql: str) -> list[dict[str, str]]:
    return documents_from_payload(_search_body(page, data_view, kql))


def _span_ids_from_kibana(page, data_view: str, request_id: str) -> list[str]:
    return span_ids_in_payload(_search_body(page, data_view, kibana_request_kql(request_id)))
