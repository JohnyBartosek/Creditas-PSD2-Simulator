"""
TPP User Authorization Test
Automates OAuth2 authorization flow using a TPP client from the JSON database
"""

from playwright.sync_api import sync_playwright
import json
import os
import random
import argparse
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode
import sys
import os
from pathlib import Path

# Get the parent directory (project root)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add parent directory to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.sms_otp_helper import wait_for_sms_otp
from Helpers.file_lock_helper import safe_update_json
from Helpers.data_store import keep_valid_auth_codes
from Helpers.environment_config import get_database_file, get_oauth_authorize_url, load_token_config


def _open_auth_codes(entries, current_state):
    expiration = load_token_config()["authorization_code_expiration_seconds"]
    return [
        entry
        for entry in keep_valid_auth_codes(entries, expiration)
        if entry.get("state") != current_state
    ]

# ----------------------------
# UI selector discovery helpers
# ----------------------------

# Toggle via CLI flag (see __main__) or env var.
DISCOVERY_MODE = False

# Confirmed selectors (from discovery logs)
SEL_USERNAME = 'input[autocomplete="username"]'
SEL_LOGIN_SUBMIT = 'button[type="submit"]'  # text: "Přihlásit se"
SEL_BDAY_DAY_COMBO = 'button[role="combobox"] >> text=Den'
SEL_BDAY_MONTH_COMBO = 'button[role="combobox"] >> text=Měsíc'
SEL_BDAY_CONTINUE = 'button[type="submit"]'  # text: "Pokračovat"
SEL_PASSWORD = '#password'
SEL_OTP = 'input[data-input-otp="true"]'
SEL_OTP_CONFIRM = 'button[type="submit"]'  # text: "Pokračovat"


def _safe_text(s: str, max_len: int = 160) -> str:
    if s is None:
        return ""
    s = str(s).replace("\n", " ").replace("\r", " ").strip()
    return s[:max_len] + ("..." if len(s) > max_len else "")


def _safe_input(prompt: str, default: str = "") -> str:
    """
    input() wrapper that won't crash/hang in non-interactive runs.
    Returns default on EOFError.
    """
    try:
        return input(prompt)
    except EOFError:
        print("WARNING: No interactive input available; using default.")
        return default


def _build_best_selector_for_handle(handle) -> str:
    """
    Return a stable-ish CSS selector for an element handle:
    prefers #id, data-testid, name, aria-label, placeholder; else falls back to tag+classes.
    """
    try:
        return handle.evaluate(
            """(el) => {
  const tag = (el.tagName || '').toLowerCase();
  const id = el.getAttribute && el.getAttribute('id');
  if (id) return `#${CSS.escape(id)}`;
  const dt = el.getAttribute && (el.getAttribute('data-testid') || el.getAttribute('data-test-id') || el.getAttribute('data-test'));
  if (dt) return `${tag}[data-testid="${dt}"]`;
  const name = el.getAttribute && el.getAttribute('name');
  if (name) return `${tag}[name="${name}"]`;
  const aria = el.getAttribute && el.getAttribute('aria-label');
  if (aria) return `${tag}[aria-label="${aria}"]`;
  const ph = el.getAttribute && el.getAttribute('placeholder');
  if (ph) return `${tag}[placeholder="${ph}"]`;
  const type = el.getAttribute && el.getAttribute('type');
  const cls = (el.getAttribute && el.getAttribute('class')) ? el.getAttribute('class').trim() : '';
  const classes = cls ? '.' + cls.split(/\\s+/).filter(Boolean).slice(0, 3).map(c => CSS.escape(c)).join('.') : '';
  if (type) return `${tag}[type="${type}"]${classes}`;
  return `${tag}${classes}` || 'element';
}"""
        )
    except Exception:
        return "element"


def log_visible_elements_snapshot(page, title: str, *, limit: int = 40) -> None:
    """
    Logs a compact snapshot of visible inputs and buttons on the current page.
    Use this output to pick stable selectors (id/name/data-testid/etc) and harden the flow.
    """
    try:
        print("\n" + "=" * 60)
        print(f"UI SNAPSHOT: {title}")
        print("=" * 60)
        print(f"URL: {page.url}")
        try:
            print(f"Title: {_safe_text(page.title())}")
        except Exception:
            pass

        # Inputs
        inputs = page.locator("input, textarea, select").all()
        shown = 0
        for loc in inputs:
            if shown >= limit:
                break
            try:
                if not loc.is_visible(timeout=200):
                    continue
                h = loc.element_handle()
                if not h:
                    continue
                sel = _build_best_selector_for_handle(h)
                attrs = {
                    "tag": h.evaluate("(el) => el.tagName.toLowerCase()"),
                    "type": h.get_attribute("type"),
                    "id": h.get_attribute("id"),
                    "name": h.get_attribute("name"),
                    "placeholder": h.get_attribute("placeholder"),
                    "aria-label": h.get_attribute("aria-label"),
                    "autocomplete": h.get_attribute("autocomplete"),
                    "data-testid": h.get_attribute("data-testid"),
                    "data-input-otp": h.get_attribute("data-input-otp"),
                }
                attrs = {k: v for k, v in attrs.items() if v}
                print(f"- INPUT: selector={sel} attrs={attrs}")
                shown += 1
            except Exception:
                continue

        # Buttons
        buttons = page.locator("button, input[type='submit'], input[type='button']").all()
        shown = 0
        for loc in buttons:
            if shown >= limit:
                break
            try:
                if not loc.is_visible(timeout=200):
                    continue
                h = loc.element_handle()
                if not h:
                    continue
                sel = _build_best_selector_for_handle(h)
                text = ""
                try:
                    text = _safe_text(loc.text_content() or "")
                except Exception:
                    pass
                attrs = {
                    "tag": h.evaluate("(el) => el.tagName.toLowerCase()"),
                    "type": h.get_attribute("type"),
                    "id": h.get_attribute("id"),
                    "name": h.get_attribute("name"),
                    "role": h.get_attribute("role"),
                    "aria-label": h.get_attribute("aria-label"),
                    "data-testid": h.get_attribute("data-testid"),
                }
                attrs = {k: v for k, v in attrs.items() if v}
                print(f"- BUTTON: selector={sel} text='{text}' attrs={attrs}")
                shown += 1
            except Exception:
                continue
    except Exception as e:
        print(f"WARNING: Failed to log UI snapshot: {e}")


def _try_fill_first(page, description: str, selectors: list, value: str, *, timeout_ms: int = 3000) -> bool:
    """
    Try selectors in order. Log which one succeeded.
    """
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout_ms)
            if loc.is_visible():
                loc.fill(value)
                print(f"PASS: {description} selector={sel}")
                return True
        except Exception as e:
            print(f"FAIL: {description} selector={sel} err={_safe_text(e)}")
    return False


def _try_click_first(page, description: str, selectors: list, *, timeout_ms: int = 3000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout_ms)
            if loc.is_visible():
                txt = ""
                try:
                    txt = _safe_text(loc.text_content() or "")
                except Exception:
                    pass
                loc.click()
                print(f"PASS: {description} selector={sel} text='{txt}'")
                return True
        except Exception as e:
            print(f"FAIL: {description} selector={sel} err={_safe_text(e)}")
    return False


def _select_radix_option_from_open_list(page, option_text: str, *, timeout_ms: int = 3000) -> bool:
    """
    Fallback for Radix UI selects when there is no hidden <select>.
    Assumes the dropdown is already open; clicks the matching role=option item.
    """
    candidates = [
        f'[role="option"] >> text="{option_text}"',
        f'[role="option"]:has-text("{option_text}")',
        f'[data-radix-collection-item] >> text="{option_text}"',
    ]
    for sel in candidates:
        try:
            opt = page.locator(sel).first
            opt.wait_for(state="visible", timeout=timeout_ms)
            if opt.is_visible():
                # Avoid implicit navigation waits; Radix option clicks can trigger re-render.
                opt.click(timeout=timeout_ms, force=True, no_wait_after=True)
                print(f"PASS: radix option click selector={sel} text={option_text}")
                return True
        except Exception as e:
            print(f"FAIL: radix option click selector={sel} err={_safe_text(e)}")
    return False


