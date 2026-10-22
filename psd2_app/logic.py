"""Pure helpers shared by the Reflex UI."""

from __future__ import annotations

import asyncio
import base64
import json
import re
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_REQUEST_ID_RE = re.compile(
    r"X-Request-ID:\s*([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
    re.IGNORECASE,
)
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_RISON_TIME_RE = re.compile(r"^[A-Za-z0-9_+-]+$")
_DATA_VIEW_RE = re.compile(r"^[A-Za-z0-9_-]+$")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Helpers.access_token_helper import get_token_info, is_token_expired
from Helpers.environment_config import (
    get_consents_url,
    get_current_environment,
    get_database_file,
    get_kibana_settings,
    get_show_invalid_consents,
    load_environment_config,
    load_token_config,
    set_environment,
)
from Helpers.data_store import (
    get_client_credentials,
    load_auth_codes_collection,
    load_auth_config,
    load_registrations,
    load_tokens,
    load_users,
    save_auth_config,
    save_users,
)
from Helpers.token_introspection_helper import (
    get_last_introspection_error,
    introspect_token,
    is_refresh_token_valid,
    revoke_token,
)

ENV_ORDER = ["ITG", "TST", "PRE", "PROD"]
SCOPE_OPTIONS = ["aisp", "pisp", "aisp pisp"]
PRIORITY_OPTIONS = ["NORM", "HIGH", "INST"]
CONSENT_SCOPES = [
    "AISP.Balance",
    "AISP.AccountList",
    "AISP.TransactionList",
    "PISP.PaymentInitiation",
]
ACCOUNT_COLUMNS = [
    "name18N",
    "IBAN",
    "BBAN",
    "Bank code",
    "Currency",
    "BIC",
    "Country code",
    "Relationship",
    "Product18N",
    "id",
]
TX_COLUMNS = ["amount", "currency", "creditDebitIndicator", "status", "valueDate", "note"]
PAYMENT_COLUMNS = [
    "instructionIdentification",
    "transactionIdentification",
    "amount + currency",
    "requestedExecutionDate",
    "dateCreated",
    "status",
    "code",
    "instructionPriority",
    "signId",
    "debtorAccountId",
    "debtorIban",
    "partyId",
]
USER_COLUMNS = ["Party ID", "Name", "Birth Date", "Username", "Phone"]
REG_COLUMNS = ["Name", "Client_id", "Scopes", "Registered"]
TOKEN_COLUMNS = [
    "Registration",
    "User",
    "Scope",
    "Expired",
    "Created",
    "Refresh Token Valid",
    "Refresh Token Created",
]
CONSENT_COLUMNS = ["Owner", "OAuth2 Client", "Scopes", "Created", "Valid To", "Consent ID"]

def pretty(data) -> str:
    try:
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(data)


def cell(value) -> str:
    if value is None:
        return ""
    return str(value)


def unique_labels(labels: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for label in labels:
        seen[label] = seen.get(label, 0) + 1
        result.append(label if seen[label] == 1 else f"{label} ({seen[label]})")
    return result


def environment_names() -> list[str]:
    cfg = load_environment_config()
    all_envs = list((cfg.get("environments") or {}).keys())
    return sorted(all_envs, key=lambda env: (ENV_ORDER.index(env) if env in ENV_ORDER else 999, env))


def clear_environment_cache() -> None:
    import Helpers.environment_config as env_config_module

    env_config_module._config_cache = None
    env_config_module._current_environment = None


def switch_saved_environment(environment: str) -> str:
    set_environment(environment)
    clear_environment_cache()
    return get_current_environment()


def client_choices() -> list[tuple[str, str, str]]:
    choices = []
    for reg in load_registrations():
        body = (reg.get("response") or {}).get("body") or {}
        client_id = body.get("client_id")
        if not client_id:
            continue
        name = body.get("client_name") or "Unknown"
        choices.append((f"{name} ({client_id})", str(client_id), name))
    return choices


def user_choices() -> list[tuple[str, str, str]]:
    choices = []
    for user in load_users():
        party_id = user.get("partyId")
        if not party_id:
            continue
        name = user.get("name") or "Unknown"
        choices.append((f"{name} ({party_id})", str(party_id), name))
    return choices


def client_name_map() -> dict[str, str]:
    mapping = {}
    for reg in load_registrations():
        response_body = (reg.get("response") or {}).get("body") or {}
        request_body = (reg.get("request") or {}).get("body") or {}
        client_id = response_body.get("client_id")
        if client_id:
            mapping[client_id] = request_body.get("client_name") or response_body.get("client_name") or client_id
    return mapping


def user_name_map() -> dict[str, str]:
    mapping = {}
    for user in load_users():
        party_id = user.get("partyId")
        if party_id:
            mapping[str(party_id)] = user.get("name") or f"User {party_id}"
    return mapping


def request_id_from_text(*parts: str) -> str:
    """Last printed X-Request-ID. Scripts often echo the header more than once."""
    found = ""
    for part in parts:
        for match in _REQUEST_ID_RE.finditer(part or ""):
            found = match.group(1)
    return found


def result_request_id(result: dict | None) -> str:
    if not isinstance(result, dict):
        return ""
    explicit = str(result.get("request_id") or "").strip()
    if _UUID_RE.fullmatch(explicit):
        return explicit
    return request_id_from_text(str(result.get("output") or ""), str(result.get("error") or ""))


def _rison_string(value: str) -> str:
    escaped = value.replace("!", "!!").replace("'", "!'")
    return f"'{escaped}'"


def kibana_discover_url(kql: str) -> str:
    """Discover URL for one KQL query. Empty when this environment has no Kibana URL."""
    settings = get_kibana_settings()
    base = settings["discover_url"].split("#", 1)[0].strip().rstrip("/")
    if not base or not kql.strip():
        return ""
    time_from = settings["time_from"]
    if not _RISON_TIME_RE.fullmatch(time_from):
        time_from = "now-24h"
    data_view = settings["data_view"]
    data_source = ""
    if data_view and _DATA_VIEW_RE.fullmatch(data_view):
        data_source = f"dataSource:(dataViewId:'{data_view}',type:dataView),"
    global_state = f"(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:{time_from},to:now))"
    app_state = (
        f"(columns:!(message),{data_source}filters:!(),interval:auto,"
        f"query:(language:kuery,query:{_rison_string(kql)}),"
        "sort:!(!('@timestamp',desc)))"
    )
    return f"{base}#/?_g={global_state}&_a={app_state}"


def kibana_request_kql(request_id: str) -> str:
    """Match the request id anywhere in message. The id can be any text."""
    request_id = (request_id or "").strip()
    if not request_id:
        return ""
    escaped = request_id.replace("\\", "\\\\").replace('"', '\\"')
    return f'message: "*{escaped}*"'


def kibana_request_url(request_id: str) -> str:
    """Logs keep X-Request-ID inside message, not in its own field."""
    return kibana_discover_url(kibana_request_kql(request_id))


def kibana_spans_kql(span_ids: list[str]) -> str:
    """Quoted wildcard so a span id matches the access log and the internal services."""
    clauses = []
    for span_id in span_ids:
        span_id = (span_id or "").strip()
        if span_id and span_id not in clauses:
            clauses.append(span_id.replace("\\", "\\\\").replace('"', '\\"'))
    return " or ".join(f'"*{span_id}*"' for span_id in clauses)


def kibana_spans_url(span_ids: list[str]) -> str:
    """Internal logs are tied to X-B3-SpanId from the access log, not to X-Request-ID."""
    return kibana_discover_url(kibana_spans_kql(span_ids))


def kibana_span_url(span_id: str) -> str:
    """Internal services log under x-b3-span-id taken from the X-Request-ID hits."""
    return kibana_spans_url([span_id])


def run_script(script: str, args: list[str], capture: bool = True) -> dict:
    cmd = [sys.executable, str(ROOT / "Requests" / script), *args]
    try:
        if capture:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=ROOT,
            )
            if result.stdout:
                print(result.stdout, flush=True)
            if result.stderr:
                print(result.stderr, file=sys.stderr, flush=True)
            output = result.stdout or ""
            error = result.stderr or ""
            return {
                "success": result.returncode == 0,
                "output": output,
                "error": error,
                "returncode": result.returncode,
                "request_id": request_id_from_text(output, error),
            }
        result = subprocess.run(cmd, text=True, cwd=ROOT)
        return {
            "success": result.returncode == 0,
            "output": "",
            "error": "",
            "returncode": result.returncode,
            "request_id": "",
        }
    except Exception as exc:
        return {"success": False, "output": "", "error": str(exc), "returncode": -1, "request_id": ""}


def response_http_status(output: str) -> int | None:
    matches = re.findall(r"Response Status:\s*(\d+)", output or "")
    if not matches:
        return None
    return int(matches[-1])


def extract_json(output: str):
    if not output:
        return None
    marker = "📄 Response Body:"
    if marker in output:
        section = output[output.rfind(marker) + len(marker):].strip()
        parsed = _first_json_object(section)
        if parsed is not None:
            return parsed
    for pattern in (r"\{[\s\S]*\"accounts\"[\s\S]*\}", r"\{[\s\S]*\"transactions\"[\s\S]*\}"):
        match = re.search(pattern, output)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return _first_json_object(output)


