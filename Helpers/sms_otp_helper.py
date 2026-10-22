"""
Helper for retrieving SMS OTP from OBO-SMC API
Based on TypeScript implementation in TypeScript/helpers/smsOtpHelper.ts
"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
from urllib.parse import urlencode
from typing import Any, Dict, List, Optional

import requests
import urllib3

try:
    # Optional: only needed if you want the Playwright-based functions.
    from playwright.sync_api import APIRequestContext  # type: ignore
except Exception:  # pragma: no cover
    APIRequestContext = Any  # type: ignore

# Load Entra credentials from configuration file
def _load_entra_config():
    """Load Entra ID configuration from environment-specific Configurations/{ENV}/entra_config.json"""
    import sys
    from pathlib import Path
    
    # Add project root to path for imports
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    from Helpers.environment_config import get_entra_config_file, get_current_environment
    
    config_path = get_entra_config_file()
    
    if not config_path.exists():
        current_env = get_current_environment()
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please create Configurations/{current_env}/entra_config.json with your Entra ID credentials."
        )
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Validate required fields
    required_fields = ["tenant_id", "client_id", "client_secret", "component_client_id", 
                       "employee_username", "employee_password"]
    missing_fields = [field for field in required_fields if field not in config]
    if missing_fields:
        raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
    
    return config

# Don't load ENTRA_CONFIG at module level - load it dynamically based on current environment
def get_entra_config():
    """Get Entra config for the current environment (lazy loading)"""
    return _load_entra_config()

# Import environment config
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from Helpers.environment_config import get_obo_smc_base_url
from Helpers.employee_token_retriever import get_employee_token_requests


def generate_request_id(username: str = "jbartosek") -> str:
    """Generate a request ID"""
    return f"{username}-{int(time.time() * 1000)}"


def generate_employee_token(api_request_context: APIRequestContext) -> str:
    """
    Generate Employee Token for OBO API access
    """
    print("\n🔑 Generating Employee Token...")
    
    entra_config = get_entra_config()
    token_url = f"https://login.microsoftonline.com/{entra_config['tenant_id']}/oauth2/v2.0/token"
    
    # Prepare form data as URL-encoded string
    form_data = {
        "client_id": entra_config["client_id"],
        "client_secret": entra_config["client_secret"],
        "grant_type": "password",
        "scope": f"{entra_config['component_client_id']}/api",
        "username": entra_config["employee_username"],
        "password": entra_config["employee_password"]
    }
    
    # URL-encode the form data
    form_data_encoded = urlencode(form_data)
    
    response = api_request_context.post(
        token_url,
        data=form_data_encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    
    if response.status != 200:
        error_body = ""
        try:
            error_body = response.text()
        except:
            pass
        raise Exception(f"Failed to generate Employee Token: Status {response.status}, Response: {error_body}")
    
    body = response.json()
    if "access_token" not in body:
        raise Exception(f"Token response missing access_token. Response: {body}")
    token = body["access_token"]
    
    print("✅ Employee Token generated")
    return token


def _format_iso_utc(dt: datetime) -> str:
    iso_str = dt.isoformat()
    if iso_str.endswith("+00:00"):
        return iso_str[:-6] + "Z"
    return iso_str


def fetch_sms_otps_requests(
    *,
    created_from: datetime,
    created_to: datetime,
    employee_token: str,
    verify_ssl: bool = False,
    timeout_seconds: int = 30,
) -> List[Dict[str, Any]]:
    """
    Fetch OTP messages from OBO-SMC using requests.
    """
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    resp = requests.get(
        f"{get_obo_smc_base_url()}/v1/sms/otp",
        params={
            "createdFrom": _format_iso_utc(created_from),
            "createdTo": _format_iso_utc(created_to),
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-request-id": generate_request_id(),
            "Authorization": f"Bearer {employee_token}",
        },
        verify=verify_ssl,
        timeout=timeout_seconds,
    )

    if resp.status_code != 200:
        raise Exception(f"OTP API failed: HTTP {resp.status_code}: {resp.text}")

    body = resp.json()
    if not isinstance(body, list):
        raise Exception(f"Unexpected OTP API response format: {type(body).__name__}")

    return body


def list_party_otps_requests(
    *,
    party_id: int,
    time_range_minutes: int = 30,
    verify_ssl: bool = False,
    timeout_seconds: int = 30,
) -> List[Dict[str, Any]]:
    """
    List OTP messages for a partyId (no polling), using requests.
    """
    now = datetime.now(timezone.utc)
    minutes_ago = now - timedelta(minutes=time_range_minutes)

    token = get_employee_token_requests(verify_ssl=verify_ssl, timeout_seconds=timeout_seconds)
    sms_array = fetch_sms_otps_requests(
        created_from=minutes_ago,
        created_to=now,
        employee_token=token,
        verify_ssl=verify_ssl,
        timeout_seconds=timeout_seconds,
    )

    otps = [sms for sms in sms_array if sms.get("partyId") == party_id]
    otps.sort(
        key=lambda x: datetime.fromisoformat(str(x.get("createdAt", "")).replace("Z", "+00:00"))
        if x.get("createdAt")
        else datetime.fromtimestamp(0, tz=timezone.utc),
        reverse=True,
    )
    return otps


def wait_for_sms_otp_requests(
    *,
    party_id: int,
    timeout_seconds: int = 60,
    poll_interval_seconds: float = 2.0,
    time_range_minutes: int = 5,
    verify_ssl: bool = False,
    timeout_http_seconds: int = 30,
) -> str:
    """
    Poll until the latest ACTIVE OTP for party_id is available (requests-based).
    """
    deadline = time.time() + timeout_seconds

    while True:
        otps = list_party_otps_requests(
            party_id=party_id,
            time_range_minutes=time_range_minutes,
            verify_ssl=verify_ssl,
            timeout_seconds=timeout_http_seconds,
        )
        active = [o for o in otps if o.get("otpStatus") == "ACTIVE"]
        if active:
            latest = active[0]
            otp_value = (latest.get("smsData") or {}).get("otpValue")
            if otp_value:
                return str(otp_value)

        if time.time() >= deadline:
            raise Exception(f"SMS OTP not received after {timeout_seconds} seconds")

        time.sleep(poll_interval_seconds)


def get_sms_otp(
    api_request_context: APIRequestContext,
    party_id: int,
    max_attempts: int = 30,
    poll_interval: int = 2000,
    time_range_minutes: int = 5,
    employee_token: str = None
) -> str:
    """
    Get the latest active SMS OTP for a given partyId
    Polls the API until SMS arrives (or timeout expires)
    
    Args:
        api_request_context: Playwright API request context
        party_id: Party ID to search for
        max_attempts: Maximum number of polling attempts (default: 30)
        poll_interval: Interval between attempts in milliseconds (default: 2000)
        time_range_minutes: Time range for searching SMS in minutes (default: 5)
        employee_token: Optional token (if not provided, generates a new one)
    
    Returns:
        OTP code as string
    
    Raises:
        Exception: If SMS OTP not received after max attempts
    """
    print("\n📱 Waiting for SMS OTP...")
    print(f"   Party ID: {party_id}")
    print(f"   Max attempts: {max_attempts}")
    print(f"   Poll interval: {poll_interval}ms")
    print(f"   Time range: {time_range_minutes} minutes back")
    
    # Generate token if not provided
    if not employee_token:
        employee_token = generate_employee_token(api_request_context)
    
    # Time range - last X minutes
    now = datetime.now(timezone.utc)
    minutes_ago = now - timedelta(minutes=time_range_minutes)
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n🔄 Attempt {attempt}/{max_attempts}...")
        print(f"   🕐 Time range: {_format_iso_utc(minutes_ago)} → {_format_iso_utc(now)}")
        
        try:
            # Request config
            request_id = generate_request_id()
            response = api_request_context.get(
                f"{get_obo_smc_base_url()}/v1/sms/otp",
                params={
                    "createdFrom": _format_iso_utc(minutes_ago),
                    "createdTo": _format_iso_utc(now)
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "x-request-id": request_id,
                    "Authorization": f"Bearer {employee_token}"
                }
            )
            
            if response.status != 200:
                error_body = ""
                try:
                    error_body = response.text()
                except:
                    pass
                print(f"   ⚠️ API returned status {response.status}")
                if error_body:
                    print(f"   Error response: {error_body[:200]}")  # First 200 chars
                if attempt < max_attempts:
                    time.sleep(poll_interval / 1000.0)
                continue
            
            sms_array = response.json()
            
            if not isinstance(sms_array, list):
                print("   ⚠️ Invalid response format")
                if attempt < max_attempts:
                    time.sleep(poll_interval / 1000.0)
                continue
            
            print(f"   📊 Found {len(sms_array)} SMS messages")
            
            # Debug: Show all partyIds in response
            party_ids = list(set([sms.get("partyId") for sms in sms_array if sms.get("partyId")]))
            print(f"   📋 Unique partyIds in response: {', '.join(map(str, party_ids))}")
            print(f"   🎯 Looking for partyId: {party_id} (type: {type(party_id).__name__})")
            
            # Filter only ACTIVE SMS for the given partyId
            active_sms_for_party = [
                sms for sms in sms_array
                if sms.get("partyId") == party_id and sms.get("otpStatus") == "ACTIVE"
            ]
            
            # Debug: Log matching SMS
            for sms in sms_array:
                if sms.get("partyId") == party_id:
                    matches = sms.get("partyId") == party_id and sms.get("otpStatus") == "ACTIVE"
                    print(f"   🔎 Found SMS for partyId {sms.get('partyId')}, status: {sms.get('otpStatus')}, matches: {matches}")
            
            print(f"   🔍 Active SMS for party {party_id}: {len(active_sms_for_party)}")
            
            if len(active_sms_for_party) == 0:
                print("   ⏳ No active SMS yet, waiting...")
                if attempt < max_attempts:
                    time.sleep(poll_interval / 1000.0)
                continue
            
            # Sort by createdAt descending (newest first)
            active_sms_for_party.sort(
                key=lambda x: datetime.fromisoformat(x["createdAt"].replace("Z", "+00:00")),
                reverse=True
            )
            
            # Get the latest
            latest_sms = active_sms_for_party[0]
            otp_value = latest_sms.get("smsData", {}).get("otpValue")
            
            if not otp_value:
                print("   ⚠️ SMS found but no OTP value")
                if attempt < max_attempts:
                    time.sleep(poll_interval / 1000.0)
                continue
            
            print("\n✅ SMS OTP found!")
            print(f"   OTP: {otp_value}")
            print(f"   Created: {latest_sms.get('createdAt')}")
            print(f"   SMS Code: {latest_sms.get('smsCode')}")
            
            return otp_value
            
        except Exception as error:
            print(f"   ❌ Error: {error}")
            import traceback
            traceback.print_exc()
        
        # Wait before next attempt (except for the last one)
        if attempt < max_attempts:
            time.sleep(poll_interval / 1000.0)
    
    raise Exception(f"SMS OTP not received after {max_attempts} attempts")


def wait_for_sms_otp(
    api_request_context: APIRequestContext,
    party_id: int,
    timeout_seconds: int = 60,
    time_range_minutes: int = 5
) -> str:
    """
    Simple wrapper - waits for SMS and returns OTP value
    Usage: otp = wait_for_sms_otp(request, party_id, 60, 5)
    """
    max_attempts = 5  # Poll up to 5 times (was: int(timeout_seconds / 2))
    return get_sms_otp(
        api_request_context,
        party_id,
        max_attempts=max_attempts,
        poll_interval=2000,
        time_range_minutes=time_range_minutes
    )


def _cli() -> int:
    import argparse
    import sys

    # Interactive mode: no parameters -> prompt for environment + user selection
    if len(sys.argv) == 1:
        return _cli_interactive()

    parser = argparse.ArgumentParser(description="Fetch SMS OTP codes from OBO-SMC for a partyId.")
    parser.add_argument("--party-id", type=int, required=True, help="Party ID (user id) to query OTPs for")
    parser.add_argument("--minutes", type=int, default=30, help="How many minutes back to search (default: 30)")
    parser.add_argument("--wait", action="store_true", help="Poll until an ACTIVE OTP is available")
    parser.add_argument("--timeout", type=int, default=60, help="Wait timeout seconds (default: 60)")
    parser.add_argument("--verify-ssl", action="store_true", help="Enable SSL verification")
    args = parser.parse_args()

    if args.wait:
        otp = wait_for_sms_otp_requests(
            party_id=args.party_id,
            timeout_seconds=args.timeout,
            time_range_minutes=args.minutes,
            verify_ssl=args.verify_ssl,
        )
        print(otp)
        return 0

    otps = list_party_otps_requests(
        party_id=args.party_id,
        time_range_minutes=args.minutes,
        verify_ssl=args.verify_ssl,
    )
    print(json.dumps(otps, indent=2, ensure_ascii=False))
    return 0


def _prompt_choice(prompt: str, options: List[str], default_index: int = 0) -> str:
    while True:
        print(f"\n{prompt}")
        for i, opt in enumerate(options, start=1):
            default_marker = " (default)" if (i - 1) == default_index else ""
            print(f"  {i}. {opt}{default_marker}")
        try:
            raw = input("> ").strip()
        except EOFError:
            # Non-interactive execution (e.g., CI/automation): fall back to default.
            print("\nWARNING: No interactive input available; using default.")
            return options[default_index]
        if raw == "":
            return options[default_index]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print("Invalid selection, try again.")


def _prompt_int(prompt: str, default: int, min_value: int = 1, max_value: int = 10**9) -> int:
    while True:
        try:
            raw = input(f"{prompt} (default {default}): ").strip()
        except EOFError:
            print("\nWARNING: No interactive input available; using default.")
            return default
        if raw == "":
            return default
        try:
            val = int(raw)
            if min_value <= val <= max_value:
                return val
        except ValueError:
            pass
        print("Invalid number, try again.")


def _prompt_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        try:
            raw = input(f"{prompt} [{suffix}]: ").strip().lower()
        except EOFError:
            print("\nWARNING: No interactive input available; using default.")
            return default
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please answer y or n.")


def _cli_interactive() -> int:
    import json as _json
    import sys as _sys
    from Helpers.environment_config import (
        get_current_environment,
        load_environment_config,
        set_environment,
        get_database_file,
    )

    if not _sys.stdin.isatty():
        print("ERROR: Interactive mode requires a real terminal (TTY).")
        print("Run this in a console, or pass --party-id for non-interactive use.")
        return 2

    cfg = load_environment_config()
    # Logical environment order: ITG → TST → PRE → PROD
    ENV_ORDER = ["ITG", "TST", "PRE", "PROD"]
    all_envs = list((cfg.get("environments") or {}).keys())
    # Sort by logical order, with any unknown environments at the end
    envs = sorted(all_envs, key=lambda e: (ENV_ORDER.index(e) if e in ENV_ORDER else 999, e))
    current_env = get_current_environment()
    default_env_idx = envs.index(current_env) if current_env in envs else 0

    selected_env = _prompt_choice("Select environment:", envs, default_index=default_env_idx)
    set_environment(selected_env)
    print(f"\nEnvironment set to: {selected_env}")

    users_path = get_database_file("users.json", selected_env)
    if not users_path.exists():
        print(f"\nWARNING: No users database found at: {users_path}")
        print("Add a user in the app first (Users page), or run with --party-id.")
        return 2

    try:
        users_db = _json.loads(users_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\nERROR: Failed to read users database: {users_path}\nError: {e}")
        return 2

    users = users_db.get("users") or []
    if not users:
        print(f"\nWARNING: No users found in: {users_path}")
        print("Add a user in the app first (Users page), or run with --party-id.")
        return 2

    # Build selection list
    user_labels: List[str] = []
    label_to_user: Dict[str, Dict[str, Any]] = {}
    for u in users:
        party_id = str(u.get("partyId", "")).strip()
        name = str(u.get("name", "")).strip() or "Unknown"
        username = str(u.get("username", "")).strip()
        label = f"{name} (partyId={party_id})" + (f" | {username}" if username else "")
        user_labels.append(label)
        label_to_user[label] = u

    chosen_label = _prompt_choice("Select user:", user_labels, default_index=0)
    chosen_user = label_to_user[chosen_label]
    party_id = int(str(chosen_user.get("partyId")).strip())

    minutes = _prompt_int("Search how many minutes back?", default=30, min_value=1, max_value=1440)
    wait = _prompt_yes_no("Wait/poll for ACTIVE OTP?", default=False)

    if wait:
        timeout = _prompt_int("Wait timeout (seconds)?", default=60, min_value=1, max_value=3600)
        otp = wait_for_sms_otp_requests(
            party_id=party_id,
            timeout_seconds=timeout,
            time_range_minutes=minutes,
            verify_ssl=False,
        )
        print(f"\nOTP: {otp}")
        return 0

    otps = list_party_otps_requests(
        party_id=party_id,
        time_range_minutes=minutes,
        verify_ssl=False,
    )
    print(_json.dumps(otps, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())

