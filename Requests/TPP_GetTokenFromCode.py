"""
TPP Get Token From Authorization Code
Based on Bruno/COA Token - code.bru
Exchanges authorization code for access token using TPP credentials from database
"""

from playwright.sync_api import sync_playwright
import json
import os
import sys
import base64
import argparse
from urllib.parse import urlencode
from pathlib import Path

# Get the parent directory (project root)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone

from Helpers.file_lock_helper import safe_read_json
from Helpers.environment_config import get_oauth_token_url, get_database_file, load_token_config

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Database files (environment-aware paths)
DATABASE_FILE = str(get_database_file("tpp_registrations.json"))
AUTH_CODE_FILE = str(get_database_file("last_authorization_code.json"))
TOKEN_RESPONSE_FILE = str(get_database_file("tpp_tokens.json"))

# X-Client-Certificate header (from Bruno file)
X_CLIENT_CERTIFICATE = """MIII9zCCBt+gAwIBAgIJA1Ga8pKetC86MA0GCSqGSIb3DQEBCwUAMH8xKDAmBgNVBAMMH0kuQ0EgVGVzdCBUTFMgRVYgQ0EvUlNBIDA1LzIwMjIxLTArBgNVBAoMJFBydm7DrSBjZXJ0aWZpa2HEjW7DrSBhdXRvcml0YSwgYS5zLjEXMBUGA1UEYQwOTlRSQ1otMjY0MzkzOTUxCzAJBgNVBAYTAkNaMB4XDTI1MTExNDA5NDYyMFoXDTI2MTExNDA5NDYyMFowggEHMQswCQYDVQQGEwJDWjEdMBsGA1UECAwUSGxhdm7DrSBtxJtzdG8gUHJhaGExEDAOBgNVBAcMB1ByYWhhIDgxDjAMBgNVBBEMBTE4NjAwMRowGAYDVQQJDBFTb2tvbG92c2vDoSA2NzUvOTEcMBoGA1UECgwTQmFua2EgQ1JFRElUQVMgYS5zLjEdMBsGA1UEDwwUUHJpdmF0ZSBPcmdhbml6YXRpb24xEzARBgsrBgEEAYI3PAIBAxMCQ1oxETAPBgNVBAUTCDYzNDkyNTU1MRswGQYDVQRhDBJQU0RDWi1DTkItNjM0OTI1NTUxGTAXBgNVBAMMEHRlc3QuY3JlZGl0YXMuY3owggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCvmcGJkuDeOPKaY2RBkokJVH63pGbWlEO8tdb40VzNxGq6ISYtT/q1kvlyp0ToC6svgECxpVmHAsZzwnYKh/r3m86skQc/wHhW+KndbIMeDalaRMwoRcC3dtg9yeeGZrcHRqHaEAqbiCWs/OxpR5S9NoMydPyF0i02vYt/xy8Zq48gXtJUv3JI4af1uxng2T6ZdqgMdkmxOxbjEUVby972zDAHpIi8YW/1PN0KSooSmo6yt4fwh06empS0sS24JQQnSc8XN0vIZT+l5Qd7+ditG60NJiYhEbBnAEoAHielPxTLu6NrMFk11coWH5fLiAsWqrPGNtX6zx17m+FJeEzVAgMBAAGjggPqMIID5jAiBgVngQwDAQQZMBcTA1BTRBMCQ1oMDENOQi02MzQ5MjU1NTAbBgNVHREEFDASghB0ZXN0LmNyZWRpdGFzLmN6MAwGA1UdEwEB/wQCMAAwTwYDVR0gBEgwRjAHBgVngQwBATAwBg0rBgEEAYG4SAoDKAEBMB8wHQYIKwYBBQUHAgEWEWh0dHA6Ly93d3cuaWNhLmN6MAkGBwQAi+xAAQQwXgYDVR0fBFcwVTAooCagJIYiaHR0cDovL3Rlc3RxLmljYS5jei90cWN3MjJfcnNhLmNybDApoCegJYYjaHR0cDovL3Rlc3RxMi5pY2EuY3ovdHFjdzIyX3JzYS5jcmwwagYIKwYBBQUHAQEEXjBcMC4GCCsGAQUFBzAChiJodHRwOi8vdGVzdHEuaWNhLmN6L3RxY3cyMl9yc2EuY2VyMCoGCCsGAQUFBzABhh5odHRwOi8vdG9jc3AuaWNhLmN6L3RxY3cyMl9yc2EwDgYDVR0PAQH/BAQDAgWgMIIBAAYIKwYBBQUHAQMEgfMwgfAwCAYGBACORgEBMBMGBgQAjkYBBjAJBgcEAI5GAQYDMFgGBgQAjkYBBTBOMCUWH2h0dHBzOi8vdGVzdHEuaWNhLmN6L3Bkc19jcy5wZGYTAmNzMCUWH2h0dHBzOi8vdGVzdHEuaWNhLmN6L3Bkc19lbi5wZGYTAmVuMHUGBgQAgZgnAjBrMEwwEQYHBACBmCcBAQwGUFNQX0FTMBEGBwQAgZgnAQIMBlBTUF9QSTARBgcEAIGYJwEDDAZQU1BfQUkwEQYHBACBmCcBBAwGUFNQX0lDDBNDemVjaCBOYXRpb25hbCBCYW5rDAZDWi1DTkIwHwYDVR0jBBgwFoAU4+6eqSwGvI60H83GOkuAjTkHVykwHQYDVR0OBBYEFJdgEg8BgTbUHNNifda27oR9DS5MMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjCCAQMGCisGAQQB1nkCBAIEgfQEgfEA7wB1AGLpAGAEoweVWnVEtNWEqWJoyh1uRYWt8JFt/l/cHwTbAAABmoHCQ9QAAAQDAEYwRAIgM0AOCr9FHD+uvW40jWO7P2OWx7sYf0I3Dd0vBovMkXYCICKdstfhOSBqzh8fxe6LRk7Xa4jXQ5IvieoOYzp4uMRmAHYAsMyD5aX5fWuvfAnMKEkEhyrH6IsTLGNQt8b9JuFsbHcAAAGagcJGuwAABAMARzBFAiAnxglGtfBvA877YhOWN5NYtK3ehXyxXgQk69OpWtnS9gIhALU2QP3znCe20XORzXlsie+FAwzaPpk1j6nra9UTVhxQMA0GCSqGSIb3DQEBCwUAA4ICAQAiQo8e/42bqImKhNos/UHPBVMpxXhBwYDu8T2/qxxokEFXjEloB2IG6pI94eK14bkuHDbruJFSLQkup2Sj+72ok/Mez8jv2rkc3DRTQqYToUXQcZXJ0LI0TahMlw8CDyUkxVdZQkCBGxhcPs5bt7eeq5Lh0fX8dK0Cwak9mVoejrfCH83pzty2Pblk6Im7iDsc87edk1l3jRzevLOq4UsX4mpdCo0mJdEBABOTRLv+g2H9FjTmdyLxZJ7JrlGEMvY99HtCAy31IWzBThhPiD2rSIHtBRCW1OwRUNE5C2J2QoqkSg84KIfSRpBYRaV2pmdLkxaMl040mWGAQKVk3G8sMWIZWJxH7tj5uJluo338kiH6xgfL7SJpK7YwjjhO+tCl1iiBKaBtPQtfWQByv8GVCvhVjgTzS4Y8MTLJSbQpKxOEbzJUv0t4rOoY0HoAszr0WNvzMPtvuxG+55Fgo89a6uCFix1bjwKHkb2pwVnfWuThUkTBUlVrzUByYEElmTZ6uPgrxjeBKkzbhUu8N26YBff1KK2nVPBqvfiqlrU0JcOkM1+AXy8VLtvQeeDo0q7ytELt7/yC6JbDc07G7i2/49xh6bLj2SAlPYP+mREyRfrOpXwVMgO1PJ9hvrz3YCp8Kg3zrWgLX7TOcK86cEPyFnodMLoTMEs3ASBExGWeAg=="""


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


