"""
TPP Consent GET API Test
Based on Bruno/GetConsents.bru
Fetches consents for a user using access token from database
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
DEFAULT_AUTH_CONFIG_FILE = str(get_database_file("default_auth_config.json"))
USERS_FILE = str(get_database_file("users.json"))
CONSENTS_FILE = str(get_database_file("tpp_consents.json"))

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


def load_consents_database():
    """Load consents database from JSON file"""
    if os.path.exists(CONSENTS_FILE):
        try:
            with open(CONSENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading consents database: {e}")
            return {"consents": []}
    return {"consents": []}


def save_consent_to_database(consent_data):
    """Save consent response to database"""
    database = load_consents_database()
    
    consent_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "response": consent_data
    }
    
    database["consents"].append(consent_entry)
    
    try:
        os.makedirs(os.path.dirname(CONSENTS_FILE), exist_ok=True)
        with open(CONSENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(database, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving consents database: {e}")
        return False


def generate_request_id():
    """Generate a GUID for X-Request-ID"""
    return str(uuid.uuid4())


def test_get_consents(client_id: str = None, user_id: str = None, owner_id: str = None, 
                     disponent_id: str = None, valid_consents_only: bool = None):
    """
    Fetch consents for a user
    
    Args:
        client_id: Client ID to use. If None, will prompt.
        user_id: User ID (party_id as string). If None, will prompt.
        owner_id: Owner ID (defaults to user_id if not provided)
        disponent_id: Disponent ID (optional)
        valid_consents_only: Whether to return only valid consents (default: False)
    """
    try:
        # GUI mode: If user_id is provided, use it directly (client_id is optional)
        if user_id:
            try:
                user = int(user_id)
            except:
                print(f"⚠️  Invalid user_id provided: {user_id}. Must be an integer.")
                return
            
            if not owner_id:
                owner_id = user_id
            
            # If valid_consents_only not explicitly set, use configuration
            if valid_consents_only is None:
                from Helpers.environment_config import get_show_invalid_consents
                show_invalid = get_show_invalid_consents()
                # valid_consents_only should be inverse of show_invalid_consents
                valid_consents_only = not show_invalid
            
            if client_id:
                print(f"✅ Using context: Client={client_id}, User={user_id}")
            else:
                print(f"✅ Using context: User={user_id} (no Client selected)")
            print(f"📋 Valid consents only: {valid_consents_only}")
        else:
            # Console mode: Prompt for input
            print("="*60)
            print("GET CONSENTS - CONSOLE MODE")
            print("="*60)
            
            if not client_id:
                client_id = input("Enter Client ID: ").strip()
                if not client_id:
                    print("❌ Client ID is required")
                    return
            
            if not user_id:
                user_id = input("Enter User ID (Party ID): ").strip()
                if not user_id:
                    print("❌ User ID is required")
                    return
                try:
                    user = int(user_id)
                except:
                    print(f"⚠️  Invalid user_id: {user_id}. Must be an integer.")
                    return
            
            if not owner_id:
                owner_id_input = input(f"Enter Owner ID (default: {user_id}): ").strip()
                owner_id = owner_id_input if owner_id_input else user_id
            
            disponent_id_input = input("Enter Disponent ID (optional, press Enter to skip): ").strip()
            if disponent_id_input:
                disponent_id = disponent_id_input
            
            if valid_consents_only is None:
                valid_input = input("Return only valid consents? (y/N): ").strip().lower()
                valid_consents_only = valid_input == 'y'
            else:
                # Use provided value
                pass
        
        # Get Entra employee token for Authorization header
        print("🔑 Retrieving Entra token for Authorization header...")
        
        # Build query parameters
        params = {
            "owner-id": owner_id,
            "valid-consents-only": str(valid_consents_only).lower()
        }
        if disponent_id:
            params["disponent-id"] = disponent_id
        
        query_string = urlencode(params)
        consents_url = get_consents_url()
        url = f"{consents_url}?{query_string}"
        
        request_id = generate_request_id()
        
        logger.info(f"GET CONSENTS REQUEST - URL: {url}, X-Request-ID: {request_id}")
        print("="*60)
        print("GET CONSENTS REQUEST")
        print("="*60)
        print(f"URL: {url}")
        print(f"Method: GET")
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
                
                response = api_request_context.get(url, headers=headers)
                
                status = response.status
                response_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text()
                
                logger.info(f"GET CONSENTS RESPONSE - Status: {status}")
                print("="*60)
                print("RESPONSE")
                print("="*60)
                print(f"Status: {status}")
                print()
                
                if status == 200:
                    logger.info("GET CONSENTS - Success")
                    print(f"✅ Success! Status: {status}")
                    
                    # Output JSON marker for parsing by GUI (only output needed)
                    print("\n[CONSENTS_JSON_START]")
                    print(json.dumps(response_body, ensure_ascii=False))
                    print("[CONSENTS_JSON_END]")
                else:
                    logger.error(f"GET CONSENTS - Error: {status}, Response: {response_body}")
                    print(f"❌ Error: {status}")
                    if isinstance(response_body, dict):
                        print(json.dumps(response_body, indent=2, ensure_ascii=False))
                    else:
                        print(response_body)
                
            except Exception as e:
                logger.exception(f"GET CONSENTS - Error making request: {e}")
                print(f"❌ Error making request: {e}")
                import traceback
                traceback.print_exc()
    
    except Exception as e:
        logger.exception(f"GET CONSENTS - Error: {e}")
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get consents for a user")
    parser.add_argument("--client-id", help="Client ID")
    parser.add_argument("--user-id", help="User ID (Party ID)")
    parser.add_argument("--owner-id", help="Owner ID (defaults to user-id)")
    parser.add_argument("--disponent-id", help="Disponent ID")
    parser.add_argument("--valid-consents-only", action="store_true", help="Return only valid consents")
    
    args = parser.parse_args()
    
    test_get_consents(
        client_id=args.client_id,
        user_id=args.user_id,
        owner_id=args.owner_id,
        disponent_id=args.disponent_id,
        valid_consents_only=args.valid_consents_only
    )

