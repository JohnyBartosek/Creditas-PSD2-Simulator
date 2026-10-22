"""
TPP User Create Payment
Based on Bruno/PSD Create Payment.bru
Creates a domestic payment using access token from database
"""

import argparse
import json
import re
import sys
from pathlib import Path

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


def get_payments_domestic_url() -> str:
    """Build payments URL from the configured PSD accounts base URL."""
    accounts_url = get_accounts_list_url().rstrip("/")
    if accounts_url.endswith("/accounts"):
        return f"{accounts_url[:-len('/accounts')]}/payments/domestic"
    return f"{accounts_url}/../payments/domestic"


def test_create_payment(client_id: str, user_id: str, payment_body: dict):
    """Create a domestic payment."""
    if not client_id:
        print("❌ Client ID is required")
        return

    if not user_id:
        print("❌ User (Party ID) is required")
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
    url = get_payments_domestic_url()

    print("=" * 60)
    print("CREATE PAYMENT REQUEST")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Client ID: {client_id}")
    print(f"Client Name (TPP-Name): {client_name}")
    print(f"User (Party ID): {user}")
    print(f"X-Request-ID: {request_id}")
    print(f"X-Request-Date: {request_date}")
    print("\n📤 Request Body:")
    print(json.dumps(payment_body, indent=2, ensure_ascii=False))
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

            print("📡 Making POST request to domestic payment endpoint...")
            response = api_request_context.post(
                url,
                headers=headers,
                data=json.dumps(payment_body, ensure_ascii=False),
            )

            status = response.status
            print(f"\n📥 Response Status: {status}")
            print(f"📋 Response Headers: {dict(response.headers)}")

            try:
                response_body = response.json()
                print("\n📄 Response Body:")
                print(json.dumps(response_body, indent=2, ensure_ascii=False))

                if 200 <= status < 300:
                    print("\n✅ Payment created successfully!")
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
    parser = argparse.ArgumentParser(description="Create Domestic Payment")
    parser.add_argument("--client-id", type=str, required=True, help="Client ID from context")
    parser.add_argument("--user-id", type=str, required=True, help="User ID (party_id) from context")
    parser.add_argument("--payment-json", type=str, required=True, help="Payment request body as JSON")
    args = parser.parse_args()

    try:
        payment_body_arg = json.loads(args.payment_json)
    except json.JSONDecodeError as exc:
        print(f"❌ Invalid payment JSON: {exc}")
        sys.exit(1)

    test_create_payment(
        client_id=args.client_id,
        user_id=args.user_id,
        payment_body=payment_body_arg,
    )