def load_authorization_code(state: str = None):
    """
    Load authorization code from saved file collection (thread-safe with file locking)
    
    Args:
        state: Optional state parameter to find specific authorization code.
               If None, returns the most recent one (by timestamp).
    
    Returns:
        Authorization code entry dict or None if not found
    """
    data = safe_read_json(AUTH_CODE_FILE)
    if not data:
        return None
    
    # Handle both old format (single object) and new format (collection)
    if "authorization_codes" in data:
        # New format: collection
        codes = data.get("authorization_codes", [])
        if not codes:
            return None
        
        if state:
            # Find by state
            for entry in codes:
                if entry.get("state") == state:
                    return entry
            print(f"⚠️  No authorization code found for state: {state}")
            return None
        else:
            # Return most recent (by timestamp)
            sorted_codes = sorted(
                codes,
                key=lambda x: x.get("timestamp", ""),
                reverse=True
            )
            return sorted_codes[0] if sorted_codes else None
    else:
        # Old format: single object (backward compatibility)
        if state and data.get("state") != state:
            print(f"⚠️  State mismatch. Expected: {state}, Found: {data.get('state')}")
            return None
        return data


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


def save_token_to_database(client_id: str, user: int, token_response: dict):
    """Save or update token in database, organized by client_id and user"""
    database = load_tokens_database()
    
    # Find existing token entry
    token_entry = None
    for idx, token in enumerate(database.get("tokens", [])):
        if token.get("client_id") == client_id and token.get("user") == user:
            token_entry = idx
            break
    
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
        "refresh_token_created": token_response.get("refresh_token_created", "")
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