def _first_json_object(text: str):
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:index + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_consents_output(output: str) -> list:
    start_marker = "[CONSENTS_JSON_START]"
    end_marker = "[CONSENTS_JSON_END]"
    start = output.find(start_marker)
    end = output.find(end_marker)
    if start < 0 or end < 0:
        return []
    try:
        data = json.loads(output[start + len(start_marker):end].strip())
    except Exception:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def dashboard_view() -> dict:
    return {
        "registration_count": str(len(load_registrations())),
        "user_count": str(len(load_users())),
        "account_count": str(len(load_user_accounts())),
        "payment_count": str(len(load_created_payments())),
    }


def users_view() -> dict:
    users = load_users()
    rows = []
    labels = []
    payloads = []
    cards = []
    for index, user in enumerate(users):
        party_id = cell(user.get("partyId"))
        name = cell(user.get("name") or "Unknown")
        birth = cell(user.get("birthDate"))
        username = cell(user.get("username"))
        phone = cell(user.get("phoneNumber"))
        labels.append(f"{name} ({party_id or 'N/A'})")
        payloads.append(pretty(user))
        rows.append([party_id, name, birth, username, phone])
        cards.append({
            "index": str(index),
            "name": name,
            "id": party_id,
            "birth": birth,
            "username": username,
            "phone": phone,
        })
    return {"rows": rows, "cards": cards, "labels": unique_labels(labels), "payloads": payloads}


def save_user_record(edit: bool, label: str, labels: list[str], form: dict) -> tuple[bool, str]:
    required = [form.get("partyId"), form.get("name"), form.get("birthDate"), form.get("username"), form.get("password")]
    if not all(required):
        return False, "Please fill in all required fields."
    users = load_users()
    if edit and label in labels:
        index = labels.index(label)
        if index < len(users):
            users[index] = form
            message = f"User {form['name']} updated."
        else:
            users.append(form)
            message = f"User {form['name']} added."
    else:
        users.append(form)
        message = f"User {form['name']} added."
    if not save_users(users):
        return False, "Could not save users."
    return True, message


def delete_user_record(index: int) -> tuple[bool, str]:
    users = load_users()
    if index < 0 or index >= len(users):
        return False, "User was not found."
    removed = users.pop(index)
    if not save_users(users):
        return False, "Could not delete the user."
    name = removed.get("name") or "User"
    return True, f"User {name} deleted."


def account_list_mode_from_config(config: dict | None) -> str:
    mode = str((config or {}).get("accountListMode") or "carousel").strip().lower()
    return mode if mode in {"carousel", "table"} else "carousel"


def config_view() -> dict:
    config = load_auth_config() or {}
    return {
        "party_id": cell(config.get("partyId")),
        "client_id": cell(config.get("client_id")),
        "redirect_uri": cell(config.get("redirect_uri")),
        "account_list_mode": account_list_mode_from_config(config),
        "json": pretty(config) if config else "",
    }


def save_config_record(party_id: str, client_id: str, redirect_uri: str, account_list_mode: str = "carousel") -> tuple[bool, str]:
    if not all([party_id.strip(), client_id.strip(), redirect_uri.strip()]):
        return False, "Please fill in all required fields."
    data = {
        "partyId": party_id.strip(),
        "client_id": client_id.strip(),
        "redirect_uri": redirect_uri.strip(),
        "accountListMode": account_list_mode_from_config({"accountListMode": account_list_mode}),
    }
    if not save_auth_config(data):
        return False, "Could not save configuration."
    return True, "Configuration saved."


def _parse_timestamp(timestamp_str: str):
    if not timestamp_str:
        return None
    text = timestamp_str.strip()
    if text.endswith("+00:00Z"):
        text = text.replace("+00:00Z", "+00:00")
    elif text.endswith("+00:00+00:00"):
        text = text.replace("+00:00+00:00", "+00:00")
    elif text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def latest_valid_auth_code(user_id: str, client_id: str = "") -> dict | None:
    """Newest unexpired authorization code for this party id and selected TPP."""
    party_id = str(user_id or "").strip()
    tpp_id = str(client_id or "").strip()
    if not party_id or not tpp_id:
        return None
    expiration = load_token_config()["authorization_code_expiration_seconds"]
    now = datetime.now(timezone.utc)
    newest = None
    newest_created = None
    remaining = 0
    for code in load_auth_codes_collection().get("authorization_codes") or []:
        if str(code.get("user") or "") != party_id:
            continue
        if str(code.get("client_id") or "") != tpp_id:
            continue
        value = str(code.get("authorization_code") or "").strip()
        created = _parse_timestamp(code.get("timestamp") or "")
        if not value or not created:
            continue
        age = (now - created).total_seconds()
        if age >= expiration:
            continue
        if newest_created is None or created > newest_created:
            newest = code
            newest_created = created
            remaining = expiration - age
    if not newest:
        return None
    if remaining >= 60:
        status = f"Valid — expires in {int(remaining / 60)} minutes"
    else:
        status = f"Valid — expires in {max(1, int(remaining))} seconds"
    return {
        "code": str(newest.get("authorization_code") or ""),
        "state": str(newest.get("state") or ""),
        "client_id": str(newest.get("client_id") or ""),
        "status": status,
    }


