"""
TPP Get Token From Refresh Token
Based on Bruno/COA Token - refresh.bru
Exchanges refresh token for new access token using TPP credentials from database
"""

from playwright.sync_api import sync_playwright
import json
import os
import sys
import base64
import argparse
from urllib.parse import urlencode
from datetime import datetime, timezone
from pathlib import Path

# Get the parent directory (project root)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.environment_config import get_oauth_token_url, get_database_file

# Database files (environment-aware paths)
DATABASE_FILE = str(get_database_file("tpp_registrations.json"))
TOKEN_RESPONSE_FILE = str(get_database_file("tpp_tokens.json"))

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


def get_client_credentials(client_id: str):
    """Get client_id and client_secret from database for given client_id"""
    database = load_database()
    
    for registration in database.get("registrations", []):
        response_body = registration.get("response", {}).get("body", {})
        if isinstance(response_body, dict):
            reg_client_id = response_body.get("client_id")
            if reg_client_id == client_id:
                client_secret = response_body.get("client_secret")
                redirect_uris = response_body.get("redirect_uris", [])
                scope = response_body.get("scope") or response_body.get("scopes", "")
                return {
                    "client_id": reg_client_id,
                    "client_secret": client_secret,
                    "redirect_uris": redirect_uris,
                    "scope": scope
                }
    
    return None


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


def list_available_tokens_for_client(client_id: str):
    """List all available tokens (users) for a given client_id"""
    database = load_tokens_database()
    tokens = []
    
    for token in database.get("tokens", []):
        if token.get("client_id") == client_id:
            tokens.append(token)
    
    return tokens


