"""
Interactive consent iterator.

Pick a user and a TPP, reuse a valid access token or refresh it, and start
authorization when neither is available. Then print the JWT, load consents
from CON, and run the Groovy consent parser.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Helpers.access_token_helper import decode_jwt_payload, is_token_expired
from Helpers.environment_config import get_show_invalid_consents
from Helpers.token_introspection_helper import is_refresh_token_valid
from Helpers.data_store import (
    get_client_credentials,
    load_registrations,
    load_tokens,
    load_users,
)
from psd2_app.logic import parse_consents_output

PARSER_SOURCE = Path(__file__).with_name("ConsentParser.groovy")
GROOVY_VERSION = "3.0.25"
GROOVY_CACHE = Path(tempfile.gettempdir()) / "creditas-groovy" / GROOVY_VERSION
GROOVY_JARS = (
    f"groovy-{GROOVY_VERSION}.jar",
    f"groovy-json-{GROOVY_VERSION}.jar",
)


def list_users():
    users = [user for user in load_users() if user.get("partyId")]
    users.sort(key=lambda user: (str(user.get("name") or "").lower(), str(user.get("partyId"))))
    return users


def list_tpps():
    clients = {}
    for registration in load_registrations():
        response = (registration.get("response") or {}).get("body") or {}
        request = (registration.get("request") or {}).get("body") or {}
        if not isinstance(response, dict):
            continue
        client_id = response.get("client_id")
        if not client_id:
            continue
        clients[client_id] = {
            "client_id": client_id,
            "client_name": request.get("client_name") or response.get("client_name") or client_id,
        }
    return sorted(clients.values(), key=lambda client: (client["client_name"].lower(), client["client_id"]))


def prompt_choice(title, items, render):
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print()
    for index, item in enumerate(items, 1):
        print(f"  [{index}] {render(item)}")
        print()
    while True:
        try:
            raw = input(f"Select (1-{len(items)}) or 'q' to quit: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return None
        if raw.lower() == "q":
            print("Cancelled.")
            return None
        try:
            number = int(raw)
        except ValueError:
            print("Enter a number or 'q'.")
            continue
        if 1 <= number <= len(items):
            return items[number - 1]
        print(f"Enter a number between 1 and {len(items)}.")


def refresh_is_valid(client_id, refresh_token):
    credentials = get_client_credentials(client_id)
    if not credentials or not credentials.get("client_secret"):
        print("Client secret is missing, refresh token cannot be checked.")
        return False
    print("Checking refresh token...")
    try:
        return is_refresh_token_valid(
            refresh_token,
            credentials["client_id"],
            credentials["client_secret"],
        )
    except Exception as exc:
        print(f"Refresh check failed: {exc}")
        return False


def run_request(script_name, client_id, user_id):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "Requests" / script_name),
            "--client-id",
            str(client_id),
            "--user-id",
            str(user_id),
        ],
        cwd=ROOT,
    )
    return completed.returncode == 0


def load_valid_access(client_id, user_id):
    for token in find_tokens(client_id, user_id):
        access = token.get("access_token") or ""
        if access and not is_token_expired(access):
            return access
    return None


def refresh_access_token(client_id, user_id):
    print("Access token is missing or expired. Refreshing...")
    if not run_request("TPP_GetTokenFromRefreshToken.py", client_id, user_id):
        print("Token refresh failed.")
        return None
    access = load_valid_access(client_id, user_id)
    if not access:
        print("Token refresh did not produce a valid access token.")
        return None
    print("Access token refreshed.")
    return access


def authorize(client_id, user_id):
    print("No valid access or refresh token. Starting authorization...")
    if not run_request("TPP_User_Authorization.py", client_id, user_id):
        print("Authorization failed.")
        return None
    print("Exchanging authorization code for an access token...")
    run_request("TPP_GetTokenFromCode.py", client_id, user_id)
    access = load_valid_access(client_id, user_id)
    if not access:
        print("Authorization did not produce a valid access token.")
        return None
    print("Access token issued.")
    return access


def find_tokens(client_id, user_id):
    return [
        token for token in load_tokens()
        if token.get("client_id") == client_id and str(token.get("user")) == str(user_id)
    ]


def describe_token(token):
    access = token.get("access_token") or ""
    payload = decode_jwt_payload(access) if access else None
    payload = payload or {}
    profiles = payload.get("bank_profile_ids") or []
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        valid_to = datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        valid_to = "n/a"
    access_valid = bool(access) and not is_token_expired(access)
    validity = valid_to if access_valid else f"access expired, refresh valid (was {valid_to})"
    return {
        "id": payload.get("jti") or "n/a",
        "scopes": payload.get("scope") or token.get("scope") or "n/a",
        "profiles": ", ".join(str(profile) for profile in profiles) or "n/a",
        "validity": validity,
    }


def usable_tokens(client_id, user_id):
    usable = []
    for token in find_tokens(client_id, user_id):
        access = token.get("access_token") or ""
        if access and not is_token_expired(access):
            usable.append({"record": token, "kind": "access"})
            continue
        refresh = token.get("refresh_token") or ""
        if refresh and refresh_is_valid(client_id, refresh):
            usable.append({"record": token, "kind": "refresh"})
    return usable


def resolve_access_token(client_id, user_id):
    usable = usable_tokens(client_id, user_id)
    if not usable:
        return authorize(client_id, user_id)
    if len(usable) == 1:
        chosen = usable[0]
    else:
        chosen = prompt_choice("VALID TOKENS", usable, render_token)
        if chosen is None:
            return None
    token = chosen["record"]
    if chosen["kind"] == "access":
        print(f"Access token is valid ({describe_token(token)['id']}).")
        return token.get("access_token")
    return refresh_access_token(client_id, user_id)


def groovy_classpath():
    GROOVY_CACHE.mkdir(parents=True, exist_ok=True)
    jars = []
    for name in GROOVY_JARS:
        path = GROOVY_CACHE / name
        if not path.exists() or path.stat().st_size < 10000:
            artifact = name[: -len(f"-{GROOVY_VERSION}.jar")]
            url = (
                "https://repo1.maven.org/maven2/org/codehaus/groovy/"
                f"{artifact}/{GROOVY_VERSION}/{name}"
            )
            print(f"Downloading {name}...")
            urllib.request.urlretrieve(url, path)
        jars.append(path)
    return os.pathsep.join(str(path) for path in jars)


def run_consent_parser(jwt, consents):
    """Compile ConsentParser and print its JSON result for this JWT and consent list."""
    java = shutil.which("java")
    if not java:
        print("Java was not found. The Groovy parser needs Java 8 or newer.")
        return None
    if not PARSER_SOURCE.exists():
        print(f"Groovy parser was not found: {PARSER_SOURCE}")
        return None

    classpath = groovy_classpath()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        jwt_file = work / "jwt.json"
        consents_file = work / "consents.json"
        classes = work / "classes"
        classes.mkdir()
        jwt_file.write_text(json.dumps(jwt, ensure_ascii=False), encoding="utf-8")
        consents_file.write_text(json.dumps(consents, ensure_ascii=False), encoding="utf-8")

        compile_run = subprocess.run(
            [
                java,
                "-cp",
                classpath,
                "org.codehaus.groovy.tools.FileSystemCompiler",
                "-d",
                str(classes),
                str(PARSER_SOURCE),
            ],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if compile_run.returncode != 0:
            print("Groovy parser failed to compile.")
            print((compile_run.stderr or compile_run.stdout or "").strip())
            return None

        completed = subprocess.run(
            [
                java,
                "-cp",
                classpath + os.pathsep + str(classes),
                "Helpers.groovy.consent_parser.ConsentParser",
                str(jwt_file),
                str(consents_file),
            ],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            print("Groovy parser failed.")
            print((completed.stderr or completed.stdout or "").strip())
            return None
        output = (completed.stdout or "").strip()
        if not output:
            print("Groovy parser returned no output.")
            return None
        return output


def fetch_user_consents(user_id):
    args = ["--user-id", str(user_id), "--owner-id", str(user_id)]
    if not get_show_invalid_consents():
        args.append("--valid-consents-only")
    completed = subprocess.run(
        [sys.executable, str(ROOT / "Requests" / "TPP_Consent_Get.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = completed.stdout or ""
    if "[CONSENTS_JSON_START]" not in output:
        status = next(
            (line.strip() for line in output.splitlines() if line.strip().startswith("Status:")),
            "",
        )
        return None, status or "Consent API call failed."
    return parse_consents_output(output), ""


def consents_for_tpp(consents, client_id):
    return [
        consent for consent in consents
        if str(consent.get("oauth2ClientId") or "") == str(client_id)
    ]


def print_consent_rows(consents, client_id):
    matched = consents_for_tpp(consents, client_id)
    ids = ", ".join(str(consent.get("consentId")) for consent in matched)
    relevant = f"{len(matched)} ({ids})" if ids else "0"
    print()
    print(f"Consents for user: {len(consents)}")
    print(f"Relevant for TPP: {relevant}")


def render_token(choice):
    info = describe_token(choice["record"])
    return (
        f"{info['id']}\n"
        f"      Scopes: {info['scopes']}\n"
        f"      Profiles: {info['profiles']}\n"
        f"      Valid to: {info['validity']}"
    )


def render_user(user):
    return (
        f"{user.get('name') or 'Unknown'}\n"
        f"      Party ID: {user.get('partyId')}\n"
        f"      Username: {user.get('username') or 'n/a'}"
    )


def render_tpp(client):
    return (
        f"{client['client_name']}\n"
        f"      Client ID: {client['client_id']}"
    )


def main():
    users = list_users()
    if not users:
        print("No users found.")
        return 1
    clients = list_tpps()
    if not clients:
        print("No TPP registrations found.")
        return 1

    user = prompt_choice("AVAILABLE USERS", users, render_user)
    if user is None:
        return 1
    client = prompt_choice("AVAILABLE TPP CLIENTS", clients, render_tpp)
    if client is None:
        return 1

    user_id = str(user.get("partyId"))
    client_id = client["client_id"]
    print()
    print(f"Selected: {user.get('name')} (Party ID {user_id}) / {client['client_name']}")

    access = resolve_access_token(client_id, user_id)
    if not access:
        return 1
    jwt = decode_jwt_payload(access)
    if not jwt:
        print("Access token could not be decoded.")
        return 1

    print()
    print("=" * 60)
    print("JWT")
    print("=" * 60)
    print(json.dumps(jwt, indent=2, ensure_ascii=False))

    consents, error = fetch_user_consents(user_id)
    if consents is None:
        print(error or "Consent API call failed.")
        return 1

    print_consent_rows(consents, client_id)
    print()
    print("=" * 60)
    print("CONSENT PARSER")
    print("=" * 60)
    result = run_consent_parser(jwt, consents)
    if result is None:
        return 1
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        print(result)
        return 1
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
