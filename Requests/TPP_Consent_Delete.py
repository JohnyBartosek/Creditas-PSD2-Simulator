"""
TPP Consent DELETE API Test
Based on Bruno/DeleteConsentsByUser.bru
Deletes consents for a user
"""

import sys
import io

# Fix Windows console encoding for Unicode characters (emojis)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import json
import os
import uuid
import argparse
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode
from pathlib import Path

# Get the parent directory (project root)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

# Import employee token retriever
from Helpers.employee_token_retriever import get_employee_token
from Helpers.environment_config import get_consents_url, get_database_file

# Database files (environment-aware paths)
DATABASE_FILE = str(get_database_file("tpp_registrations.json"))
TOKEN_RESPONSE_FILE = str(get_database_file("tpp_tokens.json"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


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


def generate_request_id():
    """Generate a GUID for X-Request-ID"""
    return str(uuid.uuid4())


def test_delete_consents(client_id: str = None, user_id: str = None, 
                         user_id_param: str = None, oauth2_client_id: str = None):
    """
    Delete consents for a user
    
    Args:
        client_id: Client ID to use. If None, will prompt.
        user_id: User ID (party_id as string) for token lookup. If None, will prompt.
        user_id_param: User ID parameter for the API call (defaults to user_id if not provided)
        oauth2_client_id: OAuth2 Client ID parameter (defaults to client_id if not provided)
    """
    try:
        # GUI mode: If client_id and user_id are provided, use them directly
        if client_id and user_id:
            try:
                user = int(user_id)
            except:
                print(f"⚠️  Invalid user_id provided: {user_id}. Must be an integer.")
                return
            
            if not user_id_param:
                user_id_param = user_id
            
            if not oauth2_client_id:
                oauth2_client_id = client_id
            
            print(f"✅ Using context: Client={client_id}, User={user_id}")
        else:
            # Console mode: Prompt for input
            print("="*60)
            print("DELETE CONSENTS - CONSOLE MODE")
            print("="*60)
            
            if not client_id:
                client_id = input("Enter Client ID: ").strip()
                if not client_id:
                    print("❌ Client ID is required")
                    return
            
            if not user_id:
                user_id = input("Enter User ID (Party ID) for token lookup: ").strip()
                if not user_id:
                    print("❌ User ID is required")
                    return
                try:
                    user = int(user_id)
                except:
                    print(f"⚠️  Invalid user_id: {user_id}. Must be an integer.")
                    return
            
            if not user_id_param:
                user_id_param_input = input(f"Enter User ID parameter for API (default: {user_id}): ").strip()
                user_id_param = user_id_param_input if user_id_param_input else user_id
            
            if not oauth2_client_id:
                oauth2_client_id_input = input(f"Enter OAuth2 Client ID parameter (default: {client_id}): ").strip()
                oauth2_client_id = oauth2_client_id_input if oauth2_client_id_input else client_id
        
        # Get Entra employee token for Authorization header
        print("🔑 Retrieving Entra token for Authorization header...")
        
        # Build query parameters
        params = {}
        if user_id_param:
            params["userID"] = user_id_param
        if oauth2_client_id:
            params["oauth2clientID"] = oauth2_client_id
        
        query_string = urlencode(params)
        consents_url = get_consents_url()
        url = f"{consents_url}?{query_string}"
        
        request_id = generate_request_id()
        
        logger.info(f"DELETE CONSENTS REQUEST - URL: {url}, X-Request-ID: {request_id}")
        print("="*60)
        print("DELETE CONSENTS REQUEST")
        print("="*60)
        print(f"URL: {url}")
        print(f"Method: DELETE")
        print(f"X-Request-ID: {request_id}")
        print()
        
        # Make request using Playwright
        with sync_playwright() as p:
            # Create API request context with SSL verification disabled
            api_request_context = p.request.new_context(ignore_https_errors=True)
            
            try:
                # Get Entra employee token for Authorization header
                entra_token = get_employee_token(api_request_context)
                
                # Prepare headers with Entra token
                headers = {
                    "Authorization": f"Bearer {entra_token}",
                    "X-Request-ID": request_id,
                    "Content-Type": "application/json"
                }
                
                response = api_request_context.delete(url, headers=headers)
                
                status = response.status
                response_body = None
                content_type = response.headers.get("content-type", "")
                
                if content_type.startswith("application/json"):
                    try:
                        response_body = response.json()
                    except:
                        response_body = response.text()
                else:
                    response_body = response.text()
                
                logger.info(f"DELETE CONSENTS RESPONSE - Status: {status}")
                print("="*60)
                print("RESPONSE")
                print("="*60)
                print(f"Status: {status}")
                print()
                
                if status in [200, 204]:
                    logger.info("DELETE CONSENTS - Success")
                    print("✅ Success! Consents deleted.")
                    if response_body:
                        if isinstance(response_body, dict):
                            print(json.dumps(response_body, indent=2, ensure_ascii=False))
                        else:
                            print(response_body)
                else:
                    logger.error(f"DELETE CONSENTS - Error: {status}, Response: {response_body}")
                    print(f"❌ Error: {status}")
                    if response_body:
                        if isinstance(response_body, dict):
                            print(json.dumps(response_body, indent=2, ensure_ascii=False))
                        else:
                            print(response_body)
                
            except Exception as e:
                logger.exception(f"DELETE CONSENTS - Error making request: {e}")
                print(f"❌ Error making request: {e}")
                import traceback
                traceback.print_exc()
    
    except Exception as e:
        logger.exception(f"DELETE CONSENTS - Error: {e}")
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete consents for a user")
    parser.add_argument("--client-id", help="Client ID")
    parser.add_argument("--user-id", help="User ID (Party ID) for token lookup")
    parser.add_argument("--user-id-param", help="User ID parameter for API call")
    parser.add_argument("--oauth2-client-id", help="OAuth2 Client ID parameter")
    
    args = parser.parse_args()
    
    test_delete_consents(
        client_id=args.client_id,
        user_id=args.user_id,
        user_id_param=args.user_id_param,
        oauth2_client_id=args.oauth2_client_id
    )

