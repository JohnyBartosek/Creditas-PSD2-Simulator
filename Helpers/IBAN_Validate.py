"""
TPP IBAN Validation
Validates IBAN numbers using the apilayer.com API
"""

from playwright.sync_api import sync_playwright
import json
import argparse

# API Configuration
IBAN_VALIDATE_URL = "https://api.apilayer.com/bank_data/iban_validate"
API_KEY = "u8Y0E4eYGo26lg5zuW3m7eiCKUKs48cS"


def validate_iban(iban_number: str):
    """
    Validate an IBAN number using the apilayer.com API
    
    Args:
        iban_number: The IBAN number to validate (e.g., "DE89370400440532013000")
    
    Returns:
        dict: Response from the API containing validation results
    """
    with sync_playwright() as p:
        # Create API request context
        api_request_context = p.request.new_context(ignore_https_errors=True)
        
        try:
            # Prepare headers
            headers = {
                "apikey": API_KEY
            }
            
            # Build URL with query parameter
            url = f"{IBAN_VALIDATE_URL}?iban_number={iban_number}"
            
            print("="*60)
            print("IBAN VALIDATION REQUEST")
            print("="*60)
            print(f"URL: {url}")
            print(f"IBAN: {iban_number}")
            print("="*60)
            print()
            
            print("📡 Making GET request to IBAN validation endpoint...")
            print(f"📤 Headers:")
            print(f"   apikey: {API_KEY[:20]}...")
            
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
                    print("\n✅ IBAN validation request successful!")
                    
                    # Extract validation information
                    if "valid" in response_body:
                        is_valid = response_body.get("valid", False)
                        if is_valid:
                            print(f"\n✅ IBAN is VALID")
                        else:
                            print(f"\n❌ IBAN is INVALID")
                    
                    if "iban" in response_body:
                        iban = response_body.get("iban", "")
                        print(f"📋 IBAN: {iban}")
                    
                    if "bank_data" in response_body:
                        bank_data = response_body.get("bank_data", {})
                        if bank_data:
                            print(f"\n🏦 Bank Information:")
                            if "bank_name" in bank_data:
                                print(f"   Bank Name: {bank_data.get('bank_name', 'N/A')}")
                            if "bic" in bank_data:
                                print(f"   BIC: {bank_data.get('bic', 'N/A')}")
                            if "branch" in bank_data:
                                print(f"   Branch: {bank_data.get('branch', 'N/A')}")
                            if "address" in bank_data:
                                print(f"   Address: {bank_data.get('address', 'N/A')}")
                            if "city" in bank_data:
                                print(f"   City: {bank_data.get('city', 'N/A')}")
                            if "state" in bank_data:
                                print(f"   State: {bank_data.get('state', 'N/A')}")
                            if "zip" in bank_data:
                                print(f"   ZIP: {bank_data.get('zip', 'N/A')}")
                            if "country" in bank_data:
                                print(f"   Country: {bank_data.get('country', 'N/A')}")
                    
                    if "country_data" in response_body:
                        country_data = response_body.get("country_data", {})
                        if country_data:
                            print(f"\n🌍 Country Information:")
                            if "country_code" in country_data:
                                print(f"   Country Code: {country_data.get('country_code', 'N/A')}")
                            if "country_name" in country_data:
                                print(f"   Country Name: {country_data.get('country_name', 'N/A')}")
                            if "currency" in country_data:
                                print(f"   Currency: {country_data.get('currency', 'N/A')}")
                    
                    if "sepa_data" in response_body:
                        sepa_data = response_body.get("sepa_data", {})
                        if sepa_data:
                            print(f"\n💳 SEPA Information:")
                            if "SCT" in sepa_data:
                                print(f"   SCT (SEPA Credit Transfer): {sepa_data.get('SCT', 'N/A')}")
                            if "SDD" in sepa_data:
                                print(f"   SDD (SEPA Direct Debit): {sepa_data.get('SDD', 'N/A')}")
                            if "SCC" in sepa_data:
                                print(f"   SCC (SEPA Card Clearing): {sepa_data.get('SCC', 'N/A')}")
                            if "SME" in sepa_data:
                                print(f"   SME (SEPA Mobile Euro): {sepa_data.get('SME', 'N/A')}")
                    
                    return response_body
                else:
                    print(f"\n⚠️  Request failed with status {status}")
                    if "error" in response_body:
                        error = response_body.get("error", "")
                        error_message = response_body.get("message", "")
                        print(f"   Error: {error}")
                        if error_message:
                            print(f"   Message: {error_message}")
                    return None
            except Exception as e:
                response_text = response.text()
                print(f"\n📄 Response Body (text):")
                print(response_text[:1000])  # First 1000 chars
                print(f"\n⚠️  Could not parse JSON response: {e}")
                return None
            
            print("\n" + "="*60)
            
        except Exception as e:
            print(f"\n❌ Request failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
        finally:
            api_request_context.dispose()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Validate IBAN Number')
    parser.add_argument('iban', type=str, nargs='?', help='IBAN number to validate (e.g., DE89370400440532013000)')
    parser.add_argument('--iban', type=str, dest='iban_arg', help='IBAN number to validate (alternative flag format)')
    args = parser.parse_args()
    
    # Get IBAN from arguments
    iban = args.iban or args.iban_arg
    
    # If no IBAN provided, prompt for it
    if not iban:
        iban = input("Enter IBAN number to validate: ").strip()
        if not iban:
            print("❌ IBAN number is required")
            exit(1)
    
    # Validate IBAN
    result = validate_iban(iban)
    
    if result:
        print("\n✅ Validation completed")
    else:
        print("\n❌ Validation failed")
        exit(1)

