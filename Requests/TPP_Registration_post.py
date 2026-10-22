"""
TPP Registration POST API Test
Based on Bruno/Registration.bru
Stores successful (200) responses in a JSON database file
"""

from playwright.sync_api import sync_playwright
import json
import os
import uuid
import sys
import io
from datetime import datetime, timezone
from pathlib import Path

# Fix encoding for Windows console to prevent UnicodeEncodeError
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Fallback for older Python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Get the parent directory (project root)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.environment_config import get_registration_post_url, get_database_file

DATABASE_FILE = str(get_database_file("tpp_registrations.json"))
# Template file is shared across environments
TEMPLATE_FILE = str(PROJECT_ROOT / "Database" / "tpp_registration_template_data.json")

# Headers from Bruno file (X-Request-ID will be generated as GUID)
BASE_HEADERS = {
    "X-Client-Cert": "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",
    "Content-Type": "application/json"
}

# Load request body template from file
def load_request_template():
    """Load request body template from Database/tpp_registration_template_data.json"""
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading template file: {e}")
            return None
    else:
        print(f"⚠️  Template file not found: {TEMPLATE_FILE}")
        return None
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


def check_client_name_exists(client_name: str) -> bool:
    """
    Check if a registration with the given client_name already exists in the database
    
    Args:
        client_name: The client name to check for
    
    Returns:
        True if client_name exists, False otherwise
    """
    database = load_database()
    
    for registration in database.get("registrations", []):
        # Check in request body
        request_body = registration.get("request", {}).get("body", {})
        if request_body.get("client_name") == client_name:
            return True
        
        # Also check in response body (in case it's stored there)
        response_body = registration.get("response", {}).get("body", {})
        if isinstance(response_body, dict) and response_body.get("client_name") == client_name:
            return True
    
    return False


def save_to_database(response_data, request_body):
    """Save successful registration to JSON database file"""
    database = load_database()
    
    # Create registration entry
    registration_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "request": {
            "url": get_registration_post_url(),
            "headers": response_data.get("request_headers", {}),
            "body": request_body
        },
        "response": response_data
    }
    
    # Add to database
    database["registrations"].append(registration_entry)
    
    # Save to file
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(database, f, indent=2, ensure_ascii=False)
        print(f"✅ Registration saved to database: {DATABASE_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving to database: {e}")
        return False


def test_tpp_registration(client_name: str = None, scope: str = None):
    """
    Test TPP Registration POST endpoint
    
    Args:
        client_name: Optional client name. If None, will prompt in console mode or use template name.
        scope: Optional scope. If provided, will overwrite template scope. If None, will use template scope or prompt in console.
    """
    # Load template
    request_body_template = load_request_template()
    if not request_body_template:
        print("❌ Cannot proceed without template file")
        return
    
    # Get client name
    if not client_name:
        # Console mode: ask for client name
        client_name = input("\nEnter Registration Name (client_name): ").strip()
        if not client_name:
            print("❌ Client name is required")
            return
    
    # Get scope
    if not scope:
        # Console mode: ask for scope
        print("\nAvailable scopes:")
        print("  1. aisp")
        print("  2. pisp")
        print("  3. aisp pisp")
        scope_choice = input("Select scope (1-3) or enter custom scope: ").strip()
        if scope_choice == "1":
            scope = "aisp"
        elif scope_choice == "2":
            scope = "pisp"
        elif scope_choice == "3":
            scope = "aisp pisp"
        elif scope_choice:
            scope = scope_choice
        else:
            # Use template scope if available
            scope = request_body_template.get("scope", "") or request_body_template.get("scopes", "aisp")
    
    # Create request body from template with custom client name and scope
    REQUEST_BODY = request_body_template.copy()
    REQUEST_BODY["client_name"] = client_name
    
    # Overwrite scope in both possible fields
    REQUEST_BODY["scope"] = scope
    if "scopes" in REQUEST_BODY:
        REQUEST_BODY["scopes"] = scope
    
    # Check if registration already exists
    print("="*60)
    print("TPP REGISTRATION POST TEST")
    print("="*60)
    print(f"\n🔍 Checking database for existing registration...")
    print(f"   Client Name: {client_name}")
    
    if check_client_name_exists(client_name):
        print(f"\n⚠️  Registration with client_name '{client_name}' already exists in database!")
        print(f"   Database file: {DATABASE_FILE}")
        print(f"\n❌ Execution stopped to prevent duplicate registration.")
        print("="*60)
        return
    
    print(f"✅ No existing registration found for '{client_name}'")
    print("   Proceeding with registration...\n")
    
    with sync_playwright() as p:
        # Create API request context with SSL verification disabled
        api_request_context = p.request.new_context(ignore_https_errors=True)
        
        try:
            # Generate GUID for X-Request-ID
            request_id = str(uuid.uuid4())
            
            # Create headers with generated GUID
            headers = {
                **BASE_HEADERS,
                "X-Request-ID": request_id
            }
            
            registration_url = get_registration_post_url()
            print(f"\n📡 Making POST request to: {registration_url}")
            print(f"📋 Request Body:")
            print(json.dumps(REQUEST_BODY, indent=2))
            print(f"\n📤 Headers:")
            print(f"   X-Request-ID: {request_id}")
            print(f"   X-Client-Cert: {headers['X-Client-Cert'][:50]}...")
            
            # Make POST request
            response = api_request_context.post(
                registration_url,
                headers=headers,
                data=json.dumps(REQUEST_BODY)
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
            except:
                response_text = response.text()
                print(f"\n📄 Response Body (text):")
                print(response_text[:500])  # First 500 chars
                response_body = {"raw_text": response_text}
            
            # Check if status is 200
            if status == 200:
                print("\n✅ Registration successful (200 OK)")
                
                # Prepare response data for database
                response_data = {
                    "status": status,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "request_headers": headers  # Include the request headers with GUID
                }
                
                # Save to database
                if save_to_database(response_data, REQUEST_BODY):
                    print(f"💾 Total registrations in database: {len(load_database()['registrations'])}")
                else:
                    print("⚠️  Failed to save to database")
            else:
                print(f"\n⚠️  Registration failed with status {status}")
                print("   Response not saved to database (only 200 responses are saved)")
            
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"\n❌ Test failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            api_request_context.dispose()


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='TPP Registration POST')
    parser.add_argument('--client-name', type=str, help='Client name for registration (GUI mode)')
    parser.add_argument('--scope', type=str, help='Scope for registration (GUI mode). Options: aisp, pisp, "aisp pisp"')
    args = parser.parse_args()
    
    try:
        # If client_name provided via args (GUI mode), use it; otherwise prompt in console
        test_tpp_registration(client_name=args.client_name, scope=args.scope)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

