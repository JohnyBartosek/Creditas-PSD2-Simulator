"""
TPP User Account List
Based on Bruno/AccountList.bru
Fetches account list for a user using access token from database
"""

import sys
import io

# Fix Windows console encoding for Unicode characters (emojis)
if sys.platform == 'win32':
    try:
        # Try to set console output encoding to UTF-8
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Fallback: wrap stdout/stderr with UTF-8 encoding
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import json
import os
import uuid
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

# Add parent directory to path for imports
import sys
from pathlib import Path

# Get the parent directory (project root)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

# Import environment config
from Helpers.environment_config import get_accounts_list_url, get_database_file

# Database files (environment-aware paths)
DATABASE_FILE = str(get_database_file("tpp_registrations.json"))
TOKEN_RESPONSE_FILE = str(get_database_file("tpp_tokens.json"))
DEFAULT_AUTH_CONFIG_FILE = str(get_database_file("default_auth_config.json"))
USERS_FILE = str(get_database_file("users.json"))

# Import environment config
from Helpers.environment_config import get_accounts_list_url

# X-Client-Certificate header (from Bruno file)
X_CLIENT_CERTIFICATE = """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"""


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


def load_tokens_database():
    """Load tokens database from JSON file"""
    if os.path.exists(TOKEN_RESPONSE_FILE):
        try:
            with open(TOKEN_RESPONSE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading tokens database: {e}")
            return {"tokens": []}
    return {"tokens": []}


def get_token_from_database(client_id: str, user: int = None):
    """Get token from database for given client_id and optionally user"""
    database = load_tokens_database()
    
    for token in database.get("tokens", []):
        if token.get("client_id") == client_id:
            if user is None or token.get("user") == user:
                return token
    
    return None


def ensure_access_token(client_id: str, user: int):
    """Return a usable access token, refreshing it when the current one is expired."""
    import subprocess
    from pathlib import Path

    from Helpers.access_token_helper import is_token_expired

    token_data = get_token_from_database(client_id, user)
    access_token = (token_data or {}).get("access_token") or ""
    if not access_token:
        print(f"❌ Could not find token for client_id: {client_id}, user: {user}")
        print("   Make sure you have completed authorization and token exchange")
        return None
    if not is_token_expired(access_token):
        return access_token

    print("⚠️  Access token is expired. Refreshing...")
    script = Path(__file__).parent / "TPP_GetTokenFromRefreshToken.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--client-id", str(client_id), "--user-id", str(user)],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    token_data = get_token_from_database(client_id, user)
    access_token = (token_data or {}).get("access_token") or ""
    if completed.returncode != 0 or not access_token or is_token_expired(access_token):
        detail = (completed.stderr or completed.stdout or "").strip()
        print("❌ Token refresh failed.")
        if detail:
            print(detail.split("📄 Response Body:", 1)[0].strip())
        return None
    print("✅ Access token refreshed.")
    return access_token


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
        
        # Get timestamp
        timestamp = registration.get("timestamp", "Unknown")
        
        clients.append({
            "index": idx,
            "client_name": client_name,
            "client_id": client_id,
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
        print(f"      Registered: {client['timestamp']}")
        print()
    
    while True:
        try:
            selection = input(f"Select TPP client (1-{len(clients)}) or 'q' to quit: ").strip()
            
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
            selection = input(f"Select user (1-{len(users)}) or 'q' to quit: ").strip()
            
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


def get_client_name_by_id(client_id: str):
    """Get client_name (TPP-Name) from database for given client_id"""
    database = load_database()
    
    for registration in database.get("registrations", []):
        response_body = registration.get("response", {}).get("body", {})
        if isinstance(response_body, dict):
            reg_client_id = response_body.get("client_id")
            if reg_client_id == client_id:
                # Try to get client_name from request body first
                request_body = registration.get("request", {}).get("body", {})
                client_name = request_body.get("client_name", "")
                if not client_name:
                    client_name = response_body.get("client_name", "")
                return client_name
    
    return None


def generate_request_id():
    """Generate a GUID for X-Request-ID"""
    return str(uuid.uuid4())


def format_request_date():
    """Format current date/time for X-Request-Date header"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def test_get_account_list(client_id: str = None, user_id: str = None, page: int = 0, size: int = 100):
    """
    Fetch account list for a user
    
    Args:
        client_id: Client ID to use. If None, will try to load from default config or prompt.
        user_id: User ID (party_id as string). If None, will try to load from default config or prompt.
        page: Page number for pagination (default: 0)
        size: Page size (default: 100)
    """
    # GUI mode: If client_id and user_id are provided, use them directly
    if client_id and user_id:
        try:
            user = int(user_id)
        except:
            print(f"⚠️  Invalid user_id provided: {user_id}. Must be an integer.")
            return
        
        print(f"✅ Using context: Client={client_id}, User={user_id}")
    else:
        # Console mode: Load default config or let user choose
        auth_config = load_default_auth_config()
        
        if not auth_config:
            # No default config: Let user choose client and user
            print("="*60)
            print("CONSOLE MODE - SELECT CLIENT AND USER")
            print("="*60)
            print()
            
            # Select TPP client
            selected_client = select_client()
            if not selected_client:
                return
            client_id = selected_client['client_id']
            
            # Select user
            print()
            selected_user = select_user()
            if not selected_user:
                return
            
            try:
                user = int(selected_user.get('partyId'))
            except:
                print(f"⚠️  Could not parse partyId '{selected_user.get('partyId')}' as integer")
                user_input = input("Enter User (Party ID) or press Enter to cancel: ").strip()
                if not user_input or not user_input.isdigit():
                    print("❌ User (Party ID) is required")
                    return
                user = int(user_input)
            
            print(f"✅ Selected: Client={selected_client['client_name']}, User={selected_user.get('name')} (Party ID: {user})")
        else:
            # Default config exists: Ask if user wants to use it or choose manually
            config_party_id = auth_config.get("partyId")
            config_client_name = auth_config.get("client_id")
            
            print("="*60)
            print("CONSOLE MODE - USING DEFAULT CONFIG")
            print("="*60)
            print(f"Default Client: {config_client_name}")
            print(f"Default User (Party ID): {config_party_id}")
            print()
            
            # Ask if user wants to use default config or choose manually
            use_default = input("Use default configuration? (Y/n): ").strip().lower()
            
            if use_default and use_default != 'n':
                # Use default config
                # Find TPP client by client_name
                database = load_database()
                selected_client = None
                for registration in database.get("registrations", []):
                    request_body = registration.get("request", {}).get("body", {})
                    reg_client_name = request_body.get("client_name", "")
                    if not reg_client_name:
                        response_body = registration.get("response", {}).get("body", {})
                        if isinstance(response_body, dict):
                            reg_client_name = response_body.get("client_name", "")
                    
                    if reg_client_name == config_client_name:
                        response_body = registration.get("response", {}).get("body", {})
                        if isinstance(response_body, dict):
                            client_id = response_body.get("client_id")
                            if client_id:
                                selected_client = {
                                    "client_name": reg_client_name,
                                    "client_id": client_id
                                }
                                break
                
                if not selected_client:
                    print(f"❌ Could not find TPP client '{config_client_name}' in database!")
                    print(f"   Database file: {DATABASE_FILE}")
                    return
                
                client_id = selected_client['client_id']
                
                # Load user data
                user_obj = get_user_by_party_id(config_party_id)
                if not user_obj:
                    print(f"⚠️  Could not find user with partyId '{config_party_id}' in users database!")
                    print(f"   Users file: {USERS_FILE}")
                    print("   Please enter Party ID manually:")
                    user_input = input("Enter User (Party ID): ").strip()
                    if not user_input or not user_input.isdigit():
                        print("❌ User (Party ID) is required")
                        return
                    user = int(user_input)
                else:
                    try:
                        user = int(config_party_id)
                        print(f"✅ Loaded user: {user_obj.get('name')} (Party ID: {config_party_id})")
                    except:
                        print(f"⚠️  Could not parse partyId '{config_party_id}' as integer")
                        user_input = input("Enter User (Party ID): ").strip()
                        if not user_input or not user_input.isdigit():
                            print("❌ User (Party ID) is required")
                            return
                        user = int(user_input)
            else:
                # Manual selection
                print()
                print("Manual selection mode...")
                
                # Select TPP client
                selected_client = select_client()
                if not selected_client:
                    return
                client_id = selected_client['client_id']
                
                # Select user
                print()
                selected_user = select_user()
                if not selected_user:
                    return
                
                try:
                    user = int(selected_user.get('partyId'))
                except:
                    print(f"⚠️  Could not parse partyId '{selected_user.get('partyId')}' as integer")
                    user_input = input("Enter User (Party ID) or press Enter to cancel: ").strip()
                    if not user_input or not user_input.isdigit():
                        print("❌ User (Party ID) is required")
                        return
                    user = int(user_input)
                
                print(f"✅ Selected: Client={selected_client['client_name']}, User={selected_user.get('name')} (Party ID: {user})")
    
    if not client_id:
        print("❌ Client ID is required")
        return
    
    if not user:
        print("❌ User (Party ID) is required")
        return
    
    # Get access token from database
    token_data = get_token_from_database(client_id, user)
    if not token_data:
        print(f"❌ Could not find token for client_id: {client_id}, user: {user}")
        print("   Make sure you have completed authorization and token exchange")
        return
    
    access_token = token_data.get("access_token")
    if not access_token:
        print(f"❌ No access token found for client_id: {client_id}, user: {user}")
        return
    
    # Check if access token is expired
    try:
        import sys
        from pathlib import Path
        parent_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(parent_dir))
        from Helpers.access_token_helper import is_token_expired
        if is_token_expired(access_token):
            print(f"⚠️  Access token is expired. Please refresh the token first.")
            return
    except Exception as e:
        print(f"⚠️  Could not check token expiration: {e}")
        # Continue anyway
    
    # Get client name (TPP-Name) from database
    client_name = get_client_name_by_id(client_id)
    if not client_name:
        print(f"⚠️  Could not find client name for client_id: {client_id}, using client_id as fallback")
        client_name = client_id
    
    # Generate request ID and date
    request_id = generate_request_id()
    request_date = format_request_date()
    
    # Build URL with query parameters
    params = {
        "page": page,
        "size": size
    }
    account_list_url = get_accounts_list_url()
    url = f"{account_list_url}?{urlencode(params)}"
    
    print("="*60)
    print("ACCOUNT LIST REQUEST")
    print("="*60)
    print(f"URL: {url}")
    print(f"Client ID: {client_id}")
    print(f"Client Name (TPP-Name): {client_name}")
    print(f"User (Party ID): {user}")
    print(f"Page: {page}")
    print(f"Size: {size}")
    print(f"X-Request-ID: {request_id}")
    print(f"X-Request-Date: {request_date}")
    print("="*60)
    print()
    
    with sync_playwright() as p:
        # Create API request context with SSL verification disabled
        api_request_context = p.request.new_context(ignore_https_errors=True)
        
        try:
            # Sanitize client_name for header (remove non-ASCII characters and control chars)
            # HTTP headers should only contain ASCII printable characters
            # Remove all non-ASCII characters (including accented/national characters)
            sanitized_client_name = re.sub(r'[^\x20-\x7E]', '', str(client_name)).strip()
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "X-Request-ID": request_id,
                "X-Request-Date": request_date,
                "User-Involved": "false",
                "TPP-Name": sanitized_client_name,
                "X-TPP-Authorization": f"Bearer {access_token}",
                "X-Client-Cert": X_CLIENT_CERTIFICATE
            }
            
            print("📡 Making GET request to account list endpoint...")
            print(f"\n📤 Headers:")
            print(f"   X-Request-ID: {request_id}")
            print(f"   X-Request-Date: {request_date}")
            print(f"   TPP-Name: {client_name}")
            print(f"   X-TPP-Authorization: Bearer {access_token[:50]}...")
            print(f"   X-Client-Cert: (certificate)")
            
            # Make GET request
            response = api_request_context.get(url, headers=headers)
            
            # Get response details
            status = response.status
            print(f"\n📥 Response Status: {status}")
            print(f"📋 Response Headers: {dict(response.headers)}")
            
            # Get response body
            try:
                response_body = response.json()
                print(f"\n📄 Response Body:")
                print(json.dumps(response_body, indent=2))
                
                # Check if successful
                if status == 200:
                    print("\n✅ Account list retrieved successfully!")
                    
                    # Extract account information
                    accounts = response_body.get("accounts", [])
                    if isinstance(accounts, list):
                        print(f"\n📋 Found {len(accounts)} account(s):")
                        for idx, account in enumerate(accounts, 1):
                            print(f"\n  Account {idx}:")
                            if isinstance(account, dict):
                                for key, value in account.items():
                                    print(f"    {key}: {value}")
                    else:
                        print(f"\n📋 Account data: {accounts}")
                else:
                    print(f"\n⚠️  Request failed with status {status}")
                    if "error" in response_body:
                        error = response_body.get("error", "")
                        error_description = response_body.get("error_description", "")
                        print(f"   Error: {error}")
                        if error_description:
                            print(f"   Description: {error_description}")
            except:
                response_text = response.text()
                print(f"\n📄 Response Body (text):")
                print(response_text[:1000])  # First 1000 chars
            
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"\n❌ Request failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            api_request_context.dispose()


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Fetch Account List')
    parser.add_argument('--client-id', type=str, help='Client ID from context (GUI)')
    parser.add_argument('--user-id', type=str, help='User ID (party_id) from context (GUI)')
    parser.add_argument('--page', type=int, default=0, help='Page number (default: 0)')
    parser.add_argument('--size', type=int, default=100, help='Page size (default: 100)')
    args = parser.parse_args()
    
    # If arguments provided (from GUI), use them
    if args.client_id and args.user_id:
        test_get_account_list(client_id=args.client_id, user_id=args.user_id, page=args.page, size=args.size)
    else:
        # Console mode: use latest token or prompt
        test_get_account_list(page=args.page, size=args.size)

