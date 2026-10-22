"""
TPP User Account Transactions
Based on Bruno/PSD AccountTransactions.bru
Fetches transaction list for a selected account using access token from database
"""

import argparse
import json
import re
import sys
import io
from pathlib import Path
from urllib.parse import urlencode

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.environment_config import get_accounts_list_url
from Requests.TPP_User_Account_List import (
    DATABASE_FILE,
    USERS_FILE,
    X_CLIENT_CERTIFICATE,
    ensure_access_token,
    format_request_date,
    generate_request_id,
    get_client_name_by_id,
    get_user_by_party_id,
    load_database,
    load_default_auth_config,
    select_client,
    select_user,
)


def _party_id_from_user(selected_user):
    try:
        return int(selected_user.get("partyId"))
    except Exception:
        print(f"⚠️  Could not parse partyId '{selected_user.get('partyId')}' as integer")
        user_input = input("Enter User (Party ID) or press Enter to cancel: ").strip()
        if not user_input or not user_input.isdigit():
            print("❌ User (Party ID) is required")
            return None
        return int(user_input)


def _client_from_default_config(config_client_name):
    database = load_database()
    for registration in database.get("registrations", []):
        request_body = registration.get("request", {}).get("body", {})
        reg_client_name = request_body.get("client_name", "")
        if not reg_client_name:
            response_body = registration.get("response", {}).get("body", {})
            if isinstance(response_body, dict):
                reg_client_name = response_body.get("client_name", "")
        if reg_client_name != config_client_name:
            continue
        response_body = registration.get("response", {}).get("body", {})
        if isinstance(response_body, dict) and response_body.get("client_id"):
            return {
                "client_name": reg_client_name,
                "client_id": response_body.get("client_id"),
            }
    return None


def choose_client_and_user():
    """Console selection of TPP client and user, matching the account list script."""
    auth_config = load_default_auth_config()

    if not auth_config:
        print("=" * 60)
        print("CONSOLE MODE - SELECT CLIENT AND USER")
        print("=" * 60)
        print()
        selected_client = select_client()
        if not selected_client:
            return None
        print()
        selected_user = select_user()
        if not selected_user:
            return None
        user = _party_id_from_user(selected_user)
        if user is None:
            return None
        print(
            f"✅ Selected: Client={selected_client['client_name']}, "
            f"User={selected_user.get('name')} (Party ID: {user})"
        )
        return selected_client["client_id"], user

    config_party_id = auth_config.get("partyId")
    config_client_name = auth_config.get("client_id")
    print("=" * 60)
    print("CONSOLE MODE - USING DEFAULT CONFIG")
    print("=" * 60)
    print(f"Default Client: {config_client_name}")
    print(f"Default User (Party ID): {config_party_id}")
    print()
    use_default = input("Use default configuration? (Y/n): ").strip().lower()

    if use_default and use_default != "n":
        selected_client = _client_from_default_config(config_client_name)
        if not selected_client:
            print(f"❌ Could not find TPP client '{config_client_name}' in database!")
            print(f"   Database file: {DATABASE_FILE}")
            return None
        user_obj = get_user_by_party_id(config_party_id)
        if not user_obj:
            print(f"⚠️  Could not find user with partyId '{config_party_id}' in users database!")
            print(f"   Users file: {USERS_FILE}")
            print("   Please enter Party ID manually:")
            user_input = input("Enter User (Party ID): ").strip()
            if not user_input or not user_input.isdigit():
                print("❌ User (Party ID) is required")
                return None
            user = int(user_input)
        else:
            try:
                user = int(config_party_id)
                print(f"✅ Loaded user: {user_obj.get('name')} (Party ID: {config_party_id})")
            except Exception:
                print(f"⚠️  Could not parse partyId '{config_party_id}' as integer")
                user_input = input("Enter User (Party ID): ").strip()
                if not user_input or not user_input.isdigit():
                    print("❌ User (Party ID) is required")
                    return None
                user = int(user_input)
        return selected_client["client_id"], user

    print()
    print("Manual selection mode...")
    selected_client = select_client()
    if not selected_client:
        return None
    print()
    selected_user = select_user()
    if not selected_user:
        return None
    user = _party_id_from_user(selected_user)
    if user is None:
        return None
    print(
        f"✅ Selected: Client={selected_client['client_name']}, "
        f"User={selected_user.get('name')} (Party ID: {user})"
    )
    return selected_client["client_id"], user


def _account_summary(account: dict) -> str:
    identification = account.get("identification") or {}
    iban = identification.get("iban", "") if isinstance(identification, dict) else ""
    parts = [str(account.get("id", ""))]
    if iban:
        parts.append(iban)
    if account.get("currency"):
        parts.append(str(account.get("currency")))
    name = account.get("nameI18N") or account.get("productI18N")
    if name:
        parts.append(str(name))
    return "  ".join(part for part in parts if part)


def _load_accounts(client_id: str, user: int):
    access_token = ensure_access_token(client_id, user)
    if not access_token:
        return None

    client_name = get_client_name_by_id(client_id) or client_id
    sanitized_client_name = re.sub(r"[^\x20-\x7E]", "", str(client_name)).strip()
    url = f"{get_accounts_list_url()}?{urlencode({'page': 0, 'size': 100})}"
    headers = {
        "Content-Type": "application/json",
        "X-Request-ID": generate_request_id(),
        "X-Request-Date": format_request_date(),
        "User-Involved": "false",
        "TPP-Name": sanitized_client_name,
        "X-TPP-Authorization": f"Bearer {access_token}",
        "X-Client-Cert": X_CLIENT_CERTIFICATE,
    }

    print("📡 Loading accounts for selection...")
    with sync_playwright() as p:
        api_request_context = p.request.new_context(ignore_https_errors=True)
        try:
            response = api_request_context.get(url, headers=headers)
            if response.status != 200:
                print(f"⚠️  Account list request failed with status {response.status}")
                return None
            body = response.json()
            accounts = body.get("accounts", []) if isinstance(body, dict) else []
            return [account for account in accounts if isinstance(account, dict) and account.get("id")]
        except Exception as exc:
            print(f"⚠️  Could not load accounts: {exc}")
            return None
        finally:
            api_request_context.dispose()


