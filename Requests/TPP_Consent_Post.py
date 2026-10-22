"""
TPP Consent POST API Test
Based on Bruno/PostConsent.bru
Creates a new consent for a user
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


def load_registrations():
    """Load registrations from JSON file"""
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading registrations: {e}")
            return {"registrations": []}
    return {"registrations": []}


def get_client_id_from_registration(client_name: str):
    """Get client_id from registration by client_name"""
    database = load_registrations()
    
    for registration in database.get("registrations", []):
        response_body = registration.get("response", {}).get("body", {})
        if isinstance(response_body, dict):
            reg_client_name = response_body.get("client_name", "")
            if reg_client_name == client_name:
                return response_body.get("client_id")
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


def save_consent_to_database(consent_data, request_body):
    """Save consent response to database"""
    database = load_consents_database()
    
    consent_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "request": {
            "url": get_consents_url(),
            "method": "POST",
            "headers": consent_data.get("request_headers", {}),
            "body": request_body
        },
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


def test_post_consent(client_id: str = None, user_id: str = None, owner_id: str = None,
                     oauth2_client_id: str = None, oauth2_client_name: str = None,
                     disponent_ids: list = None, scopes: list = None):
    """
    Create a new consent
    
    Args:
        client_id: Client ID to use. If None, will prompt.
        user_id: User ID (party_id as string). If None, will prompt.
        owner_id: Owner ID (defaults to user_id if not provided)
        oauth2_client_id: OAuth2 Client ID (optional, will try to use client_id if not provided)
        oauth2_client_name: OAuth2 Client Name (optional)
        disponent_ids: List of disponent IDs (defaults to [owner_id] if not provided)
        scopes: List of scopes (default: ["AISP.Balance", "AISP.AccountList", "AISP.TransactionList", "PISP.PaymentInitiation"])
    """
    try:
        # GUI mode: If client_id and user_id are provided, use them directly
        if client_id and user_id:
            try:
                user = int(user_id)
            except:
                print(f"⚠️  Invalid user_id provided: {user_id}. Must be an integer.")
                return
            
            if not owner_id:
                owner_id = user_id
            
            if not oauth2_client_id:
                oauth2_client_id = client_id
            
            if not disponent_ids:
                disponent_ids = [int(owner_id)]
            
            if not scopes:
                scopes = ["AISP.Balance", "AISP.AccountList", "AISP.TransactionList", "PISP.PaymentInitiation"]
            
            print(f"✅ Using context: Client={client_id}, User={user_id}")
        else:
            # Console mode: Prompt for input
            print("="*60)
            print("POST CONSENT - CONSOLE MODE")
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
            
            if not oauth2_client_id:
                oauth2_client_id_input = input(f"Enter OAuth2 Client ID (default: {client_id}): ").strip()
                oauth2_client_id = oauth2_client_id_input if oauth2_client_id_input else client_id
            
            if not oauth2_client_name:
                oauth2_client_name = input("Enter OAuth2 Client Name (optional): ").strip()
            
            if not disponent_ids:
                disponent_input = input(f"Enter Disponent IDs (comma-separated, default: {owner_id}): ").strip()
                if disponent_input:
                    disponent_ids = [int(d.strip()) for d in disponent_input.split(',')]
                else:
                    disponent_ids = [int(owner_id)]
            
            if not scopes:
                print("\nAvailable scopes:")
                print("  1. AISP.Balance")
                print("  2. AISP.AccountList")
                print("  3. AISP.TransactionList")
                print("  4. PISP.PaymentInitiation")
                print("  5. All of the above")
                scope_choice = input("Select scopes (1-5, default: 5): ").strip() or "5"
                
                if scope_choice == "5":
                    scopes = ["AISP.Balance", "AISP.AccountList", "AISP.TransactionList", "PISP.PaymentInitiation"]
                elif scope_choice == "1":
                    scopes = ["AISP.Balance"]
                elif scope_choice == "2":
                    scopes = ["AISP.AccountList"]
                elif scope_choice == "3":
                    scopes = ["AISP.TransactionList"]
                elif scope_choice == "4":
                    scopes = ["PISP.PaymentInitiation"]
                else:
                    scopes = ["AISP.Balance", "AISP.AccountList", "AISP.TransactionList", "PISP.PaymentInitiation"]
        
        # Get Entra employee token for Authorization header
        print("🔑 Retrieving Entra token for Authorization header...")
        
        # Build request body
        request_body = {
            "ownerId": int(owner_id),
            "oauth2ClientId": oauth2_client_id,
            "disponentIds": disponent_ids,
            "scopes": scopes
        }
        
        if oauth2_client_name:
            request_body["oauth2ClientName"] = oauth2_client_name
        
        request_id = generate_request_id()
        
        consents_url = get_consents_url()
        logger.info(f"POST CONSENT REQUEST - URL: {consents_url}, X-Request-ID: {request_id}, Body: {request_body}")
        print("="*60)
        print("POST CONSENT REQUEST")
        print("="*60)
        print(f"URL: {consents_url}")
        print(f"Method: POST")
        print(f"X-Request-ID: {request_id}")
        print()
        print("Request Body:")
        print(json.dumps(request_body, indent=2, ensure_ascii=False))
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
                
                response = api_request_context.post(consents_url, headers=headers, data=json.dumps(request_body))
                
                status = response.status
                response_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text()
                
                logger.info(f"POST CONSENT RESPONSE - Status: {status}")
                print("="*60)
                print("RESPONSE")
                print("="*60)
                print(f"Status: {status}")
                print()
                
                if status in [200, 201]:
                    logger.info("POST CONSENT - Success")
                    print("✅ Success!")
                    print()
                    print("📄 Response Body:")
                    if isinstance(response_body, dict):
                        print(json.dumps(response_body, indent=2, ensure_ascii=False))
                        # Save to database
                        save_consent_to_database({
                            "status": status,
                            "headers": dict(response.headers),
                            "body": response_body,
                            "request_headers": headers
                        }, request_body)
                        logger.info("POST CONSENT - Data saved to database")
                        print()
                        print("✅ Consent saved to database")
                    else:
                        print(response_body)
                else:
                    logger.error(f"POST CONSENT - Error: {status}, Response: {response_body}")
                    print(f"❌ Error: {status}")
                    if isinstance(response_body, dict):
                        print(json.dumps(response_body, indent=2, ensure_ascii=False))
                    else:
                        print(response_body)
                
            except Exception as e:
                logger.exception(f"POST CONSENT - Error making request: {e}")
                print(f"❌ Error making request: {e}")
                import traceback
                traceback.print_exc()
    
    except Exception as e:
        logger.exception(f"POST CONSENT - Error: {e}")
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new consent")
    parser.add_argument("--client-id", help="Client ID")
    parser.add_argument("--user-id", help="User ID (Party ID)")
    parser.add_argument("--owner-id", help="Owner ID (defaults to user-id)")
    parser.add_argument("--oauth2-client-id", help="OAuth2 Client ID (defaults to client-id)")
    parser.add_argument("--oauth2-client-name", help="OAuth2 Client Name")
    parser.add_argument("--disponent-ids", help="Comma-separated list of Disponent IDs")
    parser.add_argument("--scopes", help="Comma-separated list of scopes")
    
    args = parser.parse_args()
    
    disponent_ids = None
    if args.disponent_ids:
        disponent_ids = [int(d.strip()) for d in args.disponent_ids.split(',')]
    
    scopes = None
    if args.scopes:
        scopes = [s.strip() for s in args.scopes.split(',')]
    
    test_post_consent(
        client_id=args.client_id,
        user_id=args.user_id,
        owner_id=args.owner_id,
        oauth2_client_id=args.oauth2_client_id,
        oauth2_client_name=args.oauth2_client_name,
        disponent_ids=disponent_ids,
        scopes=scopes
    )