def forget_auth_code(state: str) -> None:
    marker = str(state or "").strip()
    if not marker:
        return
    path = get_database_file("last_authorization_code.json")
    codes = [
        item
        for item in (load_auth_codes_collection().get("authorization_codes") or [])
        if str(item.get("state") or "") != marker
    ]
    path.write_text(
        json.dumps({"authorization_codes": codes}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def exchange_authorization_code(client_id: str, user_id: str, state: str) -> dict:
    args = ["--client-id", str(client_id), "--user-id", str(user_id)]
    if state:
        args.extend(["--state", str(state)])
    result = run_script("TPP_GetTokenFromCode.py", args, capture=True)
    output = f"{result['output']}\n{result['error']}"
    if result["success"] and "Token exchange successful!" in output:
        forget_auth_code(state)
        return {"ok": True, "message": "Token created from the authorization code."}
    if "Authorization code expired" in output:
        return {"ok": False, "message": "Authorization code is expired."}
    if result["error"]:
        return {"ok": False, "message": f"Token exchange failed. {result['error'][:240]}"}
    return {"ok": False, "message": "Token exchange failed."}


def auth_codes_view(client_id: str = "", user_id: str = "") -> dict:
    """Valid authorization codes for the current context. Empty context returns every stored code."""
    names = client_name_map()
    users = user_name_map()
    expiration = load_token_config()["authorization_code_expiration_seconds"]
    now = datetime.now(timezone.utc)
    wanted_client = str(client_id or "").strip()
    wanted_user = str(user_id or "").strip()
    codes = []
    for code in load_auth_codes_collection().get("authorization_codes") or []:
        if wanted_client and str(code.get("client_id") or "") != wanted_client:
            continue
        if wanted_user and str(code.get("user") or "") != wanted_user:
            continue
        codes.append(code)
    codes.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
    cards = []
    for index, code in enumerate(codes):
        token_client = str(code.get("client_id") or "")
        token_user = "" if code.get("user") in (None, "") else str(code.get("user"))
        created = _parse_timestamp(code.get("timestamp") or "")
        expires = ""
        status = "Valid"
        if created:
            left = expiration - (now - created).total_seconds()
            if left >= 60:
                minutes = int(left / 60)
                expires = f"{minutes} min"
                status = f"Valid — expires in {minutes} minutes"
            elif left > 0:
                seconds = max(1, int(left))
                expires = f"{seconds} sec"
                status = f"Valid — expires in {seconds} seconds"
            else:
                expires = "Expired"
                status = "Expired"
        cards.append({
            "index": str(index),
            "tpp": names.get(token_client, token_client),
            "tpp_id": token_client,
            "user": users.get(token_user, token_user),
            "user_id": token_user,
            "scope": str(code.get("scope") or ""),
            "state": str(code.get("state") or ""),
            "code": str(code.get("authorization_code") or ""),
            "redirect": str(code.get("redirect_uri") or ""),
            "status": status,
            "expires": expires,
            "created": created.strftime("%Y-%m-%d %H:%M") if created else "",
        })
    return {"cards": cards}


def fetch_otp_codes(party_id: str, minutes: int) -> tuple[list | None, str]:
    try:
        from Helpers.sms_otp_helper import list_party_otps_requests

        codes = list_party_otps_requests(
            party_id=int(party_id),
            time_range_minutes=minutes,
            verify_ssl=False,
        )
        return codes or [], ""
    except Exception as exc:
        return None, str(exc)


def otp_result_items(codes: list) -> list[dict[str, str]]:
    items = []
    for code in codes:
        created_at = str(code.get("createdAt") or "")
        created = _parse_timestamp(created_at) if created_at else None
        timestamp = created.strftime("%Y-%m-%d %H:%M:%S") if created else created_at[:19]
        otp_value = str(((code.get("smsData") or {}).get("otpValue")) or "")
        items.append({
            "time": timestamp,
            "status": str(code.get("otpStatus") or ""),
            "otp": otp_value,
            "phone": str(code.get("phoneNumber") or ""),
        })
    return items


def registration_template() -> dict:
    path = ROOT / "Database" / "tpp_registration_template_data.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def registrations_view() -> dict:
    registrations = load_registrations()
    rows = []
    labels = []
    payloads = []
    cards = []
    for index, reg in enumerate(registrations):
        response_body = (reg.get("response") or {}).get("body") or {}
        request_body = (reg.get("request") or {}).get("body") or {}
        name = response_body.get("client_name") or "Unknown"
        client_id = response_body.get("client_id") or ""
        scopes = response_body.get("scope") or request_body.get("scope") or ""
        registered = (reg.get("timestamp") or "")[:10]
        labels.append(f"{name} ({client_id or 'N/A'})")
        payloads.append(pretty(reg))
        rows.append([
            cell(name),
            cell(client_id),
            cell(scopes),
            cell(registered),
        ])
        cards.append({
            "index": str(index),
            "name": cell(name),
            "id": cell(client_id),
            "scopes": cell(scopes),
            "registered": cell(registered),
        })
    template = registration_template()
    return {
        "count": str(len(registrations)),
        "rows": rows,
        "cards": cards,
        "labels": unique_labels(labels),
        "payloads": payloads,
        "template_name": cell(template.get("client_name")),
        "template_scope": template.get("scope") if template.get("scope") in SCOPE_OPTIONS else "aisp",
        "template_json": pretty(template) if template else "",
    }


def describe_registration(payload: str) -> dict:
    reg = json.loads(payload)
    body = (reg.get("response") or {}).get("body") or {}
    client_id = str(body.get("client_id") or "")
    client_secret = str(body.get("client_secret") or "")
    basic = ""
    if client_id and client_secret:
        encoded = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
        basic = f"Basic {encoded}"
    redirects = ", ".join(body.get("redirect_uris") or [])
    grants = ", ".join(body.get("grant_types") or [])
    registered = (reg.get("timestamp") or "")[:10]
    meta = "\n".join([
        f"Client name: {body.get('client_name') or 'N/A'}",
        f"Scope: {body.get('scope') or 'N/A'}",
        f"Redirect URIs: {redirects or 'N/A'}",
        f"Grant types: {grants or 'N/A'}",
        f"Token endpoint auth method: {body.get('token_endpoint_auth_method') or 'N/A'}",
        f"Registered: {registered or 'Unknown'}",
    ])
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": str(body.get("registration_access_token") or ""),
        "basic_auth": basic,
        "meta": meta,
        "json": pretty(reg),
        "raw_client_id": client_id,
        "name": cell(body.get("client_name") or "Unknown"),
        "scope": cell(body.get("scope") or ""),
        "registered": cell(registered),
        "redirect": cell(redirects),
        "grants": cell(grants),
        "auth_method": cell(body.get("token_endpoint_auth_method") or ""),
    }


def register_tpp(name: str, scope: str) -> dict:
    if not name.strip():
        return {"ok": False, "message": "Registration name is required.", "output": ""}
    result = run_script("TPP_Registration_post.py", ["--client-name", name.strip(), "--scope", scope])
    output = result["error"] or result["output"]
    if result["success"]:
        return {"ok": True, "message": "Registration completed.", "output": result["output"], "request_id": result.get("request_id") or ""}
    return {"ok": False, "message": "Registration failed.", "output": output, "request_id": result.get("request_id") or ""}


def delete_registration(client_id: str) -> dict:
    result = run_script("TPP_Registration_delete.py", ["--client-id", client_id])
    output = result["error"] or result["output"]
    if result["success"]:
        return {"ok": True, "message": "Registration deleted.", "output": result["output"], "request_id": result.get("request_id") or ""}
    return {"ok": False, "message": "Delete failed.", "output": output, "request_id": result.get("request_id") or ""}


def _format_refresh_created(timestamp_str: str) -> str:
    parsed = _parse_timestamp(timestamp_str)
    if parsed:
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    return timestamp_str[:19] if timestamp_str else "Unknown"


def check_refresh_token(token: dict) -> tuple[bool, str]:
    refresh_token = token.get("refresh_token") or ""
    client_id = token.get("client_id") or ""
    created = token.get("refresh_token_created") or ""
    if not refresh_token:
        return False, "N/A"
    credentials = get_client_credentials(client_id) if client_id else None
    if credentials:
        try:
            valid = is_refresh_token_valid(refresh_token, credentials["client_id"], credentials["client_secret"])
        except Exception as exc:
            if is_service_unavailable(str(exc)):
                return False, "Service unavailable"
            valid = False
        if not valid and is_service_unavailable(get_last_introspection_error()):
            return False, "Service unavailable"
        created_text = _format_refresh_created(created) if created else ""
        status = "Valid" if valid else "Invalid"
        return valid, f"{created_text} ({status})" if created_text else status
    if created:
        return True, f"{_format_refresh_created(created)} (cannot verify)"
    return True, "Cannot verify (missing credentials)"


def tokens_view(client_id: str, user_id: str) -> dict:
    tokens = load_tokens()
    names = client_name_map()
    users = user_name_map()
    filtered = tokens
    info_parts = []
    if client_id:
        filtered = [token for token in filtered if token.get("client_id") == client_id]
        info_parts.append(f"Registration: {names.get(client_id, client_id)}")
    if user_id:
        filtered = [token for token in filtered if str(token.get("user")) == str(user_id)]
        info_parts.append(f"User: {users.get(str(user_id), user_id)}")
    rows = []
    labels = []
    payloads = []
    cards = []
    for index, token in enumerate(filtered):
        access = token.get("access_token") or ""
        try:
            expired = is_token_expired(access) if access else True
        except Exception:
            expired = True
        token_client = str(token.get("client_id") or "")
        token_user = "" if token.get("user") in (None, "") else str(token.get("user"))
        client_name = names.get(token_client, token_client)
        user_name = users.get(token_user, token_user)
        scope = str(token.get("scope") or "")
        created = _consent_day(token.get("timestamp"))
        refresh_created_raw = str(token.get("refresh_token_created") or "")
        refresh_created = _format_refresh_created(refresh_created_raw) if refresh_created_raw else ""
        access_status = "Expired" if expired else "Valid"
        labels.append(f"{client_name or token_client} — {user_name or token_user}")
        payloads.append(pretty(token))
        rows.append([
            cell(client_name or token_client),
            cell(user_name or token_user),
            cell(scope),
            cell(access_status),
            cell(created),
        ])
        cards.append({
            "index": str(index),
            "tpp": client_name or token_client,
            "tpp_id": token_client,
            "user": user_name or token_user,
            "user_id": token_user,
            "scope": scope,
            "access": access_status,
            "created": created,
            "refresh_created": refresh_created,
        })
    return {
        "total": len(tokens),
        "shown": len(filtered),
        "filter_info": "Filtered by context: " + ", ".join(info_parts) if info_parts else "",
        "rows": rows,
        "labels": unique_labels(labels),
        "payloads": payloads,
        "cards": cards,
    }


def describe_token(payload: str) -> dict:
    token = json.loads(payload)
    names = client_name_map()
    users = user_name_map()
    client_id = token.get("client_id") or "N/A"
    user_id = token.get("user") or "N/A"
    access = token.get("access_token") or ""
    meta = "\n".join([
        f"Registration: {names.get(client_id, client_id)}",
        f"Client ID: {client_id}",
        f"User: {users.get(str(user_id), user_id)}",
        f"User (Party ID): {user_id}",
        f"Scope: {token.get('scope') or 'N/A'}",
        f"Token type: {token.get('token_type') or 'N/A'}",
        f"Expires in: {token.get('expires_in', 'N/A')} seconds",
        f"Created: {token.get('timestamp') or 'N/A'}",
    ])
    parsed = ""
    expires = ""
    if access:
        try:
            info = get_token_info(access)
            lines = []
            if info.get("user"):
                lines.append(f"User (Party ID): {info['user']}")
            if info.get("client_id"):
                lines.append(f"Client ID: {info['client_id']}")
            if info.get("scope"):
                lines.append(f"Scope: {info['scope']}")
            if info.get("exp_datetime"):
                expires = str(info["exp_datetime"])
                lines.append(f"Expires at: {info['exp_datetime']}")
            if "expired" in info:
                lines.append("Status: EXPIRED" if info.get("expired") else "Status: Valid")
            if info.get("expires_in_seconds") is not None:
                lines.append(
                    f"Time remaining: {info['expires_in_seconds']} seconds ({info.get('expires_in_minutes', 0)} minutes)"
                )
            parsed = "\n".join(lines)
        except Exception as exc:
            parsed = f"Could not parse token: {exc}"
    return {
        "access": access or "N/A",
        "refresh": token.get("refresh_token") or "N/A",
        "meta": meta,
        "parsed": parsed,
        "json": pretty(token),
        "client_id": "" if client_id == "N/A" else str(client_id),
        "expires": expires[:19].replace("T", " ") if expires else "",
    }


def run_introspection(token_value: str, client_id: str) -> dict:
    credentials = get_client_credentials(client_id)
    if not credentials:
        return {"ok": False, "message": "Client credentials not found for this token.", "summary": "", "json": ""}
    if not token_value or token_value == "N/A":
        return {"ok": False, "message": "Selected token value is empty.", "summary": "", "json": ""}
    result = introspect_token(token_value, credentials["client_id"], credentials["client_secret"])
    if not result:
        details = get_last_introspection_error()
        return {"ok": False, "message": details or "Introspection failed.", "summary": "", "json": ""}
    lines = ["ACTIVE" if result.get("active") else "INACTIVE"]
    for key in ("token_type", "scope", "client_id", "sub"):
        if result.get(key):
            lines.append(f"{key}: {result.get(key)}")
    for key, label in (("exp", "Expires at"), ("iat", "Issued at")):
        if result.get(key):
            try:
                value = float(result.get(key))
                moment = datetime.fromtimestamp(value, tz=timezone.utc)
                lines.append(f"{label}: {moment.isoformat()}")
                if key == "exp":
                    remaining = moment - datetime.now(timezone.utc)
                    if remaining.total_seconds() > 0:
                        lines.append(f"Time remaining: {int(remaining.total_seconds())} seconds")
                    else:
                        lines.append("Status: EXPIRED")
            except (TypeError, ValueError):
                lines.append(f"{label}: {result.get(key)}")
    return {"ok": True, "message": "Introspection successful.", "summary": "\n".join(lines), "json": pretty(result)}


def run_revocation(token_value: str, client_id: str, token_type: str) -> dict:
    credentials = get_client_credentials(client_id)
    if not credentials:
        return {"ok": False, "message": "Client credentials not found for this token."}
    if not token_value or token_value == "N/A":
        return {"ok": False, "message": "Selected token value is empty."}
    hint = "access_token" if token_type == "Access Token" else "refresh_token"
    success = revoke_token(token_value, credentials["client_id"], credentials["client_secret"], token_type_hint=hint)
    if success:
        return {"ok": True, "message": "Token revoked. It can no longer be used."}
    return {"ok": False, "message": "Token revocation failed. Check the console for details."}


def _consent_day(value) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "unknown":
        return ""
    return text[:10]


def _consent_items(data) -> list:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("consents", "items", "content", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if data.get("consentId") or data.get("ownerId"):
            return [data]
    return []


def _consent_owner_ids(client_id: str, user_id: str) -> list[str]:
    if str(user_id or "").strip():
        return [str(user_id).strip()]
    if not str(client_id or "").strip():
        return []
    owners = []
    for user in load_users():
        party_id = str(user.get("partyId") or "").strip()
        if party_id and party_id not in owners:
            owners.append(party_id)
    return owners


def fetch_consents(client_id: str, user_id: str) -> tuple[list | None, str]:
    owners = _consent_owner_ids(client_id, user_id)
    if not owners:
        return [], ""
    try:
        import requests
        import urllib3
        from Helpers.employee_token_retriever import get_employee_token_requests

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        token = get_employee_token_requests(verify_ssl=False)
        valid_only = not get_show_invalid_consents()
        collected = []
        seen = set()
        failures = []
        for owner_id in owners:
            response = requests.get(
                get_consents_url(),
                params={
                    "owner-id": owner_id,
                    "valid-consents-only": str(valid_only).lower(),
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Request-ID": str(uuid.uuid4()),
                    "Content-Type": "application/json",
                },
                verify=False,
                timeout=30,
            )
            if response.status_code in (500, 502, 503, 504):
                return None, f"HTTP {response.status_code} from consents endpoint."
            if response.status_code != 200:
                failures.append(f"HTTP {response.status_code} from consents endpoint.")
                continue
            try:
                items = _consent_items(response.json())
            except Exception:
                failures.append("Unexpected consents response.")
                continue
            for item in items:
                consent_id = str(item.get("consentId") or "")
                if consent_id:
                    if consent_id in seen:
                        continue
                    seen.add(consent_id)
                collected.append(item)
        if not collected and failures and len(failures) == len(owners):
            return None, failures[0]
        return collected, ""
    except Exception as exc:
        return None, str(exc)


def consents_view(consents: list, client_id: str, user_id: str) -> dict:
    names = client_name_map()
    users = user_name_map()
    filtered = consents
    if client_id:
        filtered = [item for item in consents if str(item.get("oauth2ClientId") or "") == str(client_id)]
    rows = []
    labels = []
    payloads = []
    cards = []
    for index, consent in enumerate(filtered):
        owner_raw = consent.get("ownerId")
        owner_id = "" if owner_raw in (None, "") else str(owner_raw)
        oauth_id = str(consent.get("oauth2ClientId") or "")
        owner = users.get(owner_id, owner_id)
        client_name = str(consent.get("oauth2ClientName") or "") or names.get(oauth_id, oauth_id)
        scopes = consent.get("scopes") or []
        scope_text = ", ".join(str(item) for item in scopes) if isinstance(scopes, list) else str(scopes or "")
        valid_from = _consent_day(consent.get("validFrom"))
        valid_to = _consent_day(consent.get("validTo"))
        consent_id = str(consent.get("consentId") or "")
        labels.append(f"{owner or owner_id} — {client_name or oauth_id}")
        payloads.append(pretty(consent))
        rows.append([
            cell(owner or owner_id),
            cell(client_name or oauth_id),
            cell(scope_text),
            cell(valid_from),
            cell(valid_to),
            cell(consent_id),
        ])
        cards.append({
            "index": str(index),
            "owner": owner or owner_id,
            "owner_id": owner_id,
            "tpp": client_name or oauth_id,
            "tpp_id": oauth_id,
            "scopes": scope_text,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "id": consent_id,
        })
    info = ""
    if user_id:
        info = f"User: {users.get(str(user_id), user_id)} ({user_id})"
    if client_id:
        info = f"{info} | TPP: {names.get(client_id, client_id)}".strip(" |")
    count = f"Total consents: {len(filtered)}"
    if client_id and len(filtered) < len(consents):
        count = f"Total consents: {len(filtered)} of {len(consents)} (filtered by TPP)"
    return {
        "count": count,
        "filter_info": info,
        "rows": rows,
        "labels": unique_labels(labels),
        "payloads": payloads,
        "cards": cards,
        "empty_message": _consent_empty_message(consents, filtered, client_id),
    }


def _consent_empty_message(consents: list, filtered: list, client_id: str) -> str:
    if not consents:
        return "No consents found."
    if not filtered and client_id:
        return f"No consents found for client ID {client_id}."
    return ""


def describe_consent(payload: str) -> dict:
    consent = json.loads(payload)
    users = user_name_map()
    names = client_name_map()
    owner_raw = consent.get("ownerId")
    owner_id = "" if owner_raw in (None, "") else str(owner_raw)
    client_id = str(consent.get("oauth2ClientId") or "")
    scopes = consent.get("scopes") or []
    disponents = consent.get("disponentIds") or []
    scope_text = ", ".join(str(item) for item in scopes) if isinstance(scopes, list) else str(scopes or "")
    disponent_text = ", ".join(str(item) for item in disponents) if isinstance(disponents, list) else str(disponents or "")
    client_name = str(consent.get("oauth2ClientName") or "") or names.get(client_id, "")
    owner_name = users.get(owner_id, "")
    valid_from = _consent_day(consent.get("validFrom"))
    valid_to = _consent_day(consent.get("validTo"))
    recalled = _consent_day(consent.get("recalledAt")) if consent.get("recalledAt") else ""
    summary = "\n".join([
        f"Owner ID: {owner_id or 'N/A'} ({owner_name or 'N/A'})",
        f"OAuth2 client ID: {client_id or 'N/A'}",
        f"OAuth2 client name: {client_name or 'N/A'}",
        f"Disponent IDs: {disponent_text or 'N/A'}",
        f"Scopes: {scope_text or 'N/A'}",
    ])
    meta_lines = [
        f"Valid from: {valid_from or 'Unknown'}",
        f"Valid to: {valid_to or 'Unknown'}",
    ]
    if recalled:
        meta_lines.append(f"Recalled at: {recalled}")
    consent_id = str(consent.get("consentId") or "")
    if consent_id:
        meta_lines.append(f"Consent ID: {consent_id}")
    return {
        "summary": summary,
        "meta": "\n".join(meta_lines),
        "json": pretty(consent),
        "id": consent_id,
        "owner": owner_name,
        "owner_id": owner_id,
        "client": client_name,
        "client_id": client_id,
        "scopes": scope_text,
        "disponents": disponent_text,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "recalled": recalled,
    }


def create_consent(owner_id: str, oauth_client_id: str, oauth_client_name: str, disponent_ids: str, scopes: list[str]) -> dict:
    if not owner_id.strip():
        return {"ok": False, "message": "Owner ID is required.", "output": ""}
    if not oauth_client_id.strip():
        return {"ok": False, "message": "OAuth2 client ID is required.", "output": ""}
    if not scopes:
        return {"ok": False, "message": "At least one scope is required.", "output": ""}
    try:
        parsed_ids = [int(part.strip()) for part in disponent_ids.split(",") if part.strip()] if disponent_ids.strip() else [int(owner_id)]
    except ValueError:
        return {"ok": False, "message": "Disponent IDs must be comma-separated integers.", "output": ""}
    args = [
        "--client-id", oauth_client_id.strip(),
        "--user-id", owner_id.strip(),
        "--owner-id", owner_id.strip(),
        "--oauth2-client-id", oauth_client_id.strip(),
        "--disponent-ids", ",".join(map(str, parsed_ids)),
        "--scopes", ",".join(scopes),
    ]
    if oauth_client_name.strip():
        args.extend(["--oauth2-client-name", oauth_client_name.strip()])
    result = run_script("TPP_Consent_Post.py", args)
    output = result["error"] or result["output"]
    if result["success"]:
        return {"ok": True, "message": "Consent created.", "output": result["output"], "request_id": result.get("request_id") or ""}
    return {"ok": False, "message": "Consent creation failed.", "output": output, "request_id": result.get("request_id") or ""}


def delete_consents(token_client_id: str, token_user_id: str, user_id_param: str, oauth_client_id: str) -> dict:
    if not user_id_param.strip() or not oauth_client_id.strip():
        return {"ok": False, "message": "User ID and OAuth2 client ID are required.", "output": ""}
    result = run_script("TPP_Consent_Delete.py", [
        "--client-id", token_client_id or oauth_client_id.strip(),
        "--user-id", token_user_id or user_id_param.strip(),
        "--user-id-param", user_id_param.strip(),
        "--oauth2-client-id", oauth_client_id.strip(),
    ])
    output = result["error"] or result["output"]
    if result["success"]:
        return {"ok": True, "message": "Consents deleted.", "output": result["output"], "request_id": result.get("request_id") or ""}
    return {"ok": False, "message": "Delete failed.", "output": output, "request_id": result.get("request_id") or ""}


def delete_consent_by_id(consent_id: str) -> dict:
    if not consent_id.strip():
        return {"ok": False, "message": "Consent ID is required.", "output": ""}
    try:
        import requests
        from Helpers.employee_token_retriever import get_employee_token_requests

        url = f"{get_consents_url()}/{consent_id.strip()}"
        token = get_employee_token_requests(verify_ssl=False)
        request_id = str(uuid.uuid4())
        response = requests.delete(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Request-ID": request_id,
                "Content-Type": "application/json",
            },
            verify=False,
            timeout=30,
        )
        body = response.text
        try:
            body = pretty(response.json())
        except Exception:
            pass
        if response.status_code in (200, 204):
            return {"ok": True, "message": f"Consent {consent_id.strip()} deleted.", "output": body, "request_id": request_id}
        return {"ok": False, "message": f"Delete failed. Status {response.status_code}.", "output": body, "request_id": request_id}
    except Exception as exc:
        return {"ok": False, "message": f"Error deleting consent: {exc}", "output": "", "request_id": ""}


def is_service_unavailable(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "timed out",
        "connect timeout",
        "read timeout",
        "max retries exceeded",
        "connection aborted",
        "connection refused",
        "connection reset",
        "failed to establish",
        "name or service not known",
        "temporary failure in name resolution",
        "network is unreachable",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
    )
    if any(marker in text for marker in markers):
        return True
    return any(f"http {code}" in text for code in ("500", "502", "503", "504"))


def _unavailable_status() -> dict:
    return {
        "status": "unavailable",
        "text": "Service unavailable",
        "access_ready": False,
        "refresh_ready": False,
    }


def check_token_status(client_id: str, user_id: str) -> dict:
    access_ready = False
    refresh_ready = False
    access_token = ""
    message = ""
    expires = ""
    for token in load_tokens():
        if token.get("client_id") == client_id and str(token.get("user")) == str(user_id):
            access_token = token.get("access_token") or ""
            refresh_token = token.get("refresh_token") or ""
            if access_token:
                try:
                    access_ready = not is_token_expired(access_token)
                except Exception as exc:
                    message = f"Error checking access token: {exc}"
            if refresh_token:
                credentials = get_client_credentials(client_id)
                if credentials:
                    try:
                        refresh_ready = is_refresh_token_valid(
                            refresh_token,
                            credentials["client_id"],
                            credentials["client_secret"],
                        )
                        if not refresh_ready and is_service_unavailable(get_last_introspection_error()):
                            return _unavailable_status()
                        message = "Refresh token is valid" if refresh_ready else "Refresh token is expired or invalid"
                    except Exception as exc:
                        if is_service_unavailable(str(exc)):
                            return _unavailable_status()
                        message = f"Error checking refresh token: {exc}"
                else:
                    refresh_ready = True
                    message = "Refresh token exists (cannot verify — missing credentials)"
            break
    if access_ready and access_token:
        try:
            info = get_token_info(access_token)
            if info.get("expires_in_minutes") is not None:
                expires = f"Expires in {int(info.get('expires_in_minutes') or 0)} min"
        except Exception:
            pass
    if access_ready:
        status = "ready"
        text = "Access token ready"
    elif refresh_ready:
        status = "needs_refresh"
        text = "Refresh token ready — access token needs refresh"
    else:
        status = "needs_auth"
        text = "No valid token — authorization required"
    if expires:
        text = f"{text}. {expires}"
    if message and status != "ready":
        text = f"{text}. {message}"
    return {"status": status, "text": text, "access_ready": access_ready, "refresh_ready": refresh_ready}


def account_rows_from_response(account_data) -> tuple[list[list[str]], list[str], list[str]]:
    accounts = account_data.get("accounts") if isinstance(account_data, dict) else []
    if not isinstance(accounts, list):
        return [], [], []
    rows = []
    labels = []
    payloads = []
    for index, account in enumerate(accounts, 1):
        if not isinstance(account, dict):
            continue
        identification = account.get("identification") if isinstance(account.get("identification"), dict) else {}
        servicer = account.get("servicer") if isinstance(account.get("servicer"), dict) else {}
        relationship = account.get("realtionship") if isinstance(account.get("realtionship"), dict) else {}
        relationship_str = "Owner" if relationship.get("isOwner") else ""
        iban = identification.get("iban") or ""
        account_id = str(account.get("id") or "").strip()
        name = account.get("nameI18N") or account.get("name18N") or "Account"
        parts = [str(name)]
        if iban:
            parts.append(iban)
        if account_id:
            parts.append(f"id: {account_id}")
        label = " | ".join(parts)
        if label in labels:
            label = f"{label} ({index})"
        labels.append(label)
        payloads.append(pretty(account))
        rows.append([
            cell(account.get("nameI18N") or ""),
            cell(iban),
            cell(identification.get("other") or ""),
            cell(servicer.get("bankCode") or ""),
            cell(account.get("currency") or ""),
            cell(servicer.get("bic") or ""),
            cell(servicer.get("countryCode") or ""),
            relationship_str,
            cell(account.get("productI18N") or ""),
            cell(account.get("id") or ""),
        ])
    return rows, labels, payloads


def _first_present(data: dict, keys: list[str], default=""):
    for key in keys:
        value = data.get(key)
        if value not in (None, "") and not isinstance(value, (dict, list)):
            return value
    return default


def _extract_amount_and_currency(transaction: dict):
    amount_data = (
        transaction.get("amount")
        or transaction.get("transactionAmount")
        or transaction.get("instructedAmount")
        or {}
    )
    if isinstance(amount_data, dict):
        nested = amount_data.get("instructedAmount")
        if isinstance(nested, dict):
            amount_data = nested
    if isinstance(amount_data, dict):
        return _first_present(amount_data, ["value", "amount"]), _first_present(amount_data, ["currency", "currencyCode"])
    return amount_data, transaction.get("currency", "")


def _extract_note(transaction: dict):
    remittance = transaction.get("remittanceInformation")
    if isinstance(remittance, dict):
        note = remittance.get("unstructured")
        if isinstance(note, list):
            return ", ".join(str(item) for item in note)
        if note:
            return note
    return _first_present(transaction, ["note", "description", "message", "narrative", "details"])


def _transaction_items(transactions_data):
    transactions = transactions_data
    if isinstance(transactions_data, dict):
        transactions = transactions_data.get("transactions", transactions_data)
    if not isinstance(transactions, list):
        return []
    return [item for item in transactions if isinstance(item, dict)]


def transaction_total(transactions_data) -> int:
    if not isinstance(transactions_data, dict):
        return -1
    sources = [transactions_data]
    page = transactions_data.get("page")
    if isinstance(page, dict):
        sources.append(page)
    for source in sources:
        for key in ("totalCount", "totalElements", "total"):
            value = source.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
    return -1


def _booking_date(transaction: dict) -> str:
    raw = transaction.get("bookingDate")
    if isinstance(raw, dict):
        raw = raw.get("date") or raw.get("dateTime") or ""
    text = str(raw or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return text


def _party_iban(node) -> str:
    if not isinstance(node, dict):
        return ""
    identification = node.get("identification")
    if isinstance(identification, dict) and identification.get("iban"):
        return str(identification.get("iban"))
    if node.get("iban"):
        return str(node.get("iban"))
    return ""


def _entry_details(transaction: dict) -> list[dict]:
    entry = transaction.get("entryDetails")
    entries = entry if isinstance(entry, list) else ([entry] if isinstance(entry, dict) else [])
    details = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        nested = item.get("transactionDetails")
        nested_list = nested if isinstance(nested, list) else ([nested] if isinstance(nested, dict) else [])
        details.extend(detail for detail in nested_list if isinstance(detail, dict))
        details.append(item)
    return details


def _related_parties(transaction: dict) -> list[dict]:
    parties = []
    for detail in _entry_details(transaction):
        related = detail.get("relatedParties")
        if isinstance(related, dict):
            parties.append(related)
    if isinstance(transaction.get("relatedParties"), dict):
        parties.append(transaction["relatedParties"])
    return parties


def _counterparty_iban(transaction: dict, indicator: str) -> str:
    code = str(indicator or "").strip().upper()
    party = "debtorAccount" if code.startswith("C") else "creditorAccount"
    candidates = []
    for related in _related_parties(transaction):
        candidates.append(related.get(party))
    candidates.append(transaction.get(party))
    for candidate in candidates:
        iban = _party_iban(candidate)
        if iban:
            return iban
    return ""


def _message_identification(transaction: dict) -> str:
    for detail in _entry_details(transaction):
        references = detail.get("references")
        if isinstance(references, dict) and references.get("messageIdentification"):
            return str(references.get("messageIdentification"))
    references = transaction.get("references")
    if isinstance(references, dict) and references.get("messageIdentification"):
        return str(references.get("messageIdentification"))
    return ""


def _counterparty_name(transaction: dict, indicator: str) -> str:
    code = str(indicator or "").strip().upper()
    party = "debtor" if code.startswith("C") else "creditor"
    for related in _related_parties(transaction):
        person = related.get(party)
        if isinstance(person, dict) and person.get("name"):
            return str(person.get("name"))
    return ""


def _signed_amount(amount, currency, indicator: str) -> str:
    money = _format_money(amount)
    if not money:
        return ""
    number = money[1:] if money.startswith("-") else money
    code = str(indicator or "").strip().upper()
    if code.startswith("D"):
        sign = "-"
    elif code.startswith("C"):
        sign = "+"
    else:
        sign = "-" if money.startswith("-") else "+"
    label = f"{sign} {number}"
    if currency:
        label = f"{label} {currency}"
    return label


def transaction_records(transactions_data) -> list[dict[str, str]]:
    records = []
    for index, item in enumerate(_transaction_items(transactions_data)):
        amount, currency = _extract_amount_and_currency(item)
        indicator = cell(_first_present(item, ["creditDebitIndicator"]))
        records.append({
            "index": str(index),
            "amount": _signed_amount(amount, currency, indicator),
            "currency": cell(currency),
            "creditDebitIndicator": indicator,
            "status": cell(_first_present(item, ["status", "bookingStatus"])),
            "bookingDate": _booking_date(item),
            "valueDate": cell(_first_present(item, ["valueDate", "bookingDate"])),
            "counterparty": _counterparty_iban(item, indicator),
            "counterpartyName": _counterparty_name(item, indicator),
            "identification": _message_identification(item),
            "tone": "credit" if indicator.upper().startswith("C") else ("debit" if indicator.upper().startswith("D") else ""),
            "note": cell(_extract_note(item)),
            "detail": pretty(item),
            "blank": "",
        })
    return records


def transaction_rows(transactions_data) -> list[list[str]]:
    return [
        [record[column] for column in TX_COLUMNS]
        for record in transaction_records(transactions_data)
    ]


def fetch_accounts(client_id: str, user_id: str, page: int = 0, size: int = 100) -> dict:
    return run_script("TPP_User_Account_List.py", [
        "--client-id", str(client_id),
        "--user-id", str(user_id),
        "--page", str(page),
        "--size", str(size),
    ])


def fetch_transactions(client_id: str, user_id: str, account_id: str, page: int, size: int) -> dict:
    return run_script("TPP_User_Account_Transactions.py", [
        "--client-id", str(client_id),
        "--user-id", str(user_id),
        "--account-id", str(account_id),
        "--page", str(page),
        "--size", str(size),
    ])


def fetch_balance(client_id: str, user_id: str, account_id: str) -> dict:
    return run_script("TPP_User_Account_Balance.py", [
        "--client-id", str(client_id),
        "--user-id", str(user_id),
        "--account-id", str(account_id),
    ])


_BALANCE_LABELS = {
    "CLBD": "Closing booked",
    "CLAV": "Closing available",
    "ITBD": "Interim booked",
    "ITAV": "Interim available",
    "OPBD": "Opening booked",
    "FWAV": "Forward available",
    "PRCD": "Previously closed",
    "XPCD": "Expected",
    "INFO": "Information",
    "AVAILABLE": "Available",
    "BOOKED": "Booked",
    "CURRENT": "Current",
}


def _format_money(value) -> str:
    text = str(value).strip().replace(" ", "").replace(",", ".")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return str(value).strip()
    sign = "-" if number < 0 else ""
    whole, fraction = f"{abs(number):.2f}".split(".")
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{sign}{' '.join(reversed(groups))},{fraction}"


def _balance_label(item: dict) -> str:
    raw = item.get("balanceType") or item.get("type") or item.get("nameI18N") or ""
    if isinstance(raw, dict):
        proprietary = raw.get("codeOrProprietary") if isinstance(raw.get("codeOrProprietary"), dict) else {}
        raw = raw.get("nameI18N") or raw.get("name") or raw.get("code") or proprietary.get("code") or proprietary.get("proprietary") or ""
    label = str(raw).strip()
    return _BALANCE_LABELS.get(label.upper(), label or "Balance")


def _balance_amount(item: dict) -> tuple[str, str]:
    currency = str(item.get("currency") or "")
    for key in ("balanceAmount", "amount", "availableAmount", "bookedAmount"):
        node = item.get(key)
        if node in (None, ""):
            continue
        if not isinstance(node, dict):
            return _format_money(node), currency
        nested = node.get("instructedAmount")
        if isinstance(nested, dict):
            node = nested
        amount = _first_present(node, ["value", "amount"])
        currency = str(_first_present(node, ["currency", "currencyCode"]) or currency)
        if amount != "":
            return _format_money(amount), currency
    amount = _first_present(item, ["value"])
    return (_format_money(amount), currency) if amount != "" else ("", currency)


def _balance_date(item: dict) -> str:
    for key in ("referenceDate", "dateTime", "valueDate", "date"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:10] if "T" in value else value.strip()
        if isinstance(value, dict):
            inner = value.get("dateTime") or value.get("date")
            if inner:
                return str(inner)[:10]
    return ""


def _balance_items(payload) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("balances", "balance", "accountBalances"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
    if any(key in payload for key in ("balanceAmount", "amount", "value", "balanceType")):
        return [payload]
    return []


def balance_entries(payload) -> list[dict[str, str]]:
    entries = []
    for item in _balance_items(payload):
        if not isinstance(item, dict):
            continue
        amount, currency = _balance_amount(item)
        indicator = str(item.get("creditDebitIndicator") or "").upper()
        if indicator in ("DBIT", "DEBIT") and amount and not amount.startswith("-"):
            amount = f"-{amount}"
        if not amount and not currency:
            continue
        value = amount or "—"
        if currency:
            value = f"{value} {currency}"
        entries.append({
            "label": _balance_label(item),
            "amount": amount or "—",
            "currency": currency,
            "date": _balance_date(item),
            "value": value,
            "role": "",
        })
    available_labels = {"Closing available", "Interim available", "Available", "Forward available"}
    available_index = next((index for index, entry in enumerate(entries) if entry["label"] in available_labels), 0 if entries else -1)
    for index, entry in enumerate(entries):
        entry["role"] = "available" if index == available_index else "other"
    return entries


def build_payment_body(
    instruction_id: str,
    amount: str,
    currency: str,
    requested_execution_date: str,
    debtor_iban: str,
    creditor_iban: str,
    creditor_currency: str,
    unstructured: str,
    variable_symbol: str,
    specific_symbol: str,
    constant_symbol: str,
    note_for_requestor: str,
    note_for_bank: str,
    narrative: str,
    instruction_priority: str = "NORM",
) -> dict:
    references = [
        f"VS:{variable_symbol}" if variable_symbol else "",
        f"SS:{specific_symbol}" if specific_symbol else "",
        f"KS:{constant_symbol}" if constant_symbol else "",
    ]
    return {
        "paymentIdentification": {"instructionIdentification": instruction_id},
        "paymentTypeInformation": {
            "instructionPriority": (instruction_priority or "NORM").strip().upper(),
            "serviceLevel": {"code": "DMCT"},
        },
        "amount": {"instructedAmount": {"value": float(amount), "currency": currency}},
        "requestedExecutionDate": requested_execution_date or date.today().isoformat(),
        "debtorAccount": {"identification": {"iban": debtor_iban}, "currency": currency},
        "creditorAccount": {"identification": {"iban": creditor_iban}, "currency": creditor_currency},
        "remittanceInformation": {
            "unstructured": unstructured,
            "structured": {"creditorReferenceInformation": {"reference": [item for item in references if item]}},
        },
        "x-paymentNotes": {
            "noteForRequestor": note_for_requestor,
            "noteForBank": note_for_bank,
            "narrative": narrative,
        },
    }


def create_payment(client_id: str, user_id: str, payment_body: dict) -> dict:
    return run_script("TPP_User_Create_Payment.py", [
        "--client-id", str(client_id),
        "--user-id", str(user_id),
        "--payment-json", json.dumps(payment_body, ensure_ascii=False),
    ])


def _payments_file() -> Path:
    return get_database_file("tpp_payments.json")


def load_created_payments() -> list[dict]:
    path = _payments_file()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    payments = data.get("payments") if isinstance(data, dict) else data
    if not isinstance(payments, list):
        return []
    return [_normalize_payment(payment) for payment in payments if isinstance(payment, dict)]


def _normalize_payment(payment: dict) -> dict:
    normalized = {column: payment.get(column, "") for column in PAYMENT_COLUMNS}
    for key, value in payment.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


def delete_local_payment(index: int) -> bool:
    payments = load_created_payments()
    if index < 0 or index >= len(payments):
        return False
    if str(payments[index].get("status") or "").strip().upper() != "DRAFT":
        return False
    del payments[index]
    return _save_payments(payments)


def _save_payments(payments: list[dict]) -> bool:
    path = _payments_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"payments": [_normalize_payment(payment) for payment in payments]}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def _find_nested(data, keys: list[str], default=""):
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if value not in (None, "") and not isinstance(value, (dict, list)):
                return value
        for value in data.values():
            found = _find_nested(value, keys, default=None)
            if found not in (None, ""):
                return found
    if isinstance(data, list):
        for item in data:
            found = _find_nested(item, keys, default=None)
            if found not in (None, ""):
                return found
    return default


def save_created_payment(
    payment_body: dict,
    payment_response: dict,
    account_id: str = "",
    party_id: str = "",
    replace_index: int | None = None,
    status_override: str = "",
) -> bool:
    instructed = (payment_body.get("amount") or {}).get("instructedAmount") or {}
    debtor = (payment_body.get("debtorAccount") or {}).get("identification") or {}
    creditor = (payment_body.get("creditorAccount") or {}).get("identification") or {}
    record = {
        "instructionIdentification": (payment_body.get("paymentIdentification") or {}).get("instructionIdentification", ""),
        "transactionIdentification": _find_nested(payment_response, ["transactionIdentification", "transactionId", "paymentId", "id"]),
        "amount + currency": f"{instructed.get('value', '')} {instructed.get('currency', '')}".strip(),
        "requestedExecutionDate": payment_body.get("requestedExecutionDate", ""),
        "dateCreated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": status_override or _find_nested(payment_response, ["status", "instructionStatus", "paymentStatus", "transactionStatus", "state"]),
        "code": _find_nested(payment_response, ["code"]),
        "instructionPriority": ((payment_body.get("paymentTypeInformation") or {}).get("instructionPriority") or ""),
        "signId": _find_nested(payment_response, ["signId", "signID", "signatureId"]),
        "debtorAccountId": str(account_id or ""),
        "debtorIban": debtor.get("iban", ""),
        "creditorIban": creditor.get("iban", ""),
        "partyId": str(party_id or ""),
        "requestBody": payment_body,
    }
    payments = load_created_payments()
    if replace_index is not None and 0 <= replace_index < len(payments):
        record["dateCreated"] = payments[replace_index].get("dateCreated") or record["dateCreated"]
        payments[replace_index] = record
    else:
        payments.append(record)
    return _save_payments(payments)


def _payment_from_account(payment: dict, account_id: str, debtor_iban: str) -> bool:
    saved_id = cell(payment.get("debtorAccountId") or payment.get("accountId"))
    saved_iban = cell(payment.get("debtorIban")).replace(" ", "").upper()
    wanted_iban = cell(debtor_iban).replace(" ", "").upper()
    if account_id and saved_id == str(account_id):
        return True
    if wanted_iban and saved_iban == wanted_iban:
        return True
    return False


def _payment_tone(status) -> str:
    value = cell(status).strip()
    if not value:
        return ""
    if value in {"ACSC", "ASCS"}:
        return "settled"
    if value == "CANC":
        return "cancelled"
    if value == "DRAFT":
        return "draft"
    return "other"


def account_payment_records(account_id: str, debtor_iban: str) -> list[dict[str, str]]:
    records = []
    for index, payment in enumerate(load_created_payments()):
        if not _payment_from_account(payment, account_id, debtor_iban):
            continue
        records.append({
            "index": str(index),
            "instructionIdentification": cell(payment.get("instructionIdentification")),
            "transactionIdentification": cell(payment.get("transactionIdentification")),
            "amount": cell(payment.get("amount + currency")),
            "requestedExecutionDate": cell(payment.get("requestedExecutionDate")),
            "dateCreated": cell(payment.get("dateCreated")),
            "status": cell(payment.get("status")),
            "tone": _payment_tone(payment.get("status")),
            "code": cell(payment.get("code")),
            "instructionPriority": cell(payment.get("instructionPriority")),
            "signId": cell(payment.get("signId")),
            "debtorAccountId": cell(payment.get("debtorAccountId") or payment.get("accountId")),
            "debtorIban": cell(payment.get("debtorIban")),
            "creditorIban": cell(payment.get("creditorIban")),
            "partyId": cell(payment.get("partyId")),
            "detail": pretty(payment),
            "blank": "",
        })
    return records


def payment_table() -> dict:
    payments = load_created_payments()
    labels = []
    rows = []
    for index, payment in enumerate(payments):
        parts = [f"{index + 1}."]
        if payment.get("transactionIdentification"):
            parts.append(f"id: {payment.get('transactionIdentification')}")
        if payment.get("instructionIdentification"):
            parts.append(f"instruction: {payment.get('instructionIdentification')}")
        if payment.get("amount + currency"):
            parts.append(str(payment.get("amount + currency")))
        if payment.get("status"):
            parts.append(f"status: {payment.get('status')}")
        labels.append(" | ".join(parts))
        rows.append([cell(payment.get(column, "")) for column in PAYMENT_COLUMNS])
    return {"labels": labels, "rows": rows}


def _extract_payment_status(action_response, raw_output: str) -> str:
    keys = [
        "status", "instructionStatus", "paymentStatus", "paymentInformationStatus",
        "transactionStatus", "transactionStatusCode", "state", "paymentState", "authorizationStatus",
    ]
    status = _find_nested(action_response, keys) if action_response else ""
    if status:
        return str(status)
    if not raw_output:
        return ""
    for key in keys:
        match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', raw_output, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    marker = "📄 Response Body (text):"
    if marker in raw_output:
        text_body = raw_output.split(marker, 1)[1].strip()
        first_line = text_body.splitlines()[0].strip() if text_body else ""
        if first_line and not first_line.startswith("="):
            return first_line
    return ""


def run_payment_action(client_id: str, user_id: str, action: str, index: int) -> dict:
    payments = load_created_payments()
    if index < 0 or index >= len(payments):
        return {"ok": False, "message": "Payment was not found.", "output": "", "request_id": "", "table": payment_table()}
    payment = payments[index]
    args = [
        "--client-id", str(client_id),
        "--user-id", str(user_id),
        "--action", action,
        "--payment-id", str(payment.get("transactionIdentification") or ""),
    ]
    if payment.get("signId"):
        args.extend(["--sign-id", str(payment.get("signId"))])
    result = run_script("TPP_User_Payment_Action.py", args)
    response_data = extract_json(result["output"]) if result["output"] else None
    output = pretty(response_data) if response_data else (result["output"] or result["error"])
    message = f"Payment {action} completed." if result["success"] else f"Payment {action} failed."
    if result["success"]:
        if action == "delete":
            payments[index]["status"] = "CANC"
            _save_payments(payments)
        else:
            status = _extract_payment_status(response_data, result["output"])
            if status and index < len(payments):
                payments[index]["status"] = status
                _save_payments(payments)
            elif action == "status":
                message += " Status response did not contain a recognizable status."
            if action == "authorize":
                status_args = [
                    "--client-id", str(client_id),
                    "--user-id", str(user_id),
                    "--action", "status",
                    "--payment-id", str(payment.get("transactionIdentification") or ""),
                ]
                if payment.get("signId"):
                    status_args.extend(["--sign-id", str(payment.get("signId"))])
                status_result = run_script("TPP_User_Payment_Action.py", status_args)
                status_data = extract_json(status_result["output"]) if status_result["output"] else None
                if status_result["success"]:
                    latest = _extract_payment_status(status_data, status_result["output"])
                    if latest and index < len(load_created_payments()):
                        refreshed = load_created_payments()
                        if index < len(refreshed):
                            refreshed[index]["status"] = latest
                            _save_payments(refreshed)
                    if status_data:
                        output += "\n\nLatest status response:\n" + pretty(status_data)
    return {
        "ok": result["success"],
        "message": message,
        "output": output,
        "request_id": result.get("request_id") or "",
        "table": payment_table(),
    }


def refresh_access_token(client_id: str, user_id: str) -> dict:
    return run_script(
        "TPP_GetTokenFromRefreshToken.py",
        ["--client-id", str(client_id), "--user-id", str(user_id)],
        capture=True,
    )


def login_user_to_ib(user_id: str) -> dict:
    result = run_script("IB_User_Login.py", ["--user-id", str(user_id)], capture=False)
    if result["success"]:
        return {"ok": True, "message": "Internet Banking login finished."}
    if result["error"]:
        return {"ok": False, "message": f"Internet Banking login failed. {result['error'][:240]}"}
    return {"ok": False, "message": f"Internet Banking login finished with exit code {result['returncode']}."}


def authorize_tpp_user(client_id: str, user_id: str) -> dict:
    result = run_script(
        "TPP_User_Authorization.py",
        ["--client-id", str(client_id), "--user-id", str(user_id)],
        capture=False,
    )
    if result["success"]:
        return {"ok": True, "message": "Authorization finished."}
    if result["error"]:
        return {"ok": False, "message": f"Authorization failed. {result['error'][:240]}"}
    return {"ok": False, "message": f"Authorization finished with exit code {result['returncode']}."}


def authorize_and_exchange(client_id: str, user_id: str) -> dict:
    auth = run_script(
        "TPP_User_Authorization.py",
        ["--client-id", str(client_id), "--user-id", str(user_id)],
        capture=False,
    )
    if not auth["success"]:
        return {"ok": False, "message": f"Authorization finished with exit code {auth['returncode']}."}
    token = run_script(
        "TPP_GetTokenFromCode.py",
        ["--client-id", str(client_id), "--user-id", str(user_id)],
        capture=False,
    )
    if token["success"]:
        return {"ok": True, "message": "Authorization and token exchange completed."}
    return {"ok": False, "message": f"Token exchange finished with exit code {token['returncode']}."}


def log_entry(message: str, level: str = "info", request_id: str = "") -> dict[str, str]:
    color = {"error": "red", "warning": "orange", "success": "green"}.get(level, "blue")
    request_id = (request_id or request_id_from_text(message)).strip()
    if not _UUID_RE.fullmatch(request_id):
        request_id = ""
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "message": message,
        "color": color,
        "request_id": request_id,
        "kibana_url": kibana_request_url(request_id),
    }


def log_line(message: str, level: str = "info", request_id: str = "") -> dict[str, str]:
    return log_entry(message, level, request_id)


async def prepare_accounts(client_id: str, user_id: str) -> dict:
    logs = [log_line(f"Checking token status for client_id: {client_id}, user_id: {user_id}")]
    status = await asyncio.to_thread(check_token_status, client_id, user_id)
    refresh_error = ""
    account_data = None
    raw_output = ""

    if status["access_ready"]:
        logs.append(log_line("Access token is valid and ready"))
        logs.append(log_line("Fetching account list..."))
        result = await asyncio.to_thread(fetch_accounts, client_id, user_id)
        raw_output = result["output"] or result["error"]
        request_id = result_request_id(result)
        if result["success"]:
            account_data = extract_json(result["output"])
            logs.append(log_line("Account list fetched" if account_data else "Could not parse JSON from response", "info" if account_data else "warning", request_id))
        elif is_service_unavailable(f"{result['error']}\n{result['output']}"):
            status = _unavailable_status()
            logs.append(log_line("Service unavailable", "error", request_id))
        else:
            logs.append(log_line(f"Failed to fetch accounts: {result['error']}", "error", request_id))
    elif status["refresh_ready"]:
        logs.append(log_line("Access token expired, but refresh token is valid"))
        logs.append(log_line("Refreshing access token..."))
        refresh = await asyncio.to_thread(refresh_access_token, client_id, user_id)
        if refresh["success"]:
            logs.append(log_line("Token refreshed"))
            status = await asyncio.to_thread(check_token_status, client_id, user_id)
            if status["access_ready"]:
                result = await asyncio.to_thread(fetch_accounts, client_id, user_id)
                raw_output = result["output"] or result["error"]
                request_id = result_request_id(result)
                if result["success"]:
                    account_data = extract_json(result["output"])
                    logs.append(log_line("Account list fetched" if account_data else "Could not parse JSON from response", "info" if account_data else "warning", request_id))
                elif is_service_unavailable(f"{result['error']}\n{result['output']}"):
                    status = _unavailable_status()
                    logs.append(log_line("Service unavailable", "error", request_id))
                else:
                    logs.append(log_line(f"Failed to fetch accounts: {result['error']}", "error", request_id))
            elif status["status"] == "unavailable":
                logs.append(log_line("Service unavailable", "error"))
            else:
                logs.append(log_line("Token refresh did not produce a valid access token", "error"))
        elif is_service_unavailable(f"{refresh['error']}\n{refresh['output']}"):
            status = _unavailable_status()
            logs.append(log_line("Service unavailable", "error"))
        else:
            refresh_error = "\n".join(part for part in (refresh["error"], refresh["output"]) if part)
            logs.append(log_line(f"Token refresh failed: {(refresh_error or 'unknown error')[:300]}", "error"))
    elif status["status"] == "unavailable":
        logs.append(log_line("Service unavailable", "error"))
    else:
        logs.append(log_line("No valid tokens found", "error"))
        logs.append(log_line("Authorization flow required"))

    rows, labels, payloads = account_rows_from_response(account_data) if account_data else ([], [], [])
    view_status = status["status"]
    if view_status == "ready" and not account_data:
        view_status = "error"
    return {
        "logs": logs,
        "status": view_status,
        "status_text": status["text"],
        "rows": rows,
        "labels": labels,
        "payloads": payloads,
        "cards": account_cards_from_payloads(payloads),
        "json": pretty(account_data) if account_data else "",
        "output": "" if account_data else raw_output,
        "refresh_error": refresh_error,
    }


def account_from_payload(payload: str) -> dict:
    try:
        data = json.loads(payload)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def account_iban(payload: str) -> str:
    account = account_from_payload(payload)
    identification = account.get("identification") if isinstance(account.get("identification"), dict) else {}
    return identification.get("iban") or ""


def account_id(payload: str) -> str:
    return str(account_from_payload(payload).get("id") or "").strip()


def account_currency(payload: str) -> str:
    return account_from_payload(payload).get("currency") or "CZK"


def _user_accounts_key(party_id: str, iban: str, currency: str) -> tuple[str, str, str]:
    return (
        str(party_id or "").strip(),
        str(iban or "").replace(" ", "").upper(),
        str(currency or "").strip().upper(),
    )


def load_user_accounts() -> list[dict]:
    path = get_database_file("user_accounts.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    accounts = data.get("accounts") if isinstance(data, dict) else None
    if not isinstance(accounts, list):
        return []
    return [item for item in accounts if isinstance(item, dict)]


def creditor_account_choices(debtor_iban: str) -> list[dict[str, str]]:
    """Saved accounts except the account the payment is sent from."""
    debtor = str(debtor_iban or "").replace(" ", "").upper()
    choices = []
    for account in load_user_accounts():
        iban = str(account.get("iban") or "").strip()
        if not iban or iban.replace(" ", "").upper() == debtor:
            continue
        currency = str(account.get("currency") or "").strip()
        name = str(account.get("partyName") or "").strip() or str(account.get("partyId") or "").strip() or "Account"
        label = f"{name} · {iban}" + (f" · {currency}" if currency else "")
        choices.append({"label": label, "iban": iban, "currency": currency})
    return choices


def save_missing_user_accounts(party_id: str, party_name: str, payloads: list[str]) -> dict[str, int]:
    """Store loaded accounts that are not already saved for this party, IBAN, and currency."""
    existing = load_user_accounts()
    known = {
        _user_accounts_key(item.get("partyId"), item.get("iban"), item.get("currency"))
        for item in existing
    }
    added = 0
    party = str(party_id or "").strip()
    name = str(party_name or "").strip()
    for payload in payloads:
        account = account_from_payload(payload)
        identification = account.get("identification") if isinstance(account.get("identification"), dict) else {}
        iban = str(identification.get("iban") or "").strip()
        currency = str(account.get("currency") or "").strip()
        key = _user_accounts_key(party, iban, currency)
        if not party or not key[1] or key in known:
            continue
        existing.append({
            "partyId": party,
            "partyName": name,
            "iban": iban,
            "currency": currency,
        })
        known.add(key)
        added += 1
    if added:
        path = get_database_file("user_accounts.json")
        path.write_text(
            json.dumps({"accounts": existing}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return {"added": added, "total": len(payloads)}


def account_detail_fields(payload: str) -> dict[str, str]:
    account = account_from_payload(payload)
    identification = account.get("identification") if isinstance(account.get("identification"), dict) else {}
    servicer = account.get("servicer") if isinstance(account.get("servicer"), dict) else {}
    relationship = account.get("relationship") if isinstance(account.get("relationship"), dict) else {}
    if not relationship and isinstance(account.get("realtionship"), dict):
        relationship = account.get("realtionship")
    owner = ""
    if relationship:
        owner = "Owner" if relationship.get("isOwner") else "Disponent"
    return {
        "name": str(account.get("nameI18N") or account.get("productI18N") or "Account"),
        "product": str(account.get("productI18N") or ""),
        "iban": str(identification.get("iban") or ""),
        "number": str(identification.get("other") or ""),
        "currency": str(account.get("currency") or ""),
        "id": str(account.get("id") or "").strip(),
        "bank": str(servicer.get("bankCode") or ""),
        "bic": str(servicer.get("bic") or ""),
        "country": str(servicer.get("countryCode") or ""),
        "owner": owner,
    }


_CARD_GRADIENTS = {
    "CZK": "linear-gradient(145deg, #312e81 0%, #4f46e5 58%, #818cf8 100%)",
    "EUR": "linear-gradient(145deg, #134e4a 0%, #0f766e 55%, #2dd4bf 100%)",
    "USD": "linear-gradient(145deg, #1e3a5f 0%, #1d4ed8 55%, #60a5fa 100%)",
}
_CARD_GRADIENT_FALLBACKS = [
    "linear-gradient(145deg, #3b1d5a 0%, #7e22ce 52%, #c084fc 100%)",
    "linear-gradient(145deg, #1e293b 0%, #334155 55%, #94a3b8 100%)",
]


def account_cards_from_payloads(payloads: list[str]) -> list[dict[str, str]]:
    cards = []
    for index, payload in enumerate(payloads):
        account = account_from_payload(payload)
        identification = account.get("identification") if isinstance(account.get("identification"), dict) else {}
        currency = str(account.get("currency") or "").strip()
        gradient = _CARD_GRADIENTS.get(currency) or _CARD_GRADIENT_FALLBACKS[index % len(_CARD_GRADIENT_FALLBACKS)]
        cards.append({
            "index": str(index),
            "name": str(account.get("nameI18N") or account.get("productI18N") or "Account"),
            "iban": str(identification.get("iban") or ""),
            "number": str(identification.get("other") or ""),
            "currency": currency,
            "id": str(account.get("id") or "").strip(),
            "gradient": gradient,
        })
    return cards
