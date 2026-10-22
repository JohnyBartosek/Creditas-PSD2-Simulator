"""
TPP User Account Balance
Based on Bruno/AccountBalance.bru
Fetches balances for a selected account using the access token from the database.
"""

import argparse
import json
import re
import sys
import io
from pathlib import Path

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
    X_CLIENT_CERTIFICATE,
    ensure_access_token,
    format_request_date,
    generate_request_id,
    get_client_name_by_id,
)
from Requests.TPP_User_Account_Transactions import choose_client_and_user, select_account


def test_get_account_balance(client_id: str, user_id: str, account_id: str):
    """Fetch balances for one account."""
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
    url = f"{get_accounts_list_url().rstrip('/')}/{account_id}/balance"

    print("=" * 60)
    print("ACCOUNT BALANCE REQUEST")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Client ID: {client_id}")
    print(f"Client Name (TPP-Name): {client_name}")
    print(f"User (Party ID): {user}")
    print(f"Account ID: {account_id}")
    print(f"X-Request-ID: {request_id}")
    print(f"X-Request-Date: {request_date}")
    print("=" * 60)
    print()

    with sync_playwright() as playwright:
        api_request_context = playwright.request.new_context(ignore_https_errors=True)
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
            print("📡 Making GET request to account balance endpoint...")
            response = api_request_context.get(url, headers=headers)
            status = response.status
            print(f"\n📥 Response Status: {status}")
            print(f"📋 Response Headers: {dict(response.headers)}")
            try:
                response_body = response.json()
                print("\n📄 Response Body:")
                print(json.dumps(response_body, indent=2, ensure_ascii=False))
                if status == 200:
                    print("\n✅ Account balance retrieved successfully!")
                    _print_balance_summary(response_body)
                else:
                    print(f"\n⚠️  Request failed with status {status}")
            except Exception:
                response_text = response.text()
                print("\n📄 Response Body (text):")
                print(response_text[:1000])
            print("\n" + "=" * 60)
        except Exception as exc:
            print(f"\n❌ Request failed: {exc}")
            import traceback
            traceback.print_exc()
        finally:
            api_request_context.dispose()


def _print_balance_summary(body):
    items = []
    if isinstance(body, list):
        items = body
    elif isinstance(body, dict):
        for key in ("balances", "balance", "accountBalances"):
            value = body.get(key)
            if isinstance(value, list):
                items = value
                break
            if isinstance(value, dict):
                items = [value]
                break
        if not items and any(key in body for key in ("balanceAmount", "amount", "value")):
            items = [body]
    if not items:
        return
    print("\nBalances:")
    for item in items:
        if not isinstance(item, dict):
            continue
        label = item.get("balanceType") or item.get("type") or item.get("nameI18N") or "Balance"
        if isinstance(label, dict):
            proprietary = label.get("codeOrProprietary") if isinstance(label.get("codeOrProprietary"), dict) else {}
            label = label.get("nameI18N") or label.get("code") or proprietary.get("code") or "Balance"
        amount_node = item.get("balanceAmount") or item.get("amount") or item
        value = ""
        currency = item.get("currency") or ""
        if isinstance(amount_node, dict):
            nested = amount_node.get("instructedAmount")
            if isinstance(nested, dict):
                amount_node = nested
            value = amount_node.get("value", amount_node.get("amount", ""))
            currency = amount_node.get("currency") or amount_node.get("currencyCode") or currency
        print(f"  {label}: {value} {currency}".rstrip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Account Balance")
    parser.add_argument("--client-id", type=str, help="Client ID from context (GUI)")
    parser.add_argument("--user-id", type=str, help="User ID (party_id) from context (GUI)")
    parser.add_argument("--account-id", type=str, help="Account ID")
    args = parser.parse_args()

    if args.client_id and args.user_id and args.account_id:
        test_get_account_balance(
            client_id=args.client_id,
            user_id=args.user_id,
            account_id=args.account_id,
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
        test_get_account_balance(client_id=client_id, user_id=str(user), account_id=account_id)