def select_account(client_id: str, user: int):
    """Show accounts for the selected context and let the user pick one."""
    accounts = _load_accounts(client_id, user)
    if accounts is None:
        account_id = input("Enter Account ID or press Enter to cancel: ").strip()
        return account_id or None
    if not accounts:
        print("⚠️  No accounts returned.")
        account_id = input("Enter Account ID or press Enter to cancel: ").strip()
        return account_id or None

    print()
    print("=" * 60)
    print("AVAILABLE ACCOUNTS")
    print("=" * 60)
    print()
    for index, account in enumerate(accounts, 1):
        print(f"  [{index}] {_account_summary(account)}")
    print()

    while True:
        try:
            selection = input(f"Select account (1-{len(accounts)}) or 'q' to quit: ").strip()
            if selection.lower() == "q":
                print("❌ Cancelled by user")
                return None
            selection_num = int(selection)
            if 1 <= selection_num <= len(accounts):
                return str(accounts[selection_num - 1].get("id"))
            print(f"⚠️  Please enter a number between 1 and {len(accounts)}")
        except ValueError:
            print("⚠️  Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None


def test_get_account_transactions(
    client_id: str,
    user_id: str,
    account_id: str,
    page: int = 0,
    size: int = 100,
):
    """Fetch transactions for a selected account."""
    if not client_id:
        print("❌ Client ID is required")
        return

    if not user_id:
        print("❌ User (Party ID) is required")
        return

    if not account_id:
        print("❌ Account ID is required")
        return

    try:
        user = int(user_id)
    except Exception:
        print(f"⚠️  Invalid user_id provided: {user_id}. Must be an integer.")
        return

    access_token = ensure_access_token(client_id, user)
    if not access_token:
        return

    client_name = get_client_name_by_id(client_id) or client_id
    request_id = generate_request_id()
    request_date = format_request_date()
    url = f"{get_accounts_list_url().rstrip('/')}/{account_id}/transactions?{urlencode({'page': page, 'size': size})}"

    print("=" * 60)
    print("ACCOUNT TRANSACTIONS REQUEST")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Client ID: {client_id}")
    print(f"Client Name (TPP-Name): {client_name}")
    print(f"User (Party ID): {user}")
    print(f"Account ID: {account_id}")
    print(f"Page: {page}")
    print(f"Size: {size}")
    print(f"X-Request-ID: {request_id}")
    print(f"X-Request-Date: {request_date}")
    print("=" * 60)
    print()

    with sync_playwright() as p:
        api_request_context = p.request.new_context(ignore_https_errors=True)

        try:
            sanitized_client_name = re.sub(r"[^\x20-\x7E]", "", str(client_name)).strip()
            headers = {
                "Content-Type": "application/json",
                "X-Request-ID": request_id,
                "X-Request-Date": request_date,
                "User-Involved": "false",
                "TPP-Name": sanitized_client_name,
                "X-TPP-Authorization": f"Bearer {access_token}",
                "X-Client-Cert": X_CLIENT_CERTIFICATE,
            }

            print("📡 Making GET request to account transactions endpoint...")
            response = api_request_context.get(url, headers=headers)

            status = response.status
            print(f"\n📥 Response Status: {status}")
            print(f"📋 Response Headers: {dict(response.headers)}")

            try:
                response_body = response.json()
                print("\n📄 Response Body:")
                print(json.dumps(response_body, indent=2, ensure_ascii=False))

                if status == 200:
                    print("\n✅ Account transactions retrieved successfully!")
                else:
                    print(f"\n⚠️  Request failed with status {status}")
            except Exception:
                response_text = response.text()
                print("\n📄 Response Body (text):")
                print(response_text[:1000])

            print("\n" + "=" * 60)

        except Exception as e:
            print(f"\n❌ Request failed: {str(e)}")
            import traceback

            traceback.print_exc()
        finally:
            api_request_context.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Account Transactions")
    parser.add_argument("--client-id", type=str, help="Client ID from context (GUI)")
    parser.add_argument("--user-id", type=str, help="User ID (party_id) from context (GUI)")
    parser.add_argument("--account-id", type=str, help="Account ID")
    parser.add_argument("--page", type=int, default=0, help="Page number (default: 0)")
    parser.add_argument("--size", type=int, default=100, help="Page size (default: 100)")
    args = parser.parse_args()

    if args.client_id and args.user_id and args.account_id:
        test_get_account_transactions(
            client_id=args.client_id,
            user_id=args.user_id,
            account_id=args.account_id,
            page=args.page,
            size=args.size,
        )
    elif args.client_id or args.user_id or args.account_id:
        parser.error("Pass --client-id, --user-id and --account-id together, or omit them for console selection.")
    else:
        chosen = choose_client_and_user()
        if not chosen:
            sys.exit(0)
        client_id, user = chosen
        account_id = select_account(client_id, user)
        if not account_id:
            sys.exit(0)
        test_get_account_transactions(
            client_id=client_id,
            user_id=str(user),
            account_id=account_id,
            page=args.page,
            size=args.size,
        )