def save_token_to_database(client_id: str, user: int, token_response: dict):
    """Save or update token in database, organized by client_id and user"""
    database = load_tokens_database()
    
    # Find existing token entry
    token_entry = None
    existing_token = None
    for idx, token in enumerate(database.get("tokens", [])):
        if token.get("client_id") == client_id and token.get("user") == user:
            token_entry = idx
            existing_token = token
            break
    
    # Preserve refresh_token_created from existing token if it exists
    refresh_token_created = None
    if existing_token and existing_token.get("refresh_token_created"):
        refresh_token_created = existing_token.get("refresh_token_created")
    elif token_response.get("refresh_token_created"):
        refresh_token_created = token_response.get("refresh_token_created")
    
    # Prepare token entry
    token_data = {
        "client_id": client_id,
        "user": user,
        "refresh_token": token_response.get("refresh_token", ""),
        "access_token": token_response.get("access_token", ""),
        "scope": token_response.get("scope", ""),
        "token_type": token_response.get("token_type", "Bearer"),
        "expires_in": token_response.get("expires_in", 0),
        "redirect_uri": token_response.get("redirect_uri", ""),
        "timestamp": token_response.get("timestamp", ""),
        "refresh_token_created": refresh_token_created if refresh_token_created else ""
    }
    
    # Update or add token
    if token_entry is not None:
        database["tokens"][token_entry] = token_data
    else:
        if "tokens" not in database:
            database["tokens"] = []
        database["tokens"].append(token_data)
    
    # Save to file
    try:
        with open(TOKEN_RESPONSE_FILE, 'w', encoding='utf-8') as f:
            json.dump(database, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving tokens database: {e}")
        return False


def create_basic_auth_header(client_id: str, client_secret: str) -> str:
    """Create Basic Authentication header from base64 encoded client_id:client_secret"""
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return f"Basic {encoded}"


def test_get_token_from_refresh_token(refresh_token: str = None, client_id: str = None, user_id: str = None):
    """
    Exchange refresh token for new access token
    
    Args:
        refresh_token: Refresh token from previous token exchange. If None, will try to load from file.
        client_id: Client ID to use. If None, will select TPP from database.
        user_id: User ID (party_id as string). If provided (from GUI), will use this instead of interactive selection.
    """
    # If client_id and user_id are provided (from GUI context), use them directly
    user = None
    gui_mode = False
    if client_id and user_id:
        gui_mode = True
        try:
            user = int(user_id)
        except:
            pass
        
        # Get client name from database
        database = load_database()
        client_name = "Unknown"
        for registration in database.get("registrations", []):
            response_body = registration.get("response", {}).get("body", {})
            if isinstance(response_body, dict):
                reg_client_id = response_body.get("client_id")
                if reg_client_id == client_id:
                    request_body = registration.get("request", {}).get("body", {})
                    client_name = request_body.get("client_name", "")
                    if not client_name:
                        client_name = response_body.get("client_name", "Unknown")
                    break
        
        # Get token from database for this context
        token_data = get_token_from_database(client_id, user)
        if not token_data:
            print(f"❌ Could not find token for client_id: {client_id}, user: {user}")
            print("   Make sure you have completed authorization and token exchange")
            return
        
        refresh_token = token_data.get("refresh_token")
        redirect_uri = token_data.get("redirect_uri", "")
        scope = token_data.get("scope", "")
        
        if not refresh_token:
            print(f"❌ No refresh token found for client_id: {client_id}, user: {user}")
            return
        
        print(f"✅ Using context: Client={client_name}, User={user_id}")
        # GUI mode: token_data, refresh_token, redirect_uri, and scope are already set above
        # Skip all interactive prompts and proceed directly to token refresh
    elif not client_id:
        # Console mode: Select TPP client from database if client_id not provided
        gui_mode = False
        selected_client = select_client()
        if not selected_client:
            return
        client_id = selected_client['client_id']
        client_name = selected_client['client_name']
    else:
        gui_mode = False
        # client_id provided but no user_id (partial console mode)
        client_name = "Unknown"
        # Try to get client name from database
        database = load_database()
        for registration in database.get("registrations", []):
            response_body = registration.get("response", {}).get("body", {})
            if isinstance(response_body, dict):
                reg_client_id = response_body.get("client_id")
                if reg_client_id == client_id:
                    request_body = registration.get("request", {}).get("body", {})
                    client_name = request_body.get("client_name", "")
                    if not client_name:
                        client_name = response_body.get("client_name", "Unknown")
                    break
    
    # Get client credentials from database
    client_creds = get_client_credentials(client_id)
    if not client_creds:
        print(f"❌ Could not find client credentials for client_id: {client_id}")
        print("   Make sure the client is registered in the database")
        return
    
    if not client_creds.get("client_secret"):
        print(f"❌ Client secret not found for client_id: {client_id}")
        return
    
    # Get token data - GUI mode already has it, console mode needs selection
    # Note: If GUI mode (client_id and user_id provided), token_data, refresh_token, redirect_uri, and scope
    # are already set above (lines 247-284), so we skip all interactive prompts
    if gui_mode:
        # GUI mode: Everything is already set, skip interactive selection
        print(f"✅ Token data loaded from context, proceeding to refresh...")
    else:
        # Console mode: Get available tokens and let user select
        # Console mode: Get available tokens and let user select
        available_tokens = list_available_tokens_for_client(client_id)
        token_data = None
        refresh_token = None
        redirect_uri = None
        scope = None
        user = None
        
        if available_tokens:
            print("\n" + "="*60)
            print("AVAILABLE TOKENS FOR SELECTED TPP")
            print("="*60)
            print()
            
            for idx, token in enumerate(available_tokens, 1):
                token_user = token.get("user", "Unknown")
                token_timestamp = token.get("timestamp", "Unknown")
                print(f"  [{idx}] User (Party ID): {token_user}")
                print(f"      Access Token: {token.get('access_token', '')[:50]}...")
                print(f"      Refresh Token: {token.get('refresh_token', '')[:50]}...")
                print(f"      Scope: {token.get('scope', '')}")
                print(f"      Timestamp: {token_timestamp}")
                print()
            
            # Let user select which token to refresh
            while True:
                try:
                    selection = input(f"Select token to refresh (1-{len(available_tokens)}) or 'n' for new user, or 'q' to quit: ").strip()
                    
                    if selection.lower() == 'q':
                        print("❌ Cancelled by user")
                        return None
                    
                    if selection.lower() == 'n':
                        # New user - will prompt for refresh token
                        break
                    
                    selection_num = int(selection)
                    if 1 <= selection_num <= len(available_tokens):
                        token_data = available_tokens[selection_num - 1]
                        user = token_data.get("user")
                        refresh_token = token_data.get("refresh_token")
                        redirect_uri = token_data.get("redirect_uri", "")
                        scope = token_data.get("scope", "")
                        print(f"✅ Selected token for User (Party ID): {user}")
                        break
                    else:
                        print(f"⚠️  Please enter a number between 1 and {len(available_tokens)}")
                except ValueError:
                    print("⚠️  Please enter a valid number, 'n' for new user, or 'q' to quit")
                except KeyboardInterrupt:
                    print("\n❌ Cancelled by user")
                    return None
        
        # If no token selected, prompt for refresh token and user
        if not refresh_token:
            if not user:
                user_input = input("Enter User (Party ID) or press Enter to skip: ").strip()
                if user_input and user_input.isdigit():
                    user = int(user_input)
            
            # Try to get token from database if user is specified
            if user:
                token_data = get_token_from_database(client_id, user)
                if token_data:
                    refresh_token = token_data.get("refresh_token")
                    redirect_uri = token_data.get("redirect_uri", "")
                    scope = token_data.get("scope", "")
                    print(f"✅ Found token for User (Party ID): {user}")
            
            if not refresh_token:
                print(f"⚠️  Could not load refresh token from {TOKEN_RESPONSE_FILE}")
                refresh_token = input("Enter refresh token: ").strip()
                if not refresh_token:
                    print("❌ Refresh token is required")
                    return
    
    # Get client credentials from database
    client_creds = get_client_credentials(client_id)
    if not client_creds:
        print(f"❌ Could not find client credentials for client_id: {client_id}")
        print("   Make sure the client is registered in the database")
        return
    
    if not client_creds.get("client_secret"):
        print(f"❌ Client secret not found for client_id: {client_id}")
        return
    
    # Get redirect_uri and scope from token data or client credentials
    if not redirect_uri:
        redirect_uri = client_creds.get("redirect_uris", [""])[0] if client_creds.get("redirect_uris") else "https://tpp.example.com/redirect"
    
    if not scope:
        scope = client_creds.get("scope", "")
    
    # If we have token data, prefer values from there
    if token_data:
        if token_data.get("scope"):
            scope = token_data.get("scope")
        if token_data.get("redirect_uri"):
            redirect_uri = token_data.get("redirect_uri")
    
    # Create Basic Auth header
    auth_header = create_basic_auth_header(client_id, client_creds["client_secret"])
    
    # Prepare form data
    form_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "redirect_uri": redirect_uri,
        "scope": scope
    }
    
    print("="*60)
    print("TOKEN REFRESH REQUEST")
    print("="*60)
    token_url = get_oauth_token_url()
    print(f"Token URL: {token_url}")
    print(f"Client Name: {client_name}")
    print(f"Client ID: {client_id}")
    if user:
        print(f"User (Party ID): {user}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Scope: {scope}")
    print(f"Refresh Token: {refresh_token[:50]}...")
    print("="*60)
    print()
    
    with sync_playwright() as p:
        # Create API request context with SSL verification disabled
        api_request_context = p.request.new_context(ignore_https_errors=True)
        
        try:
            # Prepare headers
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-TPP-Authorization": auth_header,
                "X-Client-Cert": X_CLIENT_CERTIFICATE
            }
            
            print("📡 Making POST request to token endpoint...")
            print(f"📋 Form Data:")
            print(f"   grant_type: {form_data['grant_type']}")
            print(f"   refresh_token: {form_data['refresh_token'][:50]}...")
            print(f"   redirect_uri: {form_data['redirect_uri']}")
            print(f"   scope: {form_data['scope']}")
            print(f"\n📤 Headers:")
            print(f"   X-TPP-Authorization: {auth_header[:50]}...")
            print(f"   X-Client-Cert: (certificate)")
            
            # Make POST request
            response = api_request_context.post(
                token_url,
                headers=headers,
                data=urlencode(form_data)
            )
            
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
                    print("\n✅ Token refresh successful!")
                    
                    # Extract token information
                    if "access_token" in response_body:
                        access_token = response_body["access_token"]
                        print(f"\n🎉 Access Token: {access_token[:50]}...")
                    
                    if "refresh_token" in response_body:
                        new_refresh_token = response_body["refresh_token"]
                        print(f"🔄 New Refresh Token: {new_refresh_token[:50]}...")
                    
                    if "token_type" in response_body:
                        token_type = response_body["token_type"]
                        print(f"📝 Token Type: {token_type}")
                    
                    if "expires_in" in response_body:
                        expires_in = response_body["expires_in"]
                        print(f"⏰ Expires In: {expires_in} seconds")
                    
                    if "scope" in response_body:
                        returned_scope = response_body["scope"]
                        print(f"📋 Scope: {returned_scope}")
                    
                    # Save token response to database
                    try:
                        if not user:
                            # If user not specified, try to get from previous token or prompt
                            if token_data and token_data.get("user"):
                                user = token_data.get("user")
                            else:
                                user_input = input("Enter User (Party ID) to save token or press Enter to skip: ").strip()
                                if user_input and user_input.isdigit():
                                    user = int(user_input)
                        
                        token_save_data = {
                            **response_body,
                            "redirect_uri": redirect_uri,
                            "scope": scope,
                            "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
                        }
                        
                        if user and save_token_to_database(client_id, user, token_save_data):
                            print(f"\n💾 Token saved to database: {TOKEN_RESPONSE_FILE}")
                            print(f"   Client ID: {client_id}")
                            print(f"   User (Party ID): {user}")
                        elif not user:
                            print(f"\n⚠️  Token not saved (no user/party_id specified)")
                        else:
                            print(f"\n⚠️  Failed to save token to database")
                    except Exception as e:
                        print(f"⚠️  Could not save token response: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"\n⚠️  Token refresh failed with status {status}")
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
            print(f"\n❌ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            api_request_context.dispose()


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
    parser = argparse.ArgumentParser(description='Exchange Refresh Token for Access Token')
    parser.add_argument('--client-id', type=str, help='Client ID from context (GUI)')
    parser.add_argument('--user-id', type=str, help='User ID (party_id) from context (GUI)')
    args = parser.parse_args()
    
    try:
        # If arguments provided (from GUI), use them - this will skip all interactive prompts
        if args.client_id and args.user_id:
            test_get_token_from_refresh_token(client_id=args.client_id, user_id=args.user_id)
        else:
            # Console mode: Select TPP from database and use saved refresh token
            # Option 1: Select TPP from database and use saved refresh token
            # Option 2: Provide refresh_token and client_id as arguments
            # Option 3: Will prompt for refresh token if not found
            test_get_token_from_refresh_token()
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}"
        print(error_msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