def _tmark(label: str, t0: float) -> float:
    t1 = time.perf_counter()
    print(f"TIME: {label} {t1 - t0:.3f}s")
    return t1

# Database files (environment-aware paths)
DATABASE_FILE = str(get_database_file("tpp_registrations.json"))
DEFAULT_AUTH_CONFIG_FILE = str(get_database_file("default_auth_config.json"))
USERS_FILE = str(get_database_file("users.json"))

# Expected redirect URI (fallback)
REDIRECT_URI_DEFAULT = "https://tpp.example.com/redirect"


def load_database():
    """Load existing registrations from JSON database file"""
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading database: {e}")
            return {"registrations": []}
    return {"registrations": []}


def load_default_auth_config():
    """Load default authentication configuration"""
    if os.path.exists(DEFAULT_AUTH_CONFIG_FILE):
        try:
            with open(DEFAULT_AUTH_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading default auth config: {e}")
            return None
    return None


def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading users: {e}")
            return {"users": []}
    return {"users": []}


def get_user_by_party_id(party_id: str):
    """Get user by party ID"""
    users_data = load_users()
    for user in users_data.get("users", []):
        if user.get("partyId") == party_id:
            return user
    return None


def get_client_by_name(client_name: str):
    """Get TPP client from database by client_name"""
    database = load_database()
    
    for registration in database.get("registrations", []):
        # Try to get client_name from request body
        request_body = registration.get("request", {}).get("body", {})
        reg_client_name = request_body.get("client_name", "")
        
        # Try to get client_name from response body if not in request
        if not reg_client_name:
            response_body = registration.get("response", {}).get("body", {})
            if isinstance(response_body, dict):
                reg_client_name = response_body.get("client_name", "")
        
        if reg_client_name == client_name:
            # Get client_id from response
            response_body = registration.get("response", {}).get("body", {})
            client_id = None
            
            if isinstance(response_body, dict):
                client_id = response_body.get("client_id")
            
            # Get redirect_uris from request or response
            redirect_uris = request_body.get("redirect_uris", [])
            if not redirect_uris and isinstance(response_body, dict):
                redirect_uris = response_body.get("redirect_uris", [])
            
            # Get scope from request or response
            scope = request_body.get("scope", "")
            if not scope and isinstance(response_body, dict):
                scope = response_body.get("scope", "") or response_body.get("scopes", "")
            
            # Get timestamp
            timestamp = registration.get("timestamp", "Unknown")
            
            return {
                "client_name": reg_client_name,
                "client_id": client_id,
                "redirect_uris": redirect_uris,
                "scope": scope,
                "timestamp": timestamp
            }
    
    return None


def parse_birth_date(birth_date: str):
    """
    Parse birth date from format "27.06.1971" to day and month
    Returns tuple (day, month) as strings
    """
    try:
        # Format: "27.06.1971" or "27.6.1971"
        parts = birth_date.split('.')
        if len(parts) >= 2:
            day = parts[0].strip()
            month = parts[1].strip()
            return (day, month)
    except:
        pass
    return (None, None)


def get_czech_month_name(month_num: str) -> str:
    """
    Convert month number to Czech month name
    Args:
        month_num: Month number as string (e.g., "6", "06")
    Returns:
        Czech month name (e.g., "Červen")
    """
    month_map = {
        "1": "Leden",
        "01": "Leden",
        "2": "Únor",
        "02": "Únor",
        "3": "Březen",
        "03": "Březen",
        "4": "Duben",
        "04": "Duben",
        "5": "Květen",
        "05": "Květen",
        "6": "Červen",
        "06": "Červen",
        "7": "Červenec",
        "07": "Červenec",
        "8": "Srpen",
        "08": "Srpen",
        "9": "Září",
        "09": "Září",
        "10": "Říjen",
        "11": "Listopad",
        "12": "Prosinec"
    }
    return month_map.get(month_num, month_num)


def list_available_clients():
    """List all available clients from the database"""
    database = load_database()
    clients = []
    
    for idx, registration in enumerate(database.get("registrations", []), 1):
        # Try to get client_name from request body
        request_body = registration.get("request", {}).get("body", {})
        client_name = request_body.get("client_name", "Unknown")
        
        # Try to get client_name from response body if not in request
        if client_name == "Unknown":
            response_body = registration.get("response", {}).get("body", {})
            if isinstance(response_body, dict):
                client_name = response_body.get("client_name", "Unknown")
        
        # Get client_id from response
        response_body = registration.get("response", {}).get("body", {})
        client_id = None
        
        if isinstance(response_body, dict):
            client_id = response_body.get("client_id")
        
        # Get redirect_uris from request or response
        redirect_uris = request_body.get("redirect_uris", [])
        if not redirect_uris and isinstance(response_body, dict):
            redirect_uris = response_body.get("redirect_uris", [])
        
        # Get scope from request or response
        scope = request_body.get("scope", "")
        if not scope and isinstance(response_body, dict):
            scope = response_body.get("scope", "") or response_body.get("scopes", "")
        
        # Get timestamp
        timestamp = registration.get("timestamp", "Unknown")
        
        clients.append({
            "index": idx,
            "client_name": client_name,
            "client_id": client_id,
            "redirect_uris": redirect_uris,
            "scope": scope,
            "timestamp": timestamp
        })
    
    return clients


def select_client():
    """Display available clients and let user select one"""
    clients = list_available_clients()
    
    if not clients:
        print("❌ No registrations found in database!")
        print(f"   Database file: {DATABASE_FILE}")
        return None
    
    print("="*60)
    print("AVAILABLE TPP CLIENTS")
    print("="*60)
    print()
    
    for client in clients:
        print(f"  [{client['index']}] {client['client_name']}")
        print(f"      Client ID: {client['client_id']}")
        print(f"      Scope: {client['scope']}")
        print(f"      Redirect URIs: {', '.join(client['redirect_uris'])}")
        print(f"      Registered: {client['timestamp']}")
        print()
    
    while True:
        try:
            selection = _safe_input(f"Select TPP client (1-{len(clients)}) or 'q' to quit: ").strip()
            
            if selection.lower() == 'q':
                print("❌ Cancelled by user")
                return None
            
            selection_num = int(selection)
            if 1 <= selection_num <= len(clients):
                selected_client = clients[selection_num - 1]
                
                # Validate that we have required data
                if not selected_client['client_id']:
                    print(f"❌ Selected client '{selected_client['client_name']}' has no client_id in database")
                    return None
                
                return selected_client
            else:
                print(f"⚠️  Please enter a number between 1 and {len(clients)}")
        except ValueError:
            print("⚠️  Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None


def select_user():
    """Display available users and let user select one"""
    users_data = load_users()
    users = users_data.get("users", [])
    
    if not users:
        print("❌ No users found in database!")
        print(f"   Users file: {USERS_FILE}")
        return None
    
    print("="*60)
    print("AVAILABLE USERS")
    print("="*60)
    print()
    
    for idx, user in enumerate(users, 1):
        print(f"  [{idx}] {user.get('name', 'Unknown')}")
        print(f"      Party ID: {user.get('partyId', 'N/A')}")
        print(f"      Username: {user.get('username', 'N/A')}")
        print(f"      Birth Date: {user.get('birthDate', 'N/A')}")
        print()
    
    while True:
        try:
            selection = _safe_input(f"Select user (1-{len(users)}) or 'q' to quit: ").strip()
            
            if selection.lower() == 'q':
                print("❌ Cancelled by user")
                return None
            
            selection_num = int(selection)
            if 1 <= selection_num <= len(users):
                selected_user = users[selection_num - 1]
                return selected_user
            else:
                print(f"⚠️  Please enter a number between 1 and {len(users)}")
        except ValueError:
            print("⚠️  Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None


def generate_random_state():
    """Generate a random state parameter for OAuth2"""
    return str(random.randint(1000000000000, 9999999999999))


def normalize_scope(scope):
    """Normalize scope to comma-delimited string format"""
    if not scope:
        return ""
    if isinstance(scope, list):
        return ", ".join(str(s) for s in scope)
    elif isinstance(scope, str):
        return scope
    else:
        return str(scope)


def build_auth_url(client_id: str, redirect_uri: str, scope: str, state: str) -> str:
    """Build the OAuth2 authorization URL with query parameters"""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state
    }
    
    query_string = urlencode(params)
    auth_base_url = get_oauth_authorize_url()
    return f"{auth_base_url}?{query_string}"


def test_oauth2_authorize_endpoint(party_id: int = None, client_id: str = None, user_id: str = None):
    """
    Test the OAuth2 authorization endpoint in a browser and wait for redirect
    
    Args:
        party_id: Party ID for SMS OTP retrieval. If None, will load from default_auth_config.json or user_id.
        client_id: Client ID to use. If provided, will use this instead of default config.
        user_id: User ID (party_id as string). If provided, will use this instead of default config.
    """
    # Load default auth config (always needed, especially for redirect_uri)
    auth_config = load_default_auth_config()
    
    # If client_id and user_id are provided (from GUI context), use them
    if client_id and user_id:
        try:
            party_id = int(user_id)
        except:
            party_id = None
        
        # Get client by client_id (not client_name)
        database = load_database()
        selected_client = None
        for registration in database.get("registrations", []):
            response_body = registration.get("response", {}).get("body", {})
            if isinstance(response_body, dict):
                reg_client_id = response_body.get("client_id")
                if reg_client_id == client_id:
                    request_body = registration.get("request", {}).get("body", {})
                    client_name = request_body.get("client_name", "")
                    if not client_name:
                        client_name = response_body.get("client_name", "Unknown")
                    # Use redirect_uris for authorization endpoint (not authorization_redirect_uris)
                    redirect_uris = request_body.get("redirect_uris", [])
                    if not redirect_uris:
                        redirect_uris = response_body.get("redirect_uris", [])
                    
                    # Also get authorization_redirect_uris for reference (but use redirect_uris for auth endpoint)
                    authorization_redirect_uris = request_body.get("authorization_redirect_uris", [])
                    if not authorization_redirect_uris:
                        authorization_redirect_uris = response_body.get("authorization_redirect_uris", [])
                    
                    # Get scope - handle both single scope string and multiple scopes
                    scope = request_body.get("scope", "")
                    if not scope:
                        scope = response_body.get("scope", "") or response_body.get("scopes", "")
                    
                    # Normalize scope to comma-delimited string
                    scope = normalize_scope(scope)
                    
                    selected_client = {
                        "client_name": client_name,
                        "client_id": client_id,
                        "redirect_uris": redirect_uris,
                        "authorization_redirect_uris": authorization_redirect_uris,
                        "scope": scope,
                        "timestamp": registration.get("timestamp", "Unknown")
                    }
                    break
        
        if not selected_client:
            print(f"❌ Could not find TPP client with client_id '{client_id}' in database!")
            print(f"   Database file: {DATABASE_FILE}")
            return
        
        # Get user by party_id
        user = get_user_by_party_id(user_id)
        if not user:
            print(f"⚠️  Could not find user with partyId '{user_id}' in users database!")
            print(f"   Users file: {USERS_FILE}")
            user = None
        else:
            print(f"✅ Loaded user: {user.get('name')} (Party ID: {user_id})")
        
        # Use redirect_uri from TPP registration (use redirect_uris, not authorization_redirect_uris)
        # Only use config if registration doesn't have any redirect URIs
        redirect_uri = None
        if selected_client.get('redirect_uris') and len(selected_client['redirect_uris']) > 0:
            redirect_uri = selected_client['redirect_uris'][0]
            print(f"✅ Using redirect_uri from registration: {redirect_uri}")
        elif auth_config and auth_config.get("redirect_uri"):
            redirect_uri = auth_config.get("redirect_uri")
            print(f"⚠️  Using redirect_uri from config (registration has no redirect URIs): {redirect_uri}")
        else:
            redirect_uri = REDIRECT_URI_DEFAULT
            print(f"⚠️  Using default redirect_uri: {redirect_uri}")
        
        client_name = selected_client['client_name']
        client_id = selected_client['client_id']
        scope = normalize_scope(selected_client['scope'])
        
        print(f"✅ Using context: Client={client_name}, User={user_id}, Redirect URI={redirect_uri}, Scope={scope}")
    elif not auth_config:
        # Console mode: Let user choose client and user
        print("="*60)
        print("CONSOLE MODE - SELECT CLIENT AND USER")
        print("="*60)
        print()
        
        # Select TPP client
        selected_client = select_client()
        if not selected_client:
            return
        client_name = selected_client['client_name']
        client_id = selected_client['client_id']
        redirect_uris = selected_client['redirect_uris']
        scope = normalize_scope(selected_client['scope'])
        redirect_uri = redirect_uris[0] if redirect_uris else REDIRECT_URI_DEFAULT
        
        # Select user
        print()
        selected_user = select_user()
        if not selected_user:
            return
        
        user = selected_user
        party_id = None
        try:
            party_id = int(selected_user.get('partyId'))
        except:
            print(f"⚠️  Could not parse partyId '{selected_user.get('partyId')}' as integer")
            party_id_input = _safe_input("Enter Party ID (for SMS OTP retrieval) or press Enter to skip: ").strip()
            if party_id_input and party_id_input.isdigit():
                party_id = int(party_id_input)
        
        print(f"✅ Selected: Client={client_name}, User={user.get('name')} (Party ID: {user.get('partyId')})")
    else:
        # Console mode with config: Use config but let user choose if they want
        config_party_id = auth_config.get("partyId")
        config_client_name = auth_config.get("client_id")
        config_redirect_uri = auth_config.get("redirect_uri")
        
        print("="*60)
        print("CONSOLE MODE - USING DEFAULT CONFIG")
        print("="*60)
        print(f"Default Client: {config_client_name}")
        print(f"Default User (Party ID): {config_party_id}")
        print()
        
        # Ask if user wants to use default config or choose manually.
        # In discovery mode (and/or non-interactive runs), auto-use defaults.
        if DISCOVERY_MODE or not sys.stdin.isatty():
            use_default = "y"
        else:
            use_default = _safe_input("Use default configuration? (Y/n): ", default="y").strip().lower()
        
        if use_default and use_default != 'n':
            # Use default config
            # Find TPP client by client_name
            selected_client = get_client_by_name(config_client_name)
            if not selected_client:
                print(f"❌ Could not find TPP client '{config_client_name}' in database!")
                print(f"   Database file: {DATABASE_FILE}")
                return
            
            client_name = selected_client['client_name']
            client_id = selected_client['client_id']
            redirect_uris = selected_client['redirect_uris']
            scope = normalize_scope(selected_client['scope'])
            
            # Use redirect_uri from config, or from TPP registration, or default
            redirect_uri = config_redirect_uri or (redirect_uris[0] if redirect_uris else REDIRECT_URI_DEFAULT)
            
            # Load user data
            user = get_user_by_party_id(config_party_id)
            if not user:
                print(f"⚠️  Could not find user with partyId '{config_party_id}' in users database!")
                print(f"   Users file: {USERS_FILE}")
                user = None
            else:
                print(f"✅ Loaded user: {user.get('name')} (Party ID: {config_party_id})")
            
            # Use party_id from config if not provided
            if not party_id and config_party_id:
                try:
                    party_id = int(config_party_id)
                except:
                    pass
        else:
            # Manual selection
            print()
            print("Manual selection mode...")
            
            # Select TPP client
            selected_client = select_client()
            if not selected_client:
                return
            client_name = selected_client['client_name']
            client_id = selected_client['client_id']
            redirect_uris = selected_client['redirect_uris']
            scope = normalize_scope(selected_client['scope'])
            redirect_uri = redirect_uris[0] if redirect_uris else REDIRECT_URI_DEFAULT
            
            # Select user
            print()
            selected_user = select_user()
            if not selected_user:
                return
            
            user = selected_user
            party_id = None
            try:
                party_id = int(selected_user.get('partyId'))
            except:
                print(f"⚠️  Could not parse partyId '{selected_user.get('partyId')}' as integer")
                party_id_input = _safe_input("Enter Party ID (for SMS OTP retrieval) or press Enter to skip: ").strip()
                if party_id_input and party_id_input.isdigit():
                    party_id = int(party_id_input)
            
            print(f"✅ Selected: Client={client_name}, User={user.get('name')} (Party ID: {user.get('partyId')})")
    
    # Initialize password variable (will be set from user data or prompted)
    password = user.get("password") if user else None
    
    # Generate random state
    state = generate_random_state()
    
    # Build authorization URL
    auth_url = build_auth_url(client_id, redirect_uri, scope, state)
    
    print("="*60)
    print("OAUTH2 AUTHORIZATION")
    print("="*60)
    print(f"Client Name: {client_name}")
    print(f"Client ID: {client_id}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Scope: {scope}")
    print(f"State: {state}")
    print(f"Authorization URL: {auth_url}")
    print("="*60)
    print()
    
    with sync_playwright() as p:
        # Launch browser (not headless so user can see the flow)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        
        # Create API request context for SMS OTP retrieval
        api_request_context = p.request.new_context(ignore_https_errors=True)
        
        try:
            print(f"🌐 Opening browser and navigating to authorization URL...")
            print(f"URL: {auth_url}\n")
            
            # Navigate to the authorization URL
            try:
                response = page.goto(auth_url, wait_until="domcontentloaded", timeout=30000)
                
                # Check response status
                if response:
                    status = response.status
                    print(f"📊 Response Status: {status}")
                    if status >= 400:
                        print(f"⚠️  HTTP Error {status} - Authorization request failed!")
                        # Try to get error details
                        try:
                            error_text = page.content()
                            if "Whitelabel Error Page" in error_text or "error" in error_text.lower():
                                # Try to extract error message
                                error_match = page.locator("div").filter(has_text="error").first
                                if error_match.count() > 0:
                                    error_msg = error_match.inner_text()
                                    print(f"❌ Error: {error_msg}")
                        except:
                            pass
                        
                        # Show the actual URL that was requested
                        print(f"\n🔍 Debugging Information:")
                        print(f"   Requested URL: {auth_url}")
                        print(f"   Client ID: {client_id}")
                        print(f"   Redirect URI: {redirect_uri}")
                        print(f"   Scope: {scope}")
                        print(f"   State: {state}")
                        print(f"\n💡 Possible issues:")
                        print(f"   - Redirect URI might not match registered redirect_uri")
                        print(f"   - Client ID might be invalid or not registered")
                        print(f"   - Scope might be invalid")
                        print(f"   - Missing required parameters")
                        
                        return
            except Exception as e:
                print(f"❌ Error navigating to authorization URL: {e}")
                return
            
            print(f"📍 Current URL: {page.url}")
            print(f"📄 Page Title: {page.title()}\n")
            
            # Wait for the login form to appear and fill in username
            print("🔍 Looking for username input field...")
            
            # Wait for page to be ready
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Discovery snapshot (helps us lock down exact selectors and remove guessing)
            if DISCOVERY_MODE:
                log_visible_elements_snapshot(page, "Login screen")

            # Prefer deterministic selectors first; keep a small fallback set.
            username_filled = False
            username_selectors = [
                SEL_USERNAME,
            ]
            
            # Get username from user data or prompt
            username = user.get("username") if user else None
            if not username:
                username = _safe_input("Enter username: ").strip()
                if not username:
                    print("❌ Username is required")
                    return
            
            username_filled = _try_fill_first(page, "username", username_selectors, username, timeout_ms=3000)
            
            if not username_filled:
                print("❌ Username field not found with confirmed selector. Enable --discovery to inspect UI.")
                return
            
            # Wait a moment for any dynamic updates
            page.wait_for_timeout(200)  # Reduced from 500ms
            
            # Find and click the submit/confirm button
            print("\n🔍 Looking for submit/confirm button...")
            button_selectors = [
                SEL_LOGIN_SUBMIT,
            ]
            button_clicked = _try_click_first(page, "login submit/next", button_selectors, timeout_ms=3000)
            
            if not button_clicked:
                print("❌ Login submit button not found with confirmed selector. Enable --discovery to inspect UI.")
                return
            
            # Wait for navigation after form submission
            if button_clicked or username_filled:
                print("\n⏳ Waiting for page navigation after form submission...")
                page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
                print(f"📍 Current URL after submission: {page.url}\n")
            
            # After confirmation, fill in birthday fields
            print("🔍 Waiting for birthday page to load...")
            page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
            # Avoid fixed sleeps; UI elements will be waited for explicitly below.
            
            # Debug: Print page content to help identify the element
            print(f"📍 Current URL: {page.url}")
            print(f"📄 Page Title: {page.title()}")
            
            print("🔍 Looking for birthday input fields...")
            birthday_filled = False
            
            # Get birth date from user data
            birth_day = None
            birth_month = None
            birth_month_czech = None
            if user and user.get("birthDate"):
                birth_day, birth_month = parse_birth_date(user.get("birthDate"))
                if birth_month:
                    birth_month_czech = get_czech_month_name(birth_month)
                print(f"📅 Parsed birth date: Day={birth_day}, Month={birth_month} ({birth_month_czech})")
            
            if not birth_day or not birth_month:
                print("⚠️  Birth date not found in user data, prompting...")
                birth_day = _safe_input("Enter birth day (e.g., 27): ").strip()
                birth_month = _safe_input("Enter birth month (e.g., 6): ").strip()
                if birth_month:
                    birth_month_czech = get_czech_month_name(birth_month)
            
            # Based on the HTML structure, these are combobox buttons (Radix UI)
            # Day combobox: button with "Den" text
            # Month combobox: button with "Měsíc" text
            day_filled = False
            month_filled = False

            # Fast path: if hidden selects are present, set values directly (avoids slow Radix UI interactions)
            try:
                selects = page.locator("select")
                if selects.count() >= 2:
                    day_select = selects.nth(0)
                    month_select = selects.nth(1)

                    t0 = time.perf_counter()
                    day_select.select_option(value=str(int(birth_day)), timeout=2000)
                    _tmark("day select[nth=0] select_option", t0)
                    day_filled = True

                    month_value = str(int(birth_month))  # "06" -> "6"
                    t0 = time.perf_counter()
                    month_select.select_option(value=month_value, timeout=2000)
                    _tmark("month select[nth=1] select_option", t0)
                    month_filled = True
            except Exception as e:
                # Continue with combobox-based fallback below
                print(f"INFO: select fast-path not used ({_safe_text(e)})")
            
            t_bday = time.perf_counter()
            if not day_filled:
                # Try to find day combobox button (contains "Den")
                print("🔍 Looking for day combobox (Den)...")
                try:
                    # Confirmed selector (discovery): combobox labeled "Den"
                    day_combobox = page.locator(SEL_BDAY_DAY_COMBO).first
                    t0 = time.perf_counter()
                    visible = day_combobox.is_visible(timeout=5000)
                    _tmark("day combobox visible", t0)
                    if visible:
                        print("✅ Found day combobox button")
                        # Click to open the dropdown
                        t0 = time.perf_counter()
                        day_combobox.click(timeout=2000, force=True, no_wait_after=True)
                        _tmark("day combobox click", t0)
                        # Wait until either hidden select or option list is ready (no fixed sleep)
                        
                        # Confirmed path: hidden <select> exists next to the combobox
                        day_select = day_combobox.locator('xpath=ancestor::div[1]//select').first
                        if day_select.count() > 0:
                            print(f"PASS: birthday day select selector=xpath=ancestor::div[1]//select value={birth_day}")
                            t0 = time.perf_counter()
                            day_select.select_option(value=birth_day, timeout=2000)
                            _tmark("day select_option", t0)
                            day_filled = True
                        else:
                            # Fallback: Radix renders options in a portal without a hidden <select>
                            t0 = time.perf_counter()
                            if not _select_radix_option_from_open_list(page, str(birth_day), timeout_ms=3000):
                                print("❌ Day selection failed (no hidden <select>, no option found). Run --discovery and share UI snapshot.")
                                return
                            _tmark("day option click", t0)
                            day_filled = True
                        # Close dropdown
                        try:
                            page.keyboard.press("Escape")
                        except:
                            pass
                        
                        if day_filled:
                            page.wait_for_timeout(50)
                except Exception as e:
                    print(f"⚠️  Error finding day combobox: {e}")
            
            # Wait a bit between day and month selection to ensure day selection is complete
            if day_filled and not month_filled:
                # Check if any dropdown is still open and close it
                try:
                    # Check if combobox is still expanded
                    open_combobox = page.locator('button[role="combobox"][aria-expanded="true"]').first
                    if open_combobox.is_visible(timeout=300):  # Reduced from 500ms
                        print("   Closing any open dropdown...")
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(50)
                except:
                    pass
            
            if not month_filled:
                # Try to find month combobox button (contains "Měsíc")
                print("🔍 Looking for month combobox (Měsíc)...")
                try:
                    # Confirmed selector (discovery): combobox labeled "Měsíc"
                    month_combobox = page.locator(SEL_BDAY_MONTH_COMBO).first
                    t0 = time.perf_counter()
                    visible = month_combobox.is_visible(timeout=5000)
                    _tmark("month combobox visible", t0)
                    if visible:
                        print("✅ Found month combobox button")
                        # Prefer hidden <select> (fast, avoids Radix portal/actionability waits)
                        month_select = month_combobox.locator('xpath=ancestor::div[1]//select').first
                        if month_select.count() > 0:
                            month_value = str(int(birth_month))  # "06" -> "6"
                            print(f"PASS: birthday month select selector=xpath=ancestor::div[1]//select value={month_value}")
                            t0 = time.perf_counter()
                            month_select.select_option(value=month_value, timeout=2000)
                            _tmark("month select_option", t0)
                            month_filled = True
                        else:
                            # Click to open the dropdown
                            t0 = time.perf_counter()
                            month_combobox.click(timeout=2000, force=True, no_wait_after=True)
                            _tmark("month combobox click", t0)

                            if birth_month_czech:
                                month_option = page.locator(f'[role="option"]:has-text("{birth_month_czech}")').first
                                t0 = time.perf_counter()
                                if not month_option.is_visible(timeout=2000):
                                    print(f"❌ Month option not visible: {birth_month_czech}. Enable --discovery to inspect UI.")
                                    return
                                _tmark("month option visible", t0)
                                print(f"PASS: birthday month option selector=[role=\"option\"] text={birth_month_czech}")
                                t0 = time.perf_counter()
                                month_option.click(timeout=2000, force=True, no_wait_after=True)
                                _tmark("month option click", t0)
                                month_filled = True
                            
                            if month_filled:
                                page.wait_for_timeout(50)
                                try:
                                    page.keyboard.press("Escape")
                                except:
                                    pass
                except Exception as e:
                    print(f"⚠️  Error finding month combobox: {e}")
            
            # If we couldn't find separate day/month fields, try a combined date field
            if not (day_filled and month_filled):
                print("❌ Birthday controls not filled with confirmed selectors. Enable --discovery to inspect UI.")
                return
            _tmark("birthday step total", t_bday)
            
            birthday_filled = (day_filled and month_filled) or birthday_filled
            
            # Wait a moment after filling
            if birthday_filled:
                page.wait_for_timeout(50)
            else:
                print("⚠️  Could not fill birthday fields automatically")
                page.wait_for_timeout(50)
            
            # Find and click continue button after filling birthday
            print("\n🔍 Looking for continue button after birthday entry...")
            continue_button_selectors = [
                SEL_BDAY_CONTINUE,
            ]
            continue_clicked = _try_click_first(page, "birthday continue", continue_button_selectors, timeout_ms=3000)
            
            if not continue_clicked:
                print("❌ Birthday continue button not found with confirmed selector. Enable --discovery to inspect UI.")
                return
            
            # Wait for navigation after continue
            if continue_clicked:
                print("\n⏳ Waiting for page navigation after continue...")
                page.wait_for_load_state("networkidle", timeout=10000)
                print(f"📍 Current URL after continue: {page.url}\n")
            
            # Check for auth method switch (mobile/SMS) - some environments show this before password
            print("🔍 Checking for auth method selection (mobile/SMS)...")
            page.wait_for_load_state("domcontentloaded", timeout=5000)
            page.wait_for_timeout(500)  # Give page time to render
            
            if DISCOVERY_MODE:
                log_visible_elements_snapshot(page, "Auth method selection screen")
            
            auth_method_switched = False
            try:
                # First check if we're already on SMS method (password field visible)
                try:
                    password_check = page.locator(SEL_PASSWORD).first
                    if password_check.is_visible(timeout=1000):
                        print("✅ Already on SMS authentication method (password field visible)")
                        auth_method_switched = True  # No switch needed, but mark as handled
                except:
                    pass
                
                # If not already on SMS, look for "Ověřit přes SMS" button/link
                if not auth_method_switched:
                    # Look for "Ověřit přes SMS" button (Verify via SMS option)
                    # Based on actual HTML: buttons are in a flex container, second button is "Ověřit přes SMS"
                    try:
                        # Wait for the container to be visible - give it more time
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                        page.wait_for_timeout(1000)  # Increased wait time
                        
                        # Try multiple approaches
                        sms_button = None
                        
                        # Approach 1: Find all buttons and check text content
                        print("   Searching for buttons with SMS text...")
                        try:
                            all_buttons = page.locator('button[type="button"]').all()
                            print(f"   Found {len(all_buttons)} button(s) with type='button'")
                            
                            for i, btn in enumerate(all_buttons):
                                try:
                                    if btn.is_visible(timeout=1000):
                                        btn_text = btn.text_content() or ""
                                        btn_text_lower = btn_text.lower().strip()
                                        print(f"   Button {i+1}: '{_safe_text(btn_text)}'")
                                        
                                        # Look for the specific text "ověřit přes sms"
                                        if "ověřit přes sms" in btn_text_lower:
                                            sms_button = btn
                                            print(f"✅ Found SMS auth method button by text: '{_safe_text(btn_text)}'")
                                            break
                                except Exception as e:
                                    print(f"   Button {i+1} check failed: {_safe_text(e)}")
                                    continue
                        except Exception as e:
                            print(f"   Button iteration failed: {_safe_text(e)}")
                        
                        # Approach 2: Use selector-based approach if text search didn't work
                        if not sms_button:
                            print("   Trying selector-based approach...")
                            sms_button_selectors = [
                                'button:has-text("Ověřit přes SMS")',
                                'button:has-text("ověřit přes SMS")',
                                'button >> text=/ověřit přes sms/i',
                                'button[type="button"]:has-text("Ověřit přes SMS")',
                                'button >> text="Ověřit přes SMS"',
                            ]
                            
                            for selector in sms_button_selectors:
                                try:
                                    btn = page.locator(selector).first
                                    if btn.is_visible(timeout=3000):
                                        button_text = btn.text_content() or ""
                                        print(f"✅ Found SMS auth method button: {selector}")
                                        print(f"   Button text: {_safe_text(button_text)}")
                                        sms_button = btn
                                        break
                                except Exception as e:
                                    print(f"   Selector {selector} failed: {_safe_text(e)}")
                                    continue
                        
                        # Click the button if found
                        if sms_button:
                            try:
                                # Scroll into view
                                sms_button.scroll_into_view_if_needed(timeout=2000)
                                page.wait_for_timeout(200)
                                
                                # Click the button
                                sms_button.click(timeout=5000)
                                auth_method_switched = True
                                print("✅ Clicked 'Ověřit přes SMS' button to switch to SMS authentication")
                                
                                # Wait for the page to update after switching
                                page.wait_for_load_state("domcontentloaded", timeout=5000)
                                page.wait_for_timeout(1000)
                            except Exception as e:
                                print(f"⚠️  Error clicking SMS button: {_safe_text(e)}")
                                auth_method_switched = False
                        else:
                            print("⚠️  SMS auth method button not found - may not be needed in this environment")
                            # Log all visible buttons for debugging
                            if DISCOVERY_MODE:
                                try:
                                    all_visible_buttons = page.locator('button').all()
                                    print(f"   Debug: Found {len(all_visible_buttons)} total button(s) on page")
                                    for i, btn in enumerate(all_visible_buttons[:5]):  # Limit to first 5
                                        try:
                                            if btn.is_visible(timeout=500):
                                                btn_text = btn.text_content() or ""
                                                print(f"   Button {i+1}: '{_safe_text(btn_text)}'")
                                        except:
                                            pass
                                except:
                                    pass
                    
                    except Exception as e:
                        print(f"⚠️  Error finding SMS button: {_safe_text(e)}")
                        import traceback
                        if DISCOVERY_MODE:
                            traceback.print_exc()
                
            except Exception as e:
                print(f"⚠️  Error checking for auth method switch: {_safe_text(e)}")
                # Continue anyway - might not be present in all environments
            
            if auth_method_switched:
                # Wait a bit more for the page to fully load after switching
                page.wait_for_load_state("domcontentloaded", timeout=3000)
                page.wait_for_timeout(500)
            
            # After date confirmation (and auth method switch if needed), fill in password field
            print("🔍 Looking for password field...")
            page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
            page.wait_for_timeout(300)  # Reduced from 1000ms

            if DISCOVERY_MODE:
                log_visible_elements_snapshot(page, "Password screen")
            
            # Get password from user data if not already set
            if not password:
                if user:
                    password = user.get("password")
                if not password:
                    password = _safe_input("Enter password: ").strip()
                    if not password:
                        print("❌ Password is required")
                        return
            
            password_filled = False
            
            # Confirmed selector (discovery): #password
            password_field = page.locator(SEL_PASSWORD).first
            try:
                password_field.wait_for(state='visible', timeout=5000)
                password_field.fill(password)
                password_filled = True
                print(f"PASS: password selector={SEL_PASSWORD}")
            except Exception as e:
                print(f"FAIL: password selector={SEL_PASSWORD} err={_safe_text(e)}")
                return
            
            # If that didn't work, try other selectors
            if not password_filled:
                password_selectors = [
                    SEL_PASSWORD,
                ]
                
                password_filled = _try_fill_first(page, "password", password_selectors, password, timeout_ms=3000)
            
            if not password_filled:
                print("⚠️  Could not find password field automatically")
                # Try to find any password input as last resort
                try:
                    print("   Trying to find any password input...")
                    all_password_inputs = page.locator('input[type="password"]').all()
                    print(f"   Found {len(all_password_inputs)} password input(s)")
                    if len(all_password_inputs) > 0:
                        for i, pwd_input in enumerate(all_password_inputs):
                            try:
                                if pwd_input.is_visible(timeout=2000):
                                    pwd_input.fill(password)
                                    password_filled = True
                                    print(f"✅ Password filled in password input #{i+1}")
                                    break
                            except:
                                continue
                except Exception as e:
                    print(f"⚠️  Error filling password: {e}")
            
            # Wait a moment after filling password
            if password_filled:
                page.wait_for_timeout(200) 
            
            # After password, handle SMS code (single OTP input field)
            print("\n🔍 Looking for SMS code input field...")
            page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
            page.wait_for_timeout(300)  

            if DISCOVERY_MODE:
                log_visible_elements_snapshot(page, "OTP screen")
            
            sms_code_filled = False
            sms_input_field = None
            
            # Try to find the OTP input field - it's a single field with data-input-otp="true"
            try:
                # Try exact OTP input selector first
                otp_selectors = [
                    SEL_OTP,
                ]
                
                for selector in otp_selectors:
                    try:
                        sms_input_field = page.locator(selector).first
                        sms_input_field.wait_for(state='visible', timeout=3000)
                        if sms_input_field.is_visible():
                            print(f"PASS: otp input selector={selector}")
                            break
                    except Exception as e:
                        print(f"FAIL: otp input selector={selector} err={_safe_text(e)}")
                        continue
                
                if not sms_input_field or not sms_input_field.is_visible():
                    print("❌ OTP input not found with confirmed selector. Enable --discovery to inspect UI.")
                    return
                
                # Retrieve and fill SMS code
                if sms_input_field and sms_input_field.is_visible():
                    print("\n" + "="*60)
                    print("📱 SMS CODE REQUIRED")
                    print("="*60)
                    
                    # If party_id not provided, prompt for it to enable automation
                    if party_id is None:
                        print("\n💡 To enable automatic SMS code retrieval, enter your Party ID.")
                        print("   (Press Enter to skip automation and enter code manually)")
                        party_id_input = _safe_input("Party ID (or press Enter for manual entry): ").strip()
                        
                        if party_id_input and party_id_input.isdigit():
                            party_id = int(party_id_input)
                            print(f"✅ Using Party ID: {party_id} for automatic retrieval")
                        else:
                            print("⚠️  No Party ID provided, will use manual entry")
                    
                    if party_id:
                        # Automated SMS OTP retrieval
                        print(f"\n🔍 Automatically retrieving SMS OTP for party ID: {party_id}")
                        print("   Waiting for SMS to arrive...")
                        try:
                            sms_code = wait_for_sms_otp(
                                api_request_context,
                                party_id,
                                timeout_seconds=60,
                                time_range_minutes=5
                            )
                            print(f"\n📝 Filling SMS code: {sms_code}")
                            sms_input_field.fill(sms_code)
                            sms_code_filled = True
                            print("✅ SMS code filled automatically")
                            page.wait_for_timeout(200)  # Reduced from 500ms
                        except Exception as e:
                            print(f"\n⚠️  Failed to retrieve SMS OTP automatically: {e}")
                            import traceback
                            print("\n📋 Full error details:")
                            traceback.print_exc()
                            print("\n   Falling back to manual entry...")
                            # Fall back to manual entry
                            while True:
                                sms_code = _safe_input("SMS Code (6 digits): ").strip()
                                if len(sms_code) == 6 and sms_code.isdigit():
                                    break
                                print("⚠️  Please enter exactly 6 digits")
                            sms_input_field.fill(sms_code)
                            sms_code_filled = True
                            print("✅ SMS code filled manually")
                            page.wait_for_timeout(500)
                    else:
                        # Manual entry (no party_id provided)
                        print("\nPlease enter the 6-digit SMS code:")
                        while True:
                            sms_code = _safe_input("SMS Code (6 digits): ").strip()
                            if len(sms_code) == 6 and sms_code.isdigit():
                                break
                            print("⚠️  Please enter exactly 6 digits")
                        
                        print(f"\n📝 Filling SMS code: {sms_code}")
                        try:
                            sms_input_field.fill(sms_code)
                            sms_code_filled = True
                            print("✅ SMS code filled")
                            page.wait_for_timeout(200)  # Reduced from 500ms
                        except Exception as e:
                            print(f"⚠️  Error filling SMS code: {e}")
                else:
                    print("⚠️  Could not find SMS code input field")
                    
            except Exception as e:
                print(f"⚠️  Error handling SMS code: {e}")
                import traceback
                traceback.print_exc()
            
            # Variables to capture redirect URL
            redirect_url = None
            redirect_captured = False
            
            # After SMS code is filled, click the confirm button
            if sms_code_filled:
                print("\n🔍 Looking for confirm button after SMS code entry...")
                page.wait_for_timeout(200)  # Reduced from 500ms
                
                # Set up response listener to capture redirect URL
                
                def handle_response(response):
                    nonlocal redirect_url, redirect_captured
                    if redirect_captured:
                        return  # Already captured
                    
                    response_url = response.url
                    response_status = response.status
                    
                    # Check if this is a redirect response
                    if response_status in [301, 302, 303, 307, 308]:
                        location = response.headers.get('location', '')
                        if location:
                            # Handle relative URLs
                            if location.startswith('http'):
                                redirect_url = location
                            else:
                                # Construct absolute URL
                                from urllib.parse import urljoin
                                redirect_url = urljoin(response_url, location)
                            
                            if redirect_uri in redirect_url or 'tpp.example.com' in redirect_url:
                                redirect_captured = True
                                print(f"\n✅ Captured redirect URL from Location header: {redirect_url}")
                    
                    # Also check if the response URL itself is the redirect
                    if not redirect_captured and (redirect_uri in response_url or 'tpp.example.com' in response_url):
                        redirect_url = response_url
                        redirect_captured = True
                        print(f"\n✅ Captured redirect URL from response URL: {redirect_url}")
                
                # Listen for responses
                page.on("response", handle_response)
                
                confirm_clicked = _try_click_first(
                    page,
                    "otp confirm/continue",
                    [SEL_OTP_CONFIRM],
                    timeout_ms=3000
                )
                
                if not confirm_clicked:
                    print("❌ OTP confirm button not found with confirmed selector. Enable --discovery to inspect UI.")
                    return
                
                # Wait for navigation or redirect capture
                if confirm_clicked:
                    print("\n⏳ Waiting for redirect response...")
                    # Wait a bit for the response to be captured
                    for i in range(30):  # Wait up to 3 seconds
                        if redirect_captured:
                            break
                        page.wait_for_timeout(50)  # Reduced from 100ms

                    # Some flows show intermediate pages (can "blink") and then land on a profile selection
                    # page where user must pick at least one profile (consents.* checkbox) before redirect.
                    #
                    # To make this robust, poll up to ~30s for *either*:
                    # - redirect captured, OR
                    # - redirect URL visible, OR
                    # - consents checkbox appears -> select -> Pokračovat
                    profile_done = False
                    for _ in range(300):  # ~30s
                        if redirect_captured:
                            break

                        # If the browser already navigated to redirect_uri, stop waiting.
                        try:
                            if redirect_uri and page.url and page.url.startswith(redirect_uri):
                                break
                        except Exception:
                            pass

                        # Detect profile selection by the actual checkbox id prefix (most stable)
                        try:
                            consent_btn = page.locator('button[role="checkbox"][id^="consents."]').first
                            if consent_btn.is_visible(timeout=100):
                                print("\n🔍 Detected profile selection (consents.* checkbox)")
                                if DISCOVERY_MODE:
                                    log_visible_elements_snapshot(page, "Profile selection page")

                                aria_checked = (consent_btn.get_attribute("aria-checked") or "").lower()
                                if aria_checked != "true":
                                    consent_btn.click(timeout=2000, force=True, no_wait_after=True)
                                    page.wait_for_timeout(100)
                                aria_checked_after = (consent_btn.get_attribute("aria-checked") or "").lower()
                                if aria_checked_after != "true":
                                    print("❌ Profile checkbox click did not set aria-checked=true")
                                    return

                                print('PASS: profile checkbox selected')
                                cont = page.locator('button:has-text("Pokračovat"), button[type="submit"]').first
                                cont.click(timeout=3000, force=True, no_wait_after=True)
                                print('PASS: profile selection continue clicked ("Pokračovat")')
                                profile_done = True
                                # Give backend a moment to emit the redirect
                                page.wait_for_timeout(200)
                                break
                        except Exception:
                            pass

                        page.wait_for_timeout(100)
                    
                    if not redirect_captured:
                        # Try waiting for navigation
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=3000)  # Faster than networkidle
                            print(f"📍 Current URL after confirmation: {page.url}\n")
                        except:
                            pass
            
            # Process the captured redirect URL or wait for navigation
            print("\n" + "="*60)
            print("📋 PROCESSING REDIRECT")
            print("="*60)
            
            final_url = None
            auth_code = None
            
            # Check if we captured the redirect URL from the response
            if redirect_captured and redirect_url:
                final_url = redirect_url
                print(f"✅ Using captured redirect URL: {final_url}\n")
            else:
                # Try to get it from the current page URL
                print("⏳ Checking current page URL...")
                try:
                    # Wait a bit more for any navigation
                    page.wait_for_timeout(2000)  # Wait longer for redirect
                    current_url = page.url
                    print(f"📍 Current URL: {current_url}")
                    
                    # Check if current URL contains the redirect URI or code parameter
                    if redirect_uri in current_url or 'tpp.example.com' in current_url or 'code=' in current_url:
                        final_url = current_url
                        print(f"✅ Found redirect URL from page: {final_url}\n")
                    else:
                        # Try waiting for navigation with a more flexible check
                        print(f"⏳ Waiting for navigation (checking for code parameter)...")
                        print(f"Expected redirect URI: {redirect_uri}\n")
                        try:
                            # Wait for URL that contains 'code=' parameter (more flexible)
                            page.wait_for_url(
                                lambda url: 'code=' in url or redirect_uri in url or url.startswith(redirect_uri),
                                timeout=10000  # 10 seconds timeout
                            )
                            final_url = page.url
                            print(f"✅ Navigated to: {final_url}\n")
                        except Exception as nav_error:
                            print(f"⚠️  Navigation wait timeout: {nav_error}")
                            # Still try to use current URL - it might have the code
                            current_url = page.url
                            if 'code=' in current_url:
                                final_url = current_url
                                print(f"✅ Found code in current URL: {final_url}\n")
                            else:
                                print(f"⚠️  Current URL doesn't contain code parameter")
                                print(f"Current URL: {current_url}")
                                try:
                                    page_title = page.title()
                                    print(f"Page Title: {page_title}")
                                except:
                                    print(f"Page Title: (could not retrieve)")
                except Exception as e:
                    print(f"⚠️  Error checking URL: {e}")
                    # Still try to get current URL
                    try:
                        current_url = page.url
                        if 'code=' in current_url:
                            final_url = current_url
                            print(f"✅ Found code in URL despite error: {final_url}\n")
                    except:
                        pass
            
            # If we still don't have a URL with code, try to extract from page content
            if not final_url or 'code=' not in final_url:
                print("⏳ Trying to extract code from page content...")
                try:
                    # Wait for page to be stable
                    page.wait_for_timeout(1000)
                    
                    # Try to find code in URL parameters from current URL
                    current_url = page.url
                    if 'code=' in current_url:
                        final_url = current_url
                        print(f"✅ Found code in current URL: {final_url}\n")
                    else:
                        # Try to get code from page content (if displayed)
                        try:
                            # Look for code in various possible locations
                            page_content = page.content()
                            
                            # Try to find code in URL-like patterns in the page
                            import re
                            code_pattern = r'code=([^&\s"\'<>]+)'
                            matches = re.findall(code_pattern, page_content)
                            if matches:
                                auth_code = matches[0]
                                print(f"✅ Found authorization code in page content: {auth_code[:50]}...")
                                # Construct URL for parsing
                                final_url = f"{redirect_uri}?code={auth_code}&state={state}"
                        except Exception as content_error:
                            print(f"⚠️  Could not extract from page content: {content_error}")
                except Exception as extract_error:
                    print(f"⚠️  Error during code extraction: {extract_error}")
            
            # Parse the redirect URL to extract query parameters
            if final_url:
                try:
                    # Parse the URL to extract query parameters (like authorization code)
                    parsed_url = urlparse(final_url)
                    query_params = parse_qs(parsed_url.query)
                    
                    print("📋 Query Parameters from redirected URL:")
                    for key, value in query_params.items():
                        print(f"  {key}: {value[0] if len(value) == 1 else value}")
                    
                    # Check for authorization code
                    auth_code = None
                    if 'code' in query_params:
                        auth_code = query_params['code'][0]
                        print(f"\n🎉 Authorization Code received: {auth_code}")
                    else:
                        # Try to extract code directly from URL string
                        if 'code=' in final_url:
                            try:
                                code_match = final_url.split('code=')[1].split('&')[0].split('?')[0]
                                if code_match:
                                    auth_code = code_match
                                    print(f"\n🎉 Authorization Code extracted from URL: {auth_code}")
                            except:
                                pass
                    
                    # Check if auth_code was extracted from page content earlier
                    if not auth_code and 'auth_code' in locals():
                        # Code was extracted from page content earlier
                        print(f"\n🎉 Authorization Code extracted: {auth_code}")
                    
                    # Save authorization code if we have it
                    if auth_code:
                        auth_code_file = str(get_database_file("last_authorization_code.json"))
                        try:
                            # Create new auth code entry
                            auth_data = {
                                "state": state,
                                "authorization_code": auth_code,
                                "client_id": client_id,
                                "user": party_id,  # Save party_id as user
                                "redirect_uri": redirect_uri,
                                "scope": scope,
                                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                            }
                            
                            # Use thread-safe update function with file locking
                            def update_auth_codes(collection):
                                """Update function for safe concurrent access"""
                                # Handle both old format (single object) and new format (collection)
                                if "authorization_codes" not in collection:
                                    # Convert old format to new format
                                    if collection and "authorization_code" in collection:
                                        collection = {"authorization_codes": [collection]}
                                    else:
                                        collection = {"authorization_codes": []}
                                
                                # Remove existing entry with same state (if any) and add new one
                                collection["authorization_codes"] = _open_auth_codes(
                                    collection["authorization_codes"],
                                    state,
                                )
                                collection["authorization_codes"].append(auth_data)
                                return collection
                            
                            if safe_update_json(auth_code_file, update_auth_codes, default_value={"authorization_codes": []}):
                                print(f"💾 Authorization code saved to: {auth_code_file} (state: {state})")
                            else:
                                print(f"⚠️  Failed to save authorization code to: {auth_code_file}")
                            
                            # Close browser automatically after successful extraction
                            print("\n✅ Authorization code extracted and saved successfully!")
                            print("   Closing browser...")
                            return  # Exit function, browser will be closed in finally block
                        except Exception as e:
                            print(f"⚠️  Could not save authorization code: {e}")
                    else:
                        print("\n⚠️  Could not extract authorization code from redirect URL")
                    
                    # Check for state parameter
                    if 'state' in query_params:
                        returned_state = query_params['state'][0]
                        print(f"🔑 State parameter: {returned_state}")
                        if returned_state == state:
                            print("✅ State parameter matches (CSRF protection verified)")
                        else:
                            print(f"⚠️  State parameter mismatch! Expected: {state}, Got: {returned_state}")
                    
                    # Check for errors
                    if 'error' in query_params:
                        error = query_params['error'][0]
                        error_description = query_params.get('error_description', [''])[0]
                        print(f"\n❌ OAuth Error: {error}")
                        if error_description:
                            print(f"   Description: {error_description}")
                    
                    if auth_code:
                        print("\n✅ Test completed: Successfully captured redirect URL and authorization code")
                    else:
                        print("\n⚠️  Redirect URL captured but authorization code not found")
                    
                except Exception as e:
                    print(f"⚠️  Error parsing redirect URL: {e}")
                    print(f"   URL: {final_url}")
                    
                    # Try to extract code directly from URL string as fallback
                    if final_url and 'code=' in final_url:
                        try:
                            code_match = final_url.split('code=')[1].split('&')[0].split('?')[0]
                            if code_match:
                                auth_code = code_match
                                print(f"\n🎉 Authorization Code extracted from URL (fallback): {auth_code}")
                                
                                # Save it
                                auth_code_file = str(get_database_file("last_authorization_code.json"))
                                try:
                                    # Create new auth code entry
                                    auth_data = {
                                        "state": state,
                                        "authorization_code": auth_code,
                                        "client_id": client_id,
                                        "user": party_id,
                                        "redirect_uri": redirect_uri,
                                        "scope": scope,
                                        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                                    }
                                    
                                    # Use thread-safe update function with file locking
                                    def update_auth_codes(collection):
                                        """Update function for safe concurrent access"""
                                        if "authorization_codes" not in collection:
                                            if collection and "authorization_code" in collection:
                                                collection = {"authorization_codes": [collection]}
                                            else:
                                                collection = {"authorization_codes": []}
                                        
                                        collection["authorization_codes"] = _open_auth_codes(
                                            collection["authorization_codes"],
                                            state,
                                        )
                                        collection["authorization_codes"].append(auth_data)
                                        return collection
                                    
                                    if safe_update_json(auth_code_file, update_auth_codes, default_value={"authorization_codes": []}):
                                        print(f"💾 Authorization code saved to: {auth_code_file} (state: {state})")
                                    else:
                                        print(f"⚠️  Failed to save authorization code to: {auth_code_file}")
                                    print("\n✅ Authorization code extracted and saved successfully!")
                                    return  # Exit function, browser will be closed
                                except Exception as save_error:
                                    print(f"⚠️  Could not save authorization code: {save_error}")
                        except:
                            pass
            else:
                print(f"\n⏱️  Could not capture redirect URL automatically")
                print(f"Current URL: {page.url}")
                try:
                    print(f"Page Title: {page.title()}")
                except:
                    print(f"Page Title: (could not retrieve)")
                
                # Try one more time to extract code from current URL
                try:
                    current_url = page.url
                    if 'code=' in current_url:
                        code_match = current_url.split('code=')[1].split('&')[0].split('?')[0]
                        if code_match:
                            auth_code = code_match
                            print(f"\n🎉 Authorization Code found in current URL: {auth_code}")
                            
                            # Save it
                            auth_code_file = str(PROJECT_ROOT / "Database" / "last_authorization_code.json")
                            try:
                                # Load existing collection
                                auth_codes_collection = {"authorization_codes": []}
                                if os.path.exists(auth_code_file):
                                    try:
                                        with open(auth_code_file, 'r', encoding='utf-8') as f:
                                            auth_codes_collection = json.load(f)
                                            if "authorization_codes" not in auth_codes_collection:
                                                auth_codes_collection["authorization_codes"] = []
                                    except:
                                        auth_codes_collection = {"authorization_codes": []}
                                
                                # Create new auth code entry
                                auth_data = {
                                    "state": state,
                                    "authorization_code": auth_code,
                                    "client_id": client_id,
                                    "user": party_id,
                                    "redirect_uri": redirect_uri,
                                    "scope": scope,
                                    "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                                }
                                
                                # Remove existing entry with same state (if any) and add new one
                                auth_codes_collection["authorization_codes"] = _open_auth_codes(
                                    auth_codes_collection["authorization_codes"],
                                    state,
                                )
                                auth_codes_collection["authorization_codes"].append(auth_data)
                                
                                with open(auth_code_file, 'w', encoding='utf-8') as f:
                                    json.dump(auth_codes_collection, f, indent=2)
                                print(f"💾 Authorization code saved to: {auth_code_file} (state: {state})")
                                print("\n✅ Authorization code extracted and saved successfully!")
                                print("   Closing browser...")
                                return  # Exit function, browser will be closed
                            except Exception as save_error:
                                print(f"⚠️  Could not save authorization code: {save_error}")
                except Exception as extract_error:
                    print(f"⚠️  Could not extract code from URL: {extract_error}")
                
                print("\n💡 The redirect may have failed or the server is not responding")
                print("   Please check the browser window for the authorization code.")
                print("   The browser will close automatically in 5 seconds...")
                page.wait_for_timeout(5000)  # Wait 5 seconds for manual inspection
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
            print("\n   Closing browser in 3 seconds...")
            page.wait_for_timeout(3000)  # Wait 3 seconds before closing
        
        finally:
            api_request_context.dispose()
            browser.close()
            print("✅ Browser closed")


if __name__ == "__main__":
    # Fix Windows console encoding for Unicode characters
    if sys.platform == 'win32':
        try:
            # Try to set console output encoding to UTF-8
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            # Fallback: wrap stdout/stderr with UTF-8 encoding
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='OAuth2 Authorization Flow')
    parser.add_argument('--client-id', type=str, help='Client ID from context (GUI)')
    parser.add_argument('--user-id', type=str, help='User ID (party_id) from context (GUI)')
    parser.add_argument('--discovery', action='store_true', help='Log visible UI elements + log which selectors pass')
    args = parser.parse_args()

    # Enable selector discovery logging (helps remove guessing)
    DISCOVERY_MODE = bool(args.discovery)
    
    try:
        # If arguments provided (from GUI), use them
        if args.client_id and args.user_id:
            test_oauth2_authorize_endpoint(client_id=args.client_id, user_id=args.user_id)
        else:
            # Otherwise, use default config (console mode)
            # You can provide party_id as argument for automated SMS retrieval
            # Option 1: Provide party_id directly for full automation (recommended)
            # Option 2: Pass None and you'll be prompted for party_id when SMS code is needed
            # Option 3: Pass None and skip party_id prompt to enter SMS code manually
            # Load party_id from default_auth_config.json if available
            auth_config = load_default_auth_config()
            party_id = None
            if auth_config and auth_config.get("partyId"):
                try:
                    party_id = int(auth_config.get("partyId"))
                except:
                    pass
            
            test_oauth2_authorize_endpoint(party_id=party_id)
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}"
        print(error_msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

