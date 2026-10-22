"""
TPP Registration DELETE API Test
Based on Bruno/Registration DELETE.bru
Deletes a client registration from the JSON database
"""

from playwright.sync_api import sync_playwright
import json
import os
import uuid
import sys
import io
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

from Helpers.environment_config import get_registration_delete_url, get_database_file

DATABASE_FILE = str(get_database_file("tpp_registrations.json"))
TOKENS_FILE = str(get_database_file("tpp_tokens.json"))
AUTH_CODES_FILE = str(get_database_file("last_authorization_code.json"))

# Headers from Bruno file (X-Request-ID will be generated as GUID)
BASE_HEADERS = {
    "X-Client-Cert": "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"
}


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


def save_database(database):
    """Save database to JSON file"""
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(database, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving database: {e}")
        return False


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
        registration_access_token = None
        
        if isinstance(response_body, dict):
            client_id = response_body.get("client_id")
            registration_access_token = response_body.get("registration_access_token")
        
        # Get timestamp
        timestamp = registration.get("timestamp", "Unknown")
        
        clients.append({
            "index": idx,
            "client_name": client_name,
            "client_id": client_id,
            "registration_access_token": registration_access_token,
            "timestamp": timestamp,
            "registration_index": idx - 1  # Store index for deletion
        })
    
    return clients


def get_client_by_id(client_id: str):
    """Get client information by client_id from database"""
    clients = list_available_clients()
    
    for client in clients:
        if client.get('client_id') == client_id:
            # Validate that we have required data
            if not client['registration_access_token']:
                print(f"❌ Client '{client['client_name']}' has no registration_access_token in database")
                return None
            return client
    
    return None


def select_client():
    """Display available clients and let user select one"""
    clients = list_available_clients()
    
    if not clients:
        print("❌ No registrations found in database!")
        print(f"   Database file: {DATABASE_FILE}")
        return None
    
    print("="*60)
    print("AVAILABLE REGISTERED CLIENTS (FOR DELETION)")
    print("="*60)
    print()
    
    for client in clients:
        print(f"  [{client['index']}] {client['client_name']}")
        print(f"      Client ID: {client['client_id']}")
        print(f"      Registered: {client['timestamp']}")
        print()
    
    while True:
        try:
            selection = input(f"Select client to DELETE (1-{len(clients)}) or 'q' to quit: ").strip()
            
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
                
                if not selected_client['registration_access_token']:
                    print(f"❌ Selected client '{selected_client['client_name']}' has no registration_access_token in database")
                    return None
                
                # Confirm deletion
                print(f"\n⚠️  WARNING: You are about to DELETE registration for:")
                print(f"   Client Name: {selected_client['client_name']}")
                print(f"   Client ID: {selected_client['client_id']}")
                confirm = input("\nType 'DELETE' to confirm, or anything else to cancel: ").strip()
                
                if confirm != 'DELETE':
                    print("❌ Deletion cancelled")
                    return None
                
                return selected_client
            else:
                print(f"⚠️  Please enter a number between 1 and {len(clients)}")
        except ValueError:
            print("⚠️  Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None


def remove_tokens_by_client_id(client_id: str):
    """Remove all tokens associated with the given client_id"""
    if not os.path.exists(TOKENS_FILE):
        return 0
    
    try:
        with open(TOKENS_FILE, 'r', encoding='utf-8') as f:
            tokens_data = json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading tokens file: {e}")
        return 0
    
    original_count = len(tokens_data.get("tokens", []))
    
    # Filter out tokens with matching client_id
    tokens_data["tokens"] = [
        token for token in tokens_data.get("tokens", [])
        if token.get("client_id") != client_id
    ]
    
    new_count = len(tokens_data.get("tokens", []))
    removed_count = original_count - new_count
    
    if removed_count > 0:
        try:
            with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
                json.dump(tokens_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Removed {removed_count} token(s) for client_id '{client_id}'")
            return removed_count
        except Exception as e:
            print(f"⚠️  Error saving tokens file: {e}")
            return 0
    
    return 0


def remove_auth_codes_by_client_id(client_id: str):
    """Remove all authorization codes associated with the given client_id"""
    if not os.path.exists(AUTH_CODES_FILE):
        return 0
    
    try:
        with open(AUTH_CODES_FILE, 'r', encoding='utf-8') as f:
            auth_codes_data = json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading authorization codes file: {e}")
        return 0
    
    # Handle both old format (single object) and new format (collection)
    if "authorization_codes" in auth_codes_data:
        # New format: collection
        original_count = len(auth_codes_data.get("authorization_codes", []))
        
        # Filter out authorization codes with matching client_id
        auth_codes_data["authorization_codes"] = [
            code for code in auth_codes_data.get("authorization_codes", [])
            if code.get("client_id") != client_id
        ]
        
        new_count = len(auth_codes_data.get("authorization_codes", []))
        removed_count = original_count - new_count
    else:
        # Old format: single object
        if auth_codes_data.get("client_id") == client_id:
            removed_count = 1
            auth_codes_data = {"authorization_codes": []}
        else:
            removed_count = 0
    
    if removed_count > 0:
        try:
            with open(AUTH_CODES_FILE, 'w', encoding='utf-8') as f:
                json.dump(auth_codes_data, f, indent=2, ensure_ascii=False)
            print(f"✅ Removed {removed_count} authorization code(s) for client_id '{client_id}'")
            return removed_count
        except Exception as e:
            print(f"⚠️  Error saving authorization codes file: {e}")
            return 0
    
    return 0


def remove_from_database(client_id: str):
    """Remove registration with given client_id from database and clean up related data"""
    database = load_database()
    original_count = len(database.get("registrations", []))
    
    # Filter out the registration with matching client_id
    database["registrations"] = [
        reg for reg in database.get("registrations", [])
        if reg.get("response", {}).get("body", {}).get("client_id") != client_id
    ]
    
    new_count = len(database.get("registrations", []))
    
    if new_count < original_count:
        if save_database(database):
            print(f"✅ Registration removed from database")
            print(f"   Remaining registrations: {new_count}")
            
            # Clean up related tokens and authorization codes
            tokens_removed = remove_tokens_by_client_id(client_id)
            auth_codes_removed = remove_auth_codes_by_client_id(client_id)
            
            if tokens_removed > 0 or auth_codes_removed > 0:
                print(f"\n🧹 Cleanup summary:")
                if tokens_removed > 0:
                    print(f"   - Removed {tokens_removed} token(s)")
                if auth_codes_removed > 0:
                    print(f"   - Removed {auth_codes_removed} authorization code(s)")
            
            return True
        else:
            print(f"❌ Failed to save database after removal")
            return False
    else:
        print(f"⚠️  Registration with client_id '{client_id}' not found in database")
        return False


def test_tpp_registration_delete(client_id: str = None):
    """
    Test TPP Registration DELETE endpoint
    
    Args:
        client_id: Optional client_id. If provided (GUI mode), skips interactive selection.
    """
    # Get client from database
    if client_id:
        # GUI mode: get client by ID
        selected_client = get_client_by_id(client_id)
        if not selected_client:
            print(f"❌ Registration with client_id '{client_id}' not found in database")
            return
    else:
        # Console mode: interactive selection
        selected_client = select_client()
        if not selected_client:
            return
    
    client_name = selected_client['client_name']
    client_id = selected_client['client_id']
    registration_access_token = selected_client['registration_access_token']
    
    # Build URL with client_id
    registration_url = get_registration_delete_url(client_id)
    
    with sync_playwright() as p:
        # Create API request context with SSL verification disabled
        api_request_context = p.request.new_context(ignore_https_errors=True)
        
        try:
            # Generate GUID for X-Request-ID
            request_id = str(uuid.uuid4())
            
            # Create headers with generated GUID and registration access token
            headers = {
                **BASE_HEADERS,
                "X-Request-ID": request_id,
                "X-TPP-Authorization": registration_access_token
            }
            
            print("="*60)
            print("TPP REGISTRATION DELETE TEST")
            print("="*60)
            print(f"\n📡 Making DELETE request to: {registration_url}")
            print(f"📋 Client Name: {client_name}")
            print(f"📋 Client ID: {client_id}")
            print(f"\n📤 Headers:")
            print(f"   X-Request-ID: {request_id}")
            print(f"   X-TPP-Authorization: {registration_access_token[:50]}...")
            print(f"   X-Client-Cert: {headers['X-Client-Cert'][:50]}...")
            
            # Make DELETE request
            response = api_request_context.delete(
                registration_url,
                headers=headers
            )
            
            # Get response details
            status = response.status
            print(f"\n📥 Response Status: {status}")
            print(f"📋 Response Headers: {dict(response.headers)}")
            
            # Get response body (if any)
            try:
                response_body = response.json()
                print(f"\n📄 Response Body:")
                print(json.dumps(response_body, indent=2))
            except:
                response_text = response.text()
                if response_text:
                    print(f"\n📄 Response Body (text):")
                    print(response_text[:1000])  # First 1000 chars
                else:
                    print(f"\n📄 Response Body: (empty)")
            
            # Check if status is 200 (or 204 No Content)
            if status in [200, 204]:
                print(f"\n✅ Registration deleted successfully (Status {status})")
                
                # Remove from database
                if remove_from_database(client_id):
                    print(f"💾 Database updated: Registration for '{client_name}' removed")
                else:
                    print(f"⚠️  Database update failed, but API deletion was successful")
            else:
                print(f"\n⚠️  Delete request failed with status {status}")
                print("   Registration NOT removed from database")
            
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
    parser = argparse.ArgumentParser(description='TPP Registration DELETE')
    parser.add_argument('--client-id', type=str, help='Client ID to delete (GUI mode)')
    args = parser.parse_args()
    
    try:
        # If client_id provided via args (GUI mode), use it; otherwise prompt in console
        test_tpp_registration_delete(client_id=args.client_id)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

