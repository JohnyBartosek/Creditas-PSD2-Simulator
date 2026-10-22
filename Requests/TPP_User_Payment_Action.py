"""
TPP User Payment Actions
Based on Bruno payment status/detail/authorize/delete requests
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.environment_config import get_accounts_list_url, get_database_file
from Helpers.sms_otp_helper import wait_for_sms_otp
from Requests.TPP_User_Account_List import (
    X_CLIENT_CERTIFICATE,
    ensure_access_token,
    format_request_date,
    generate_request_id,
    get_client_name_by_id,
)
from Requests.TPP_User_Account_Transactions import choose_client_and_user

USERS_FILE = str(get_database_file("users.json"))


def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception as e:
            print(f"⚠️  Error loading users: {e}")
    return {"users": []}


def get_user_by_party_id(party_id: str):
    for user in load_users().get("users", []):
        if user.get("partyId") == party_id:
            return user
    return None


def parse_birth_date(birth_date: str):
    try:
        parts = birth_date.split(".")
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
    except Exception:
        pass
    return None, None


def get_czech_month_name(month_num: str) -> str:
    month_map = {
        "1": "Leden", "01": "Leden",
        "2": "Únor", "02": "Únor",
        "3": "Březen", "03": "Březen",
        "4": "Duben", "04": "Duben",
        "5": "Květen", "05": "Květen",
        "6": "Červen", "06": "Červen",
        "7": "Červenec", "07": "Červenec",
        "8": "Srpen", "08": "Srpen",
        "9": "Září", "09": "Září",
        "10": "Říjen",
        "11": "Listopad",
        "12": "Prosinec",
    }
    return month_map.get(month_num, month_num)


def _find_nested_value(data, keys: list[str], default=""):
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if value not in (None, "") and not isinstance(value, (dict, list)):
                return value

        for value in data.values():
            found = _find_nested_value(value, keys, default=None)
            if found not in (None, ""):
                return found

    if isinstance(data, list):
        for item in data:
            found = _find_nested_value(item, keys, default=None)
            if found not in (None, ""):
                return found

    return default


def _click_first_visible(page, selectors: list[str], description: str, timeout_ms: int = 3000) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            if locator.is_visible():
                text = ""
                try:
                    text = (locator.text_content() or "").strip()
                except Exception:
                    pass
                locator.click()
                print(f"✅ Clicked {description}: selector={selector} text='{text}'")
                return True
        except Exception:
            continue
    return False


def _fill_first_visible(page, selectors: list[str], value: str, description: str, timeout_ms: int = 3000) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            if locator.is_visible():
                locator.fill(value)
                print(f"✅ Filled {description}: selector={selector}")
                return True
        except Exception:
            continue
    return False


def _select_birth_date(page, user: dict) -> bool:
    birth_day, birth_month = parse_birth_date(user.get("birthDate", ""))
    if not birth_day or not birth_month:
        print("❌ Birth date missing in users database")
        return False

    month_name = get_czech_month_name(birth_month)
    print(f"📅 Birth date: day={birth_day}, month={birth_month} ({month_name})")

    try:
        selects = page.locator("select")
        if selects.count() >= 2:
            selects.nth(0).select_option(value=str(int(birth_day)), timeout=2000)
            selects.nth(1).select_option(value=str(int(birth_month)), timeout=2000)
            print("✅ Birth date selected via hidden selects")
            return True
    except Exception as e:
        print(f"ℹ️ Hidden select birth date path not used: {e}")

    try:
        day_combobox = page.locator('button[role="combobox"]').filter(has_text="Den").first
        day_combobox.click(timeout=3000)
        day_option = page.locator(f'[role="option"]:has-text("{birth_day}")').first
        day_option.click(timeout=3000)

        month_combobox = page.locator('button[role="combobox"]').filter(has_text="Měsíc").first
        month_combobox.click(timeout=3000)
        month_option = page.locator(f'[role="option"]:has-text("{month_name}")').first
        month_option.click(timeout=3000)
        print("✅ Birth date selected via comboboxes")
        return True
    except Exception as e:
        print(f"❌ Could not select birth date: {e}")
        return False


def _fill_otp(page, api_request_context, party_id: int, description: str) -> bool:
    otp_selectors = [
        'input[data-input-otp="true"]',
        'input[data-input-otp]',
        'input[autocomplete="one-time-code"]',
        'input[inputmode="numeric"][maxlength="6"]',
        'input[maxlength="6"]',
    ]

    otp_input = None
    for selector in otp_selectors:
        try:
            candidate = page.locator(selector).first
            candidate.wait_for(state="visible", timeout=5000)
            if candidate.is_visible():
                otp_input = candidate
                print(f"✅ Found {description} OTP input: {selector}")
                break
        except Exception:
            continue

    if not otp_input:
        print(f"❌ {description} OTP input not found")
        return False

    print(f"🔍 Waiting for {description} OTP for party ID: {party_id}")
    otp = wait_for_sms_otp(
        api_request_context,
        party_id,
        timeout_seconds=60,
        time_range_minutes=5,
    )
    otp_input.fill(str(otp))
    print(f"✅ Filled {description} OTP")
    return True


def _automate_payment_authorization(p, authorization_url: str, user_id: str):
    user = get_user_by_party_id(user_id)
    if not user:
        print(f"❌ Could not find user with partyId '{user_id}' in {USERS_FILE}")
        return False

    try:
        party_id = int(user_id)
    except Exception:
        print(f"❌ Invalid party ID for OTP lookup: {user_id}")
        return False

    username = user.get("username")
    password = user.get("password")
    if not username or not password:
        print("❌ User record must contain username and password")
        return False

    print("=" * 60)
    print("PAYMENT BROWSER AUTHORIZATION")
    print("=" * 60)
    print(f"URL: {authorization_url}")
    print(f"User: {user.get('name', user_id)} ({user_id})")

    browser = p.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    api_request_context = p.request.new_context(ignore_https_errors=True)

    try:
        page.goto(authorization_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
        print(f"📍 Current URL: {page.url}")

        if not _fill_first_visible(
            page,
            [
                'input[autocomplete="username"]',
                'input[type="text"]',
                'input[name="username"]',
                'input[id*="login"]',
            ],
            username,
            "username",
        ):
            print("❌ Username input not found")
            return False

        if not _click_first_visible(page, ['button[type="submit"]', 'form button'], "login submit"):
            print("❌ Login submit button not found")
            return False

        page.wait_for_load_state("domcontentloaded", timeout=10000)
        if not _select_birth_date(page, user):
            return False

        if not _click_first_visible(page, ['button[type="submit"]', 'form button'], "birthday continue"):
            print("❌ Birthday continue button not found")
            return False

        page.wait_for_load_state("domcontentloaded", timeout=10000)

        # Some environments ask to switch to SMS authentication first.
        _click_first_visible(
            page,
            [
                'button:has-text("Ověřit přes SMS")',
                'button:has-text("ověřit přes SMS")',
                'button >> text=/ověřit přes sms/i',
            ],
            "SMS authentication method",
            timeout_ms=1500,
        )

        if not _fill_first_visible(page, ['#password', 'input[type="password"]'], password, "password", timeout_ms=5000):
            print("❌ Password input not found")
            return False

        page.wait_for_load_state("domcontentloaded", timeout=5000)
        if not _fill_otp(page, api_request_context, party_id, "login"):
            return False

        if not _click_first_visible(page, ['button[type="submit"]', 'button:has-text("Pokračovat")'], "login OTP confirm"):
            print("❌ Login OTP confirm button not found")
            return False

        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)
        print("✅ Login completed, looking for payment authorization controls")

        authorize_clicked = _click_first_visible(
            page,
            [
                'button:has-text("Autorizovat")',
                'button:has-text("Podepsat")',
                'button:has-text("Potvrdit")',
                'button:has-text("Authorize")',
                'button:has-text("Sign")',
                'button[type="submit"]',
            ],
            "payment authorization",
            timeout_ms=10000,
        )
        if not authorize_clicked:
            print("⚠️ Payment authorization button not found. Browser remains open for manual authorization.")
            page.wait_for_timeout(15000)
            return False

        page.wait_for_load_state("domcontentloaded", timeout=10000)
        page.wait_for_timeout(1000)

        if _fill_otp(page, api_request_context, party_id, "payment authorization"):
            _click_first_visible(
                page,
                [
                    'button[type="submit"]',
                    'button:has-text("Potvrdit")',
                    'button:has-text("Pokračovat")',
                    'button:has-text("Odeslat")',
                ],
                "payment OTP confirm",
                timeout_ms=5000,
            )

        page.wait_for_timeout(5000)
        print(f"📍 Final URL: {page.url}")
        print("✅ Payment browser authorization flow completed")
        return True
    except Exception as e:
        print(f"❌ Payment browser authorization failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        api_request_context.dispose()
        try:
            if browser.is_connected():
                browser.close()
        except Exception:
            pass


def get_payments_base_url() -> str:
    """Build payments base URL from the configured PSD accounts base URL."""
    accounts_url = get_accounts_list_url().rstrip("/")
    if accounts_url.endswith("/accounts"):
        return f"{accounts_url[:-len('/accounts')]}/payments"
    return f"{accounts_url}/../payments"


def _build_action_request(action: str, payment_id: str, sign_id: str = None):
    payments_url = get_payments_base_url()

    if action == "status":
        return "GET", f"{payments_url}/{payment_id}/status", None
    if action == "detail":
        return "GET", f"{payments_url}/{payment_id}", None
    if action == "delete":
        return "DELETE", f"{payments_url}/{payment_id}", None
    if action == "authorize":
        if not sign_id:
            raise ValueError("sign_id is required for authorize action")
        return "POST", f"{payments_url}/{payment_id}/sign/{sign_id}", {
            "authorizationType": "USERAGENT_REDIRECT",
            "redirectUrl": "https://localhost:3000/authorization/redirect",
        }

    raise ValueError(f"Unsupported payment action: {action}")


def run_payment_action(client_id: str, user_id: str, action: str, payment_id: str, sign_id: str = None):
    if not client_id:
        print("❌ Client ID is required")
        return

    if not user_id:
        print("❌ User (Party ID) is required")
        return

    if not payment_id:
        print("❌ Payment ID is required")
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
    method, url, body = _build_action_request(action, payment_id, sign_id)

    print("=" * 60)
    print(f"PAYMENT {action.upper()} REQUEST")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Method: {method}")
    print(f"Client ID: {client_id}")
    print(f"Client Name (TPP-Name): {client_name}")
    print(f"User (Party ID): {user}")
    print(f"Payment ID: {payment_id}")
    if sign_id:
        print(f"Sign ID: {sign_id}")
    print(f"X-Request-ID: {request_id}")
    print(f"X-Request-Date: {request_date}")
    if body:
        print("\n📤 Request Body:")
        print(json.dumps(body, indent=2, ensure_ascii=False))
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

            print(f"📡 Making {method} request to payment endpoint...")
            if method == "GET":
                response = api_request_context.get(url, headers=headers)
            elif method == "POST":
                response = api_request_context.post(
                    url,
                    headers=headers,
                    data=json.dumps(body, ensure_ascii=False),
                )
            else:
                response = api_request_context.delete(url, headers=headers)

            status = response.status
            print(f"\n📥 Response Status: {status}")
            print(f"📋 Response Headers: {dict(response.headers)}")

            response_body = None
            try:
                response_body = response.json()
                print("\n📄 Response Body:")
                print(json.dumps(response_body, indent=2, ensure_ascii=False))
            except Exception:
                response_text = response.text()
                print("\n📄 Response Body (text):")
                print(response_text[:1000])

            if 200 <= status < 300:
                print(f"\n✅ Payment {action} completed successfully!")
                if action == "authorize":
                    authorization_url = _find_nested_value(response_body, ["url", "authorizationUrl", "redirectUrl"])
                    if authorization_url:
                        print(f"\n🌐 Opening payment authorization URL in browser: {authorization_url}")
                        if _automate_payment_authorization(p, authorization_url, user_id):
                            print("\n✅ Payment authorization browser flow finished.")
                        else:
                            print("\n⚠️ Payment authorization browser flow did not finish automatically.")
                    else:
                        print("\n⚠️ Authorize response did not contain an authorization URL.")
            else:
                print(f"\n⚠️  Request failed with status {status}")
                sys.exit(1)

            print("\n" + "=" * 60)
        except Exception as e:
            print(f"\n❌ Request failed: {str(e)}")
            import traceback

            traceback.print_exc()
            sys.exit(1)
        finally:
            api_request_context.dispose()


ACTIONS = ("status", "detail", "authorize", "delete")


def _load_saved_payments() -> list[dict]:
    path = get_database_file("tpp_payments.json")
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"⚠️  Could not read saved payments: {exc}")
        return []
    payments = data.get("payments") if isinstance(data, dict) else data
    if not isinstance(payments, list):
        return []
    return [payment for payment in payments if isinstance(payment, dict)]


def _payment_summary(payment: dict) -> str:
    parts = []
    if payment.get("transactionIdentification"):
        parts.append(f"id {payment.get('transactionIdentification')}")
    if payment.get("amount + currency"):
        parts.append(str(payment.get("amount + currency")))
    if payment.get("status"):
        parts.append(str(payment.get("status")))
    if payment.get("signId"):
        parts.append(f"sign {payment.get('signId')}")
    if payment.get("debtorIban"):
        parts.append(f"from {payment.get('debtorIban')}")
    if payment.get("creditorIban"):
        parts.append(f"to {payment.get('creditorIban')}")
    if payment.get("instructionIdentification"):
        parts.append(str(payment.get("instructionIdentification")))
    return "  |  ".join(parts) or "payment"


def select_payment() -> dict | None:
    payments = _load_saved_payments()
    if not payments:
        print("⚠️  No saved payments found.")
        payment_id = input("Enter Payment ID or press Enter to cancel: ").strip()
        if not payment_id:
            return None
        sign_id = input("Enter Sign ID or press Enter to skip: ").strip()
        return {"transactionIdentification": payment_id, "signId": sign_id}

    print()
    print("=" * 60)
    print("SAVED PAYMENTS")
    print("=" * 60)
    print()
    for index, payment in enumerate(payments, 1):
        print(f"  [{index}] {_payment_summary(payment)}")
    print()

    while True:
        try:
            selection = input(f"Select payment (1-{len(payments)}) or 'q' to quit: ").strip()
            if selection.lower() == "q":
                print("❌ Cancelled by user")
                return None
            selection_num = int(selection)
            if 1 <= selection_num <= len(payments):
                return payments[selection_num - 1]
            print(f"⚠️  Please enter a number between 1 and {len(payments)}")
        except ValueError:
            print("⚠️  Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None


def select_action() -> str | None:
    print()
    print("Actions: status, detail, authorize, delete")
    while True:
        try:
            selection = input("Select action or 'q' to quit: ").strip().lower()
            if selection == "q":
                print("❌ Cancelled by user")
                return None
            if selection in ACTIONS:
                return selection
            print("⚠️  Choose status, detail, authorize or delete")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Payment Action")
    parser.add_argument("--client-id", type=str, help="Client ID from context (GUI)")
    parser.add_argument("--user-id", type=str, help="User ID (party_id) from context (GUI)")
    parser.add_argument(
        "--action",
        type=str,
        choices=ACTIONS,
        help="Payment action",
    )
    parser.add_argument("--payment-id", type=str, help="Payment ID")
    parser.add_argument("--sign-id", type=str, help="Sign ID for authorize action")
    args = parser.parse_args()

    gui_args = (args.client_id, args.user_id, args.action, args.payment_id)
    if all(gui_args):
        run_payment_action(
            client_id=args.client_id,
            user_id=args.user_id,
            action=args.action,
            payment_id=args.payment_id,
            sign_id=args.sign_id,
        )
    elif any(gui_args):
        parser.error(
            "Pass --client-id, --user-id, --action and --payment-id together, or omit them for console selection."
        )
    else:
        chosen = choose_client_and_user()
        if not chosen:
            sys.exit(0)
        client_id, user = chosen
        payment = select_payment()
        if not payment:
            sys.exit(0)
        action = select_action()
        if not action:
            sys.exit(0)
        payment_id = str(payment.get("transactionIdentification") or "").strip()
        if not payment_id:
            payment_id = input("Enter Payment ID: ").strip()
        if not payment_id:
            print("❌ Payment ID is required")
            sys.exit(1)
        sign_id = str(payment.get("signId") or args.sign_id or "").strip()
        if action == "authorize" and not sign_id:
            sign_id = input("Enter Sign ID: ").strip()
            if not sign_id:
                print("❌ Sign ID is required for authorize")
                sys.exit(1)
        run_payment_action(
            client_id=client_id,
            user_id=str(user),
            action=action,
            payment_id=payment_id,
            sign_id=sign_id or None,
        )