def get_token_from_database(client_id: str, user: int = None):
    """Get token from database for given client_id and optionally user"""
    database = load_tokens_database()
    
    for token in database.get("tokens", []):
        if token.get("client_id") == client_id:
            if user is None or token.get("user") == user:
                return token
    
    return None


def create_basic_auth_header(client_id: str, client_secret: str) -> str:
    """Create Basic Authentication header from base64 encoded client_id:client_secret"""
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return f"Basic {encoded}"


def test_get_token_from_code(authorization_code: str = None, client_id: str = None, user_id: str = None, state: str = None):
    """
    Exchange authorization code for access token
    
    Args:
        authorization_code: Authorization code from OAuth2 flow. If None, will try to load from file.
        client_id: Client ID to use. If None, will try to load from saved authorization code file.
        user_id: User ID (party_id as string). If provided, will use this instead of loading from auth code file.
        state: State parameter to match specific authorization flow. If None, uses the most recent one.
    """
    # Try to load authorization code from file if not provided
    user = None  # party_id
    if not authorization_code:
        auth_data = load_authorization_code(state=state)
        if auth_data:
            # Check authorization code expiration
            timestamp_str = auth_data.get('timestamp', '')
            if timestamp_str:
                try:
                    # Parse timestamp
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str.replace('Z', '+00:00')
                    code_created_dt = datetime.fromisoformat(timestamp_str)
                    if code_created_dt.tzinfo is None:
                        code_created_dt = code_created_dt.replace(tzinfo=timezone.utc)
                    
                    # Get expiration from config
                    token_config = load_token_config()
                    expiration_seconds = token_config["authorization_code_expiration_seconds"]
                    
                    # Calculate age
                    now = datetime.now(timezone.utc)
                    age_seconds = (now - code_created_dt).total_seconds()
                    
                    if age_seconds >= expiration_seconds:
                        expired_minutes = int((age_seconds - expiration_seconds) / 60)
                        print(f"❌ Authorization code expired {expired_minutes} minutes ago")
                        print(f"   Code was created at: {timestamp_str}")
                        print(f"   Expiration time: {expiration_seconds} seconds ({expiration_seconds // 60} minutes)")
                        return
                    else:
                        remaining_seconds = expiration_seconds - age_seconds
                        remaining_minutes = int(remaining_seconds / 60)
                        print(f"⏰ Authorization code expires in {remaining_minutes} minutes")
                except Exception as e:
                    print(f"⚠️  Could not check authorization code expiration: {e}")
            
            authorization_code = auth_data.get("authorization_code")
            if not client_id:
                client_id = auth_data.get("client_id")
            # Use user_id from parameter if provided (GUI context), otherwise from auth code file
            if user_id:
                try:
                    user = int(user_id)
                except:
                    user = auth_data.get("user")
            else:
                user = auth_data.get("user")  # party_id
            redirect_uri = auth_data.get("redirect_uri")
            scope = auth_data.get("scope")
            found_state = auth_data.get("state")
            print(f"✅ Loaded authorization code from: {AUTH_CODE_FILE}")
            if found_state:
                print(f"   State: {found_state}")
            print(f"   Client ID: {client_id}")
            if user:
                print(f"   User (Party ID): {user}")
            print(f"   Redirect URI: {redirect_uri}")
            print(f"   Scope: {scope}")
        else:
            print(f"⚠️  Could not load authorization code from {AUTH_CODE_FILE}")
            if not authorization_code:
                authorization_code = input("Enter authorization code: ").strip()
                if not authorization_code:
                    print("❌ Authorization code is required")
                    return
            if not user:
                if user_id:
                    try:
                        user = int(user_id)
                    except:
                        pass
                if not user:
                    user_input = input("Enter User (Party ID) or press Enter to skip: ").strip()
                    if user_input and user_input.isdigit():
                        user = int(user_input)
    
    # Get client credentials from database
    if not client_id:
        print("❌ Client ID is required")
        return
    
    client_creds = get_client_credentials(client_id)
    if not client_creds:
        print(f"❌ Could not find client credentials for client_id: {client_id}")
        print("   Make sure the client is registered in the database")
        return
    
    if not client_creds.get("client_secret"):
        print(f"❌ Client secret not found for client_id: {client_id}")
        return
    
    # Use redirect_uri and scope from saved auth data or from client credentials
    if 'redirect_uri' not in locals():
        redirect_uri = client_creds.get("redirect_uris", [""])[0] if client_creds.get("redirect_uris") else "https://tpp.example.com/redirect"
    
    if 'scope' not in locals():
        scope = client_creds.get("scope", "")
    
    # Create Basic Auth header with base64 encoded client_id:client_secret
    auth_header = create_basic_auth_header(client_id, client_creds["client_secret"])
    
    # Prepare form data
    form_data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": redirect_uri,
        "scope": scope
    }
    
    print("="*60)
    print("TOKEN EXCHANGE REQUEST")
    print("="*60)
    token_url = get_oauth_token_url()
    print(f"Token URL: {token_url}")
    print(f"Client ID: {client_id}")
    print(f"Redirect URI: {redirect_uri}")
    print(f"Scope: {scope}")
    print(f"Authorization Code: {authorization_code[:50]}...")
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
            print(f"   code: {form_data['code'][:50]}...")
            print(f"   redirect_uri: {form_data['redirect_uri']}")
            print(f"   scope: {form_data['scope']}")
            print(f"\n📤 Headers:")
            print(f"   X-TPP-Authorization: {auth_header[:50]}...")
            print(f"   X-Client-Cert: (certificate)")
            
            # Make POST request
            token_url = get_oauth_token_url()
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
                    print("\n✅ Token exchange successful!")
                    
                    # Extract token information
                    if "access_token" in response_body:
                        access_token = response_body["access_token"]
                        print(f"\n🎉 Access Token: {access_token[:50]}...")
                    
                    if "refresh_token" in response_body:
                        refresh_token = response_body["refresh_token"]
                        print(f"🔄 Refresh Token: {refresh_token[:50]}...")
                    
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
                            # Try to extract user from token if available
                            # For now, use None if not provided
                            pass
                        
                        # Format timestamp as ISO 8601 with Z suffix
                        current_timestamp = datetime.now(timezone.utc).isoformat()
                        # Replace +00:00 with Z, but handle case where it might already have Z
                        if current_timestamp.endswith('+00:00'):
                            current_timestamp = current_timestamp.replace('+00:00', 'Z')
                        elif not current_timestamp.endswith('Z'):
                            current_timestamp = current_timestamp + 'Z'
                        
                        # Create token data with refresh_token_created set to current time
                        token_data = {
                            **response_body,
                            "redirect_uri": redirect_uri,
                            "scope": scope,
                            "timestamp": current_timestamp,
                            "refresh_token_created": current_timestamp  # Current time when refresh token is created
                        }
                        
                        if save_token_to_database(client_id, user, token_data):
                            print(f"\n💾 Token saved to database: {TOKEN_RESPONSE_FILE}")
                            print(f"   Client ID: {client_id}")
                            if user:
                                print(f"   User (Party ID): {user}")
                        else:
                            print(f"\n⚠️  Failed to save token to database")
                    except Exception as e:
                        print(f"⚠️  Could not save token response: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"\n⚠️  Token exchange failed with status {status}")
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Exchange Authorization Code for Access Token')
    parser.add_argument('--client-id', type=str, help='Client ID from context (GUI)')
    parser.add_argument('--user-id', type=str, help='User ID (party_id) from context (GUI)')
    parser.add_argument('--state', type=str, help='State of the authorization code to exchange')
    args = parser.parse_args()
    
    # If arguments provided (from GUI), use them
    if args.client_id and args.user_id:
        test_get_token_from_code(client_id=args.client_id, user_id=args.user_id, state=args.state)
    else:
        # Console mode: use saved authorization code or prompt
        # Option 1: Use saved authorization code from TPP_User_Authorization.py
        # Option 2: Provide authorization_code and client_id as arguments
        # Option 3: Will prompt for authorization code if not found
        test_get_token_from_code()

