"""
Token Introspection Helper
Introspects OAuth2 tokens (access tokens and refresh tokens) using the introspection endpoint
"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional, Any
import requests
import urllib3
from urllib.parse import urlencode

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.environment_config import get_oauth_introspect_url, get_oauth_revoke_url

# Store the latest introspection error so UI can display details
LAST_INTROSPECTION_ERROR = ""

# X-Client-Certificate header (same as used in other requests)
X_CLIENT_CERTIFICATE = """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"""


def introspect_token(token: str, client_id: str, client_secret: str, environment: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Introspect an OAuth2 token (access token or refresh token) using the introspection endpoint.
    
    Args:
        token: The token to introspect (access token or refresh token)
        client_id: Client ID for Basic authentication
        client_secret: Client secret for Basic authentication
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Dictionary with introspection response containing:
        - active: bool - Whether the token is active/valid
        - exp: int (optional) - Expiration timestamp
        - iat: int (optional) - Issued at timestamp
        - scope: str (optional) - Token scope
        - client_id: str (optional) - Client ID
        - sub: str (optional) - Subject (user ID)
        - token_type: str (optional) - Token type (e.g., "Bearer")
        Or None if introspection fails
    
    Example:
        result = introspect_token(refresh_token, "client123", "secret456")
        if result and result.get("active"):
            print("Token is valid")
    """
    import base64
    
    global LAST_INTROSPECTION_ERROR
    LAST_INTROSPECTION_ERROR = ""

    if not token:
        LAST_INTROSPECTION_ERROR = "Missing token value."
        print("Error introspecting token: missing token value.")
        return None
    
    # Disable SSL warnings for internal certificates
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Get introspection URL
    introspect_url = get_oauth_introspect_url(environment)
    
    # Create Basic auth header
    credentials = f"{client_id}:{client_secret}"
    auth_header = f"Basic {base64.b64encode(credentials.encode('utf-8')).decode('utf-8')}"
    
    # Prepare headers
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-TPP-Authorization": auth_header,
        "X-Client-Cert": X_CLIENT_CERTIFICATE
    }
    
    # Prepare form data
    form_data = {
        "token": token
    }
    
    try:
        # Make POST request to introspection endpoint
        response = requests.post(
            introspect_url,
            headers=headers,
            data=urlencode(form_data),
            verify=False,  # Disable SSL verification for internal certificates
            timeout=30
        )
        
        if response.status_code != 200:
            response_preview = (response.text or "").strip()
            if len(response_preview) > 500:
                response_preview = f"{response_preview[:500]}... [truncated]"
            LAST_INTROSPECTION_ERROR = (
                f"HTTP {response.status_code} from introspection endpoint. "
                f"Response body: {response_preview or '<empty>'}"
            )
            print(f"Error introspecting token: {LAST_INTROSPECTION_ERROR}")
            return None
        
        # Parse response
        try:
            result = response.json()
        except ValueError:
            response_preview = (response.text or "").strip()
            if len(response_preview) > 500:
                response_preview = f"{response_preview[:500]}... [truncated]"
            LAST_INTROSPECTION_ERROR = (
                "Introspection endpoint returned invalid JSON. "
                f"Response body: {response_preview or '<empty>'}"
            )
            print(f"Error introspecting token: {LAST_INTROSPECTION_ERROR}")
            return None
        return result
        
    except Exception as e:
        LAST_INTROSPECTION_ERROR = str(e)
        print(f"Error introspecting token: {e}")
        return None


def get_last_introspection_error() -> str:
    """Return the latest introspection failure reason."""
    return LAST_INTROSPECTION_ERROR


def is_refresh_token_valid(refresh_token: str, client_id: str, client_secret: str, environment: Optional[str] = None) -> bool:
    """
    Check if a refresh token is valid using token introspection.
    
    Args:
        refresh_token: The refresh token to check
        client_id: Client ID for Basic authentication
        client_secret: Client secret for Basic authentication
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        True if token is active/valid, False otherwise
    """
    if not refresh_token:
        return False
    
    result = introspect_token(refresh_token, client_id, client_secret, environment)
    if not result:
        return False
    
    return result.get("active", False)


def get_token_info_from_introspection(token: str, client_id: str, client_secret: str, environment: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get detailed token information from introspection.
    
    Args:
        token: The token to introspect
        client_id: Client ID for Basic authentication
        client_secret: Client secret for Basic authentication
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Dictionary with token information or None if introspection fails
    """
    return introspect_token(token, client_id, client_secret, environment)


def revoke_token(token: str, client_id: str, client_secret: str, token_type_hint: Optional[str] = None, environment: Optional[str] = None) -> bool:
    """
    Revoke an OAuth2 token (access token or refresh token) using the revocation endpoint.
    
    Args:
        token: The token to revoke (access token or refresh token)
        client_id: Client ID for Basic authentication
        client_secret: Client secret for Basic authentication
        token_type_hint: Optional hint about the token type ("access_token" or "refresh_token")
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        True if revocation was successful (status 200), False otherwise
    
    Example:
        success = revoke_token(refresh_token, "client123", "secret456", "refresh_token")
        if success:
            print("Token revoked successfully")
    """
    import base64
    
    if not token:
        return False
    
    # Disable SSL warnings for internal certificates
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Get revocation URL
    revoke_url = get_oauth_revoke_url(environment)
    
    # Create Basic auth header
    credentials = f"{client_id}:{client_secret}"
    auth_header = f"Basic {base64.b64encode(credentials.encode('utf-8')).decode('utf-8')}"
    
    # Prepare headers
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-TPP-Authorization": auth_header,
        "X-Client-Cert": X_CLIENT_CERTIFICATE
    }
    
    # Prepare form data
    form_data = {
        "token": token
    }
    if token_type_hint:
        form_data["token_type_hint"] = token_type_hint
    
    try:
        # Make POST request to revocation endpoint
        response = requests.post(
            revoke_url,
            headers=headers,
            data=urlencode(form_data),
            verify=False,  # Disable SSL verification for internal certificates
            timeout=30
        )
        
        # RFC 7009: The revocation endpoint responds with HTTP 200 status code on success
        # Even if the token was already revoked or invalid, the endpoint should return 200
        return response.status_code == 200
        
    except Exception as e:
        print(f"Error revoking token: {e}")
        return False


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python token_introspection_helper.py <token> <client_id> <client_secret>")
        sys.exit(1)
    
    token = sys.argv[1]
    client_id = sys.argv[2]
    client_secret = sys.argv[3]
    
    print(f"Introspecting token: {token[:50]}...")
    result = introspect_token(token, client_id, client_secret)
    
    if result:
        print("\nIntrospection Result:")
        print(json.dumps(result, indent=2))
        
        if result.get("active"):
            print("\n✅ Token is ACTIVE")
        else:
            print("\n❌ Token is INACTIVE")
    else:
        print("\n❌ Introspection failed")

