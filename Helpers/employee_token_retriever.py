"""
Standalone module for retrieving Employee Token from Microsoft Entra ID
Extracted from sms_otp_helper.py for reuse in other services
"""

import json
from pathlib import Path
from playwright.sync_api import APIRequestContext
from urllib.parse import urlencode
import requests
import urllib3

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


def get_employee_token(api_request_context: APIRequestContext) -> str:
    """
    Generate Employee Token for OBO API access using Microsoft Entra ID OAuth2
    
    This function authenticates using the Resource Owner Password Credentials (ROPC) flow
    to obtain an access token for accessing the OBO-SMC API.
    
    Args:
        api_request_context: Playwright API request context for making HTTP requests
        
    Returns:
        Access token as string
        
    Raises:
        Exception: If token generation fails (non-200 status or missing access_token)
        
    Example:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context()
            api_context = context.request
            
            token = get_employee_token(api_context)
            print(f"Token: {token[:50]}...")
    """
    print("\n🔑 Generating Employee Token...")
    
    # Get Entra config for current environment (lazy loading)
    entra_config = get_entra_config()
    
    # Microsoft Entra ID OAuth2 token endpoint
    token_url = f"https://login.microsoftonline.com/{entra_config['tenant_id']}/oauth2/v2.0/token"
    
    # Prepare form data for OAuth2 ROPC flow
    form_data = {
        "client_id": entra_config["client_id"],
        "client_secret": entra_config["client_secret"],
        "grant_type": "password",  # Resource Owner Password Credentials flow
        "scope": f"{entra_config['component_client_id']}/api",
        "username": entra_config["employee_username"],
        "password": entra_config["employee_password"]
    }
    
    # URL-encode the form data (required for application/x-www-form-urlencoded)
    form_data_encoded = urlencode(form_data)
    
    # Make POST request to token endpoint
    response = api_request_context.post(
        token_url,
        data=form_data_encoded,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    
    # Check for errors
    if response.status != 200:
        error_body = ""
        try:
            error_body = response.text()
        except:
            pass
        raise Exception(
            f"Failed to generate Employee Token: Status {response.status}, "
            f"Response: {error_body}"
        )
    
    # Parse response JSON
    body = response.json()
    if "access_token" not in body:
        raise Exception(
            f"Token response missing access_token. Response: {body}"
        )
    
    token = body["access_token"]
    print("✅ Employee Token generated")
    
    return token


# Requests-based variant (avoids Playwright subprocesses)
def get_employee_token_requests(*, verify_ssl: bool = False, timeout_seconds: int = 30) -> str:
    """
    Generate an employee token with the requests library.

    Args:
        verify_ssl: Whether to verify SSL certificates. Defaults to False because
            many internal environments use certificates not trusted by local store.
        timeout_seconds: HTTP timeout.

    Returns:
        Access token as string.
    """
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Get Entra config for current environment (lazy loading)
    entra_config = get_entra_config()

    token_url = f"https://login.microsoftonline.com/{entra_config['tenant_id']}/oauth2/v2.0/token"

    form_data = {
        "client_id": entra_config["client_id"],
        "client_secret": entra_config["client_secret"],
        "grant_type": "password",
        "scope": f"{entra_config['component_client_id']}/api",
        "username": entra_config["employee_username"],
        "password": entra_config["employee_password"],
    }

    resp = requests.post(
        token_url,
        data=form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=verify_ssl,
        timeout=timeout_seconds,
    )

    if resp.status_code != 200:
        raise Exception(f"Failed to generate Employee Token: Status {resp.status_code}, Response: {resp.text}")

    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise Exception(f"Token response missing access_token. Response: {body}")

    return token


# Example usage - can be run from console: python Helpers/employee_token_retriever.py
if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        api_context = context.request
        
        try:
            token = get_employee_token(api_context)
            print(f"\n✅ Token retrieved successfully!")
            print(f"Full token: {token}")
            print(f"Token length: {len(token)} characters")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

