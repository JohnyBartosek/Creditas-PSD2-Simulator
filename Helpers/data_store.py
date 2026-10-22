"""Load and save the JSON database files for the current environment."""

import json
import logging
import os
from datetime import datetime, timezone

from Helpers.environment_config import get_database_file, load_token_config

logger = logging.getLogger(__name__)


def _report_error(message: str) -> None:
    logger.error(message)
    print(message)


def _database_file(name: str) -> str:
    return str(get_database_file(name))


def load_json_file(filepath):
    """Load a JSON file. Missing or unreadable files return an empty dict."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            _report_error(f"Error loading {filepath}: {exc}")
            return {}
    return {}


def save_json_file(filepath, data):
    """Save data to a JSON file."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        return True
    except Exception as exc:
        _report_error(f"Error saving {filepath}: {exc}")
        return False


def load_registrations():
    """Load TPP registrations."""
    data = load_json_file(_database_file("tpp_registrations.json"))
    return data.get("registrations", [])


def load_tokens():
    """Load tokens."""
    data = load_json_file(_database_file("tpp_tokens.json"))
    return data.get("tokens", [])


def load_users():
    """Load users."""
    data = load_json_file(_database_file("users.json"))
    return data.get("users", [])


def load_auth_config():
    """Load the default auth config."""
    return load_json_file(_database_file("default_auth_config.json"))


def _parse_auth_timestamp(value):
    text = str(value or "").strip()
    if not text:
        return None
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


def keep_valid_auth_codes(codes, expiration_seconds, now=None) -> list:
    """Return authorization codes that are still inside the expiration window."""
    moment = now or datetime.now(timezone.utc)
    kept = []
    for code in codes or []:
        if not isinstance(code, dict):
            continue
        if not str(code.get("authorization_code") or "").strip():
            continue
        created = _parse_auth_timestamp(code.get("timestamp"))
        if not created:
            continue
        if (moment - created).total_seconds() < expiration_seconds:
            kept.append(code)
    return kept


def prune_auth_codes(environment: str | None = None) -> tuple[int, int]:
    """Rewrite the environment file so it contains only unexpired codes."""
    from Helpers.file_lock_helper import safe_update_json

    path = str(get_database_file("last_authorization_code.json", environment))
    expiration = load_token_config(environment)["authorization_code_expiration_seconds"]
    stats = {"kept": 0, "removed": 0}

    def update(collection):
        if not isinstance(collection, dict):
            collection = {"authorization_codes": []}
        elif "authorization_codes" not in collection:
            collection = {"authorization_codes": [collection]} if collection.get("authorization_code") else {"authorization_codes": []}
        original = collection.get("authorization_codes") or []
        kept = keep_valid_auth_codes(original, expiration)
        stats["kept"] = len(kept)
        stats["removed"] = len(original) - len(kept)
        collection["authorization_codes"] = kept
        return collection

    safe_update_json(path, update, default_value={"authorization_codes": []})
    return stats["kept"], stats["removed"]


def load_auth_code(state: str = None):
    """Load one authorization code, or the most recent one."""
    data = load_auth_codes_collection()
    if "authorization_codes" in data:
        codes = data.get("authorization_codes", [])
        if not codes:
            return None
        if state:
            for entry in codes:
                if entry.get("state") == state:
                    return entry
            return None
        sorted_codes = sorted(codes, key=lambda item: item.get("timestamp", ""), reverse=True)
        return sorted_codes[0] if sorted_codes else None
    if state and data.get("state") != state:
        return None
    return data if data else None


def load_auth_codes_collection():
    """Load authorization codes and drop expired ones from the file."""
    path = _database_file("last_authorization_code.json")
    data = load_json_file(path)
    if "authorization_codes" in data:
        codes = data.get("authorization_codes") or []
    elif data:
        codes = [data]
    else:
        codes = []
    expiration = load_token_config()["authorization_code_expiration_seconds"]
    kept = keep_valid_auth_codes(codes, expiration)
    if len(kept) != len(codes):
        save_json_file(path, {"authorization_codes": kept})
    return {"authorization_codes": kept}


def save_users(users):
    """Save users to the current environment file."""
    return save_json_file(_database_file("users.json"), {"users": users})


def save_auth_config(config_data):
    """Save the default auth config."""
    return save_json_file(_database_file("default_auth_config.json"), config_data)


def load_consents():
    """Load consents."""
    data = load_json_file(_database_file("tpp_consents.json"))
    return data.get("consents", [])


def get_client_credentials(client_id: str):
    """Return client id and secret for a registered TPP."""
    for registration in load_registrations():
        response_body = registration.get("response", {}).get("body", {})
        if isinstance(response_body, dict) and response_body.get("client_id") == client_id:
            return {
                "client_id": response_body.get("client_id"),
                "client_secret": response_body.get("client_secret"),
            }
    return None
