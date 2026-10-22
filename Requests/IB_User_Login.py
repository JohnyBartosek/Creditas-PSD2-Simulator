"""
Internet Banking User Login Test
Automates Internet Banking login flow (username, birthday, password, SMS OTP)
Similar structure to TPP_User_Authorization.py but simplified for login only (no OAuth2)
"""

from playwright.sync_api import sync_playwright
import json
import os
import random
import argparse
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode
import sys
import os
from pathlib import Path

# Get the parent directory (project root)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add parent directory to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.sms_otp_helper import wait_for_sms_otp
from Helpers.file_lock_helper import safe_update_json
from Helpers.environment_config import get_ib_login_url, get_database_file

# Database files (environment-aware paths)
DEFAULT_AUTH_CONFIG_FILE = str(get_database_file("default_auth_config.json"))
USERS_FILE = str(get_database_file("users.json"))


def load_default_auth_config():
    """Load default authentication configuration"""
    if os.path.exists(DEFAULT_AUTH_CONFIG_FILE):
        try:
            with open(DEFAULT_AUTH_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading default auth config: {e}")
            return None
    return None


def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading users: {e}")
            return {"users": []}
    return {"users": []}


def get_user_by_party_id(party_id: str):
    """Get user by party ID"""
    users_data = load_users()
    for user in users_data.get("users", []):
        if user.get("partyId") == party_id:
            return user
    return None


def parse_birth_date(birth_date: str):
    """
    Parse birth date from format "27.06.1971" to day and month
    Returns tuple (day, month) as strings
    """
    try:
        # Format: "27.06.1971" or "27.6.1971"
        parts = birth_date.split('.')
        if len(parts) >= 2:
            day = parts[0].strip()
            month = parts[1].strip()
            return (day, month)
    except:
        pass
    return (None, None)


def get_czech_month_name(month_num: str) -> str:
    """
    Convert month number to Czech month name
    Args:
        month_num: Month number as string (e.g., "6", "06")
    Returns:
        Czech month name (e.g., "Červen")
    """
    month_map = {
        "1": "Leden",
        "01": "Leden",
        "2": "Únor",
        "02": "Únor",
        "3": "Březen",
        "03": "Březen",
        "4": "Duben",
        "04": "Duben",
        "5": "Květen",
        "05": "Květen",
        "6": "Červen",
        "06": "Červen",
        "7": "Červenec",
        "07": "Červenec",
        "8": "Srpen",
        "08": "Srpen",
        "9": "Září",
        "09": "Září",
        "10": "Říjen",
        "11": "Listopad",
        "12": "Prosinec"
    }
    return month_map.get(month_num, month_num)

def select_user():
    """Display available users and let user select one"""
    users_data = load_users()
    users = users_data.get("users", [])
    
    if not users:
        print("❌ No users found in database!")
        print(f"   Users file: {USERS_FILE}")
        return None
    
    print("="*60)
    print("AVAILABLE USERS")
    print("="*60)
    print()
    
    for idx, user in enumerate(users, 1):
        print(f"  [{idx}] {user.get('name', 'Unknown')}")
        print(f"      Party ID: {user.get('partyId', 'N/A')}")
        print(f"      Username: {user.get('username', 'N/A')}")
        print(f"      Birth Date: {user.get('birthDate', 'N/A')}")
        print()
    
    while True:
        try:
            selection = input(f"Select user (1-{len(users)}) or 'q' to quit: ").strip()
            
            if selection.lower() == 'q':
                print("❌ Cancelled by user")
                return None
            
            selection_num = int(selection)
            if 1 <= selection_num <= len(users):
                selected_user = users[selection_num - 1]
                return selected_user
            else:
                print(f"⚠️  Please enter a number between 1 and {len(users)}")
        except ValueError:
            print("⚠️  Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return None

def test_login_endpoint(user_id: str = None):
    """
    Test the Internet Banking login endpoint in a browser
    
    Args:
        user_id: User ID (party_id as string). If provided, will use this instead of default config.
    """
    # Load default auth config (for party_id if needed)
    auth_config = load_default_auth_config()
    
    # If user_id is provided (from GUI context), use it
    if user_id:
        try:
            party_id = int(user_id)
        except:
            party_id = None
            
        # Get user by party_id
        user = get_user_by_party_id(user_id)
        if not user:
            print(f"⚠️  Could not find user with partyId '{user_id}' in users database!")
            print(f"   Users file: {USERS_FILE}")
            user = None
        else:
            print(f"✅ Loaded user: {user.get('name')} (Party ID: {user_id})")
        
        print(f"✅ Using context: User={user_id}")
    elif not auth_config:
        # Console mode: Let user choose user
        print("="*60)
        print("CONSOLE MODE - SELECT USER")
        print("="*60)
        print()
        
        # Select user
        selected_user = select_user()
        if not selected_user:
            return
        
        user = selected_user
        party_id = None
        try:
            party_id = int(selected_user.get('partyId'))
        except:
            print(f"⚠️  Could not parse partyId '{selected_user.get('partyId')}' as integer")
            party_id_input = input("Enter Party ID (for SMS OTP retrieval) or press Enter to skip: ").strip()
            if party_id_input and party_id_input.isdigit():
                party_id = int(party_id_input)
        
        print(f"✅ Selected: User={user.get('name')} (Party ID: {user.get('partyId')})")
    else:
        # Console mode with config: Use config but let user choose if they want
        config_party_id = auth_config.get("partyId")
        
        print("="*60)
        print("CONSOLE MODE - USING DEFAULT CONFIG")
        print("="*60)
        print(f"Default User (Party ID): {config_party_id}")
        print()
        
        # Ask if user wants to use default config or choose manually
        use_default = input("Use default configuration? (Y/n): ").strip().lower()
        
        if use_default and use_default != 'n':
            # Use default config
            user = get_user_by_party_id(config_party_id)
            if not user:
                print(f"⚠️  Could not find user with partyId '{config_party_id}' in users database!")
                print(f"   Users file: {USERS_FILE}")
                user = None
            else:
                print(f"✅ Loaded user: {user.get('name')} (Party ID: {config_party_id})")
            
            # Use party_id from config if not provided
            if not party_id and config_party_id:
                try:
                    party_id = int(config_party_id)
                except:
                    pass
        else:
            # Manual selection
            print()
            print("Manual selection mode...")
            
            selected_user = select_user()
            if not selected_user:
                return
            
            user = selected_user
            party_id = None
            try:
                party_id = int(selected_user.get('partyId'))
            except:
                print(f"⚠️  Could not parse partyId '{selected_user.get('partyId')}' as integer")
                party_id_input = input("Enter Party ID (for SMS OTP retrieval) or press Enter to skip: ").strip()
                if party_id_input and party_id_input.isdigit():
                    party_id = int(party_id_input)
            
            print(f"✅ Selected: User={user.get('name')} (Party ID: {user.get('partyId')})")
    
    # Initialize password variable (will be set from user data or prompted)
    password = user.get("password") if user else None
    
    print("="*60)
    print("INTERNET BANKING LOGIN")
    print("="*60)
    print()
    
    with sync_playwright() as p:
        # Launch browser (not headless so user can see the flow)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        
        # Create API request context for SMS OTP retrieval
        api_request_context = p.request.new_context(ignore_https_errors=True)
        
        try:
            auth_base_url = get_ib_login_url()
            print(f"🌐 Opening browser and navigating to login URL...")
            print(f"URL: {auth_base_url}\n")
            
            # Navigate to the login URL
            try:
                response = page.goto(auth_base_url, wait_until="domcontentloaded", timeout=30000)
                
                # Check response status
                if response:
                    status = response.status
                    print(f"📊 Response Status: {status}")
                    if status >= 400:
                        print(f"⚠️  HTTP Error {status} - Login request failed!")
                        # Try to get error details
                        try:
                            error_text = page.content()
                            if "Whitelabel Error Page" in error_text or "error" in error_text.lower():
                                # Try to extract error message
                                error_match = page.locator("div").filter(has_text="error").first
                                if error_match.count() > 0:
                                    error_msg = error_match.inner_text()
                                    print(f"❌ Error: {error_msg}")
                        except:
                            pass
                        
                        # Show the actual URL that was requested
                        print(f"\n🔍 Debugging Information:")
                        print(f"   Requested URL: {auth_base_url}")
                        print(f"\n💡 Possible issues:")
                        print(f"   - Login service might be unavailable")
                        print(f"   - Network connectivity issues")
                        
                        return
            except Exception as e:
                print(f"❌ Error navigating to login URL: {e}")
                return
            
            print(f"📍 Current URL: {page.url}")
            print(f"📄 Page Title: {page.title()}\n")
            
            # Wait for the login form to appear and fill in username
            print("🔍 Looking for username input field...")
            
            # Wait for page to be ready
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # Try to find and fill username field (try multiple common selectors)
            username_filled = False
            username_selectors = [
                'input[type="text"]',
                'input[type="email"]',
                'input[name="username"]',
                'input[name="user"]',
                'input[id*="user"]',
                'input[id*="login"]',
                'input[placeholder*="user" i]',
                'input[placeholder*="email" i]',
                'input[autocomplete="username"]',
                'input[autocomplete="email"]'
            ]
            
            # Get username from user data or prompt
            username = user.get("username") if user else None
            if not username:
                username = input("Enter username: ").strip()
                if not username:
                    print("❌ Username is required")
                    return
            
            for selector in username_selectors:
                try:
                    username_input = page.locator(selector).first
                    if username_input.is_visible(timeout=2000):
                        print(f"✅ Found username field with selector: {selector}")
                        username_input.fill(username)
                        username_filled = True
                        print(f"✅ Username filled: {username}")
                        break
                except:
                    continue
            
            if not username_filled:
                print("⚠️  Could not find username field automatically. Trying to find any visible input...")
                try:
                    # Try to find any visible input field
                    all_inputs = page.locator('input[type="text"], input[type="email"], input:not([type="hidden"])').all()
                    for input_field in all_inputs:
                        if input_field.is_visible():
                            input_field.fill(username)
                            username_filled = True
                            print(f"✅ Username filled in first visible input field: {username}")
                            break
                except Exception as e:
                    print(f"⚠️  Could not auto-fill username: {e}")
            
            # Wait a moment for any dynamic updates
            page.wait_for_timeout(200)  # Reduced from 500ms
            
            # Find and click the submit/confirm button
            print("\n🔍 Looking for submit/confirm button...")
            button_clicked = False
            
            # Try multiple button selectors
            button_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Confirm")',
                'button:has-text("Submit")',
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button[id*="submit"]',
                'button[id*="confirm"]',
                'button[id*="login"]',
                'button[class*="submit"]',
                'button[class*="confirm"]',
                'form button',  # Any button in a form
                'button.primary',
                'button.btn-primary'
            ]
            
            for selector in button_selectors:
                try:
                    button = page.locator(selector).first
                    if button.is_visible(timeout=2000):
                        print(f"✅ Found button with selector: {selector}")
                        button_text = button.text_content() if button else "N/A"
                        print(f"   Button text: {button_text}")
                        button.click()
                        button_clicked = True
                        print("✅ Button clicked")
                        break
                except:
                    continue
            
            if not button_clicked:
                print("⚠️  Could not find submit button automatically. Trying Enter key...")
                try:
                    # Try pressing Enter on the username field
                    if username_filled:
                        page.keyboard.press("Enter")
                        button_clicked = True
                        print("✅ Pressed Enter key")
                except Exception as e:
                    print(f"⚠️  Could not submit form: {e}")
            
            # Wait for navigation after form submission
            if button_clicked or username_filled:
                print("\n⏳ Waiting for page navigation after form submission...")
                page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
                print(f"📍 Current URL after submission: {page.url}\n")
            
            # After confirmation, fill in birthday fields
            print("🔍 Waiting for birthday page to load...")
            page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
            page.wait_for_timeout(500)  # Reduced from 2000ms
            
            # Debug: Print page content to help identify the element
            print(f"📍 Current URL: {page.url}")
            print(f"📄 Page Title: {page.title()}")
            
            print("🔍 Looking for birthday input fields...")
            birthday_filled = False
            
            # Get birth date from user data
            birth_day = None
            birth_month = None
            birth_month_czech = None
            if user and user.get("birthDate"):
                birth_day, birth_month = parse_birth_date(user.get("birthDate"))
                if birth_month:
                    birth_month_czech = get_czech_month_name(birth_month)
                print(f"📅 Parsed birth date: Day={birth_day}, Month={birth_month} ({birth_month_czech})")
            
            if not birth_day or not birth_month:
                print("⚠️  Birth date not found in user data, prompting...")
                birth_day = input("Enter birth day (e.g., 27): ").strip()
                birth_month = input("Enter birth month (e.g., 6): ").strip()
                if birth_month:
                    birth_month_czech = get_czech_month_name(birth_month)
            
            # Based on the HTML structure, these are combobox buttons (Radix UI)
            # Day combobox: button with "Den" text
            # Month combobox: button with "Měsíc" text
            day_filled = False
            month_filled = False
            
            # Try to find day combobox button (contains "Den")
            print("🔍 Looking for day combobox (Den)...")
            try:
                # Find button with role="combobox" that contains "Den" text
                day_combobox = page.locator('button[role="combobox"]').filter(has_text='Den').first
                if day_combobox.is_visible(timeout=5000):
                    print("✅ Found day combobox button")
                    # Click to open the dropdown
                    day_combobox.click()
                    page.wait_for_timeout(300)  # Reduced from 800ms
                    
                    # Try to find the hidden select element and use select_option
                    try:
                        # Find select in the same container (parent div)
                        day_select = day_combobox.locator('xpath=ancestor::div[1]//select').first
                        if day_select.count() > 0:
                            print(f"   Found hidden select, selecting value {birth_day}...")
                            day_select.select_option(value=birth_day)
                            day_filled = True
                            print(f"✅ Selected day: {birth_day} (via hidden select)")
                            # Wait for selection to process
                            page.wait_for_timeout(300)  # Reduced from 1000ms
                            
                            # Check if dropdown is still open and close it
                            try:
                                # Check if the combobox is still expanded
                                is_expanded = day_combobox.get_attribute('aria-expanded')
                                if is_expanded == 'true':
                                    print("   Dropdown still open, closing...")
                                    page.keyboard.press("Escape")
                                    page.wait_for_timeout(200)  # Reduced from 500ms
                            except:
                                # Also try clicking outside the dropdown
                                try:
                                    page.click('body', position={'x': 10, 'y': 10})
                                    page.wait_for_timeout(200)  # Reduced from 300ms
                                except:
                                    pass
                    except Exception as e1:
                        print(f"   Hidden select method failed: {e1}")
                        # Alternative: try to find visible option in popover/portal
                        try:
                            # Look for option with text matching birth_day - could be in a popover
                            option_day = page.locator(f'[role="option"]:has-text("{birth_day}"), [role="listbox"] [role="option"]:has-text("{birth_day}")').first
                            if option_day.is_visible(timeout=200):
                                option_day.click()
                                day_filled = True
                                print(f"✅ Selected day: {birth_day} (via visible option)")
                                # Wait for dropdown to close
                                page.wait_for_timeout(200)  # Reduced from 500ms
                            else:
                                # Try finding by exact text match
                                all_options = page.locator('[role="option"]').all()
                                for opt in all_options:
                                    if opt.text_content().strip() == birth_day:
                                        opt.click()
                                        day_filled = True
                                        print(f"✅ Selected day: {birth_day} (via option iteration)")
                                        page.wait_for_timeout(200)  # Reduced from 500ms
                                        break
                        except Exception as e2:
                            print(f"   Visible option method failed: {e2}")
                    
                    # Verify selection was made
                    if day_filled:
                        print("   Waiting for day selection to complete...")
                        page.wait_for_timeout(300)  # Reduced from 1000ms
                        # Check if combobox shows "27"
                        try:
                            current_value = day_combobox.locator('span:not(.text-brand)').last.text_content()
                            print(f"   Current day value: {current_value}")
                        except:
                            pass
            except Exception as e:
                print(f"⚠️  Error finding day combobox: {e}")
            
            # Wait a bit between day and month selection to ensure day selection is complete
            if day_filled:
                print("⏳ Waiting before selecting month...")
                page.wait_for_timeout(400)  # Reduced from 1500ms
                # Check if any dropdown is still open and close it
                try:
                    # Check if combobox is still expanded
                    open_combobox = page.locator('button[role="combobox"][aria-expanded="true"]').first
                    if open_combobox.is_visible(timeout=300):  # Reduced from 500ms
                        print("   Closing any open dropdown...")
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(200)  # Reduced from 500ms
                except:
                    pass
            
            # Try to find month combobox button (contains "Měsíc")
            print("🔍 Looking for month combobox (Měsíc)...")
            try:
                # Find button with role="combobox" that contains "Měsíc" text
                month_combobox = page.locator('button[role="combobox"]').filter(has_text='Měsíc').first
                if month_combobox.is_visible(timeout=5000):
                    print("✅ Found month combobox button")
                    # Click to open the dropdown
                    month_combobox.click()
                    page.wait_for_timeout(200)  # Reduced from 400ms
                    
                    # Prioritize visible option click - faster and more reliable
                    if birth_month_czech:
                        print(f"   Clicking Czech month: {birth_month_czech}...")
                        month_filled = False
                        
                        # Method 1: Direct locator with exact text (fastest)
                        try:
                            month_option = page.locator(f'[role="option"]:has-text("{birth_month_czech}")').first
                            if month_option.is_visible(timeout=500):  # Reduced from 1000ms
                                month_option.click()
                                month_filled = True
                                print(f"✅ Selected month: {birth_month_czech}")
                        except:
                            pass
                        
                        # Method 2: Iterate through options if direct click failed
                        if not month_filled:
                            try:
                                all_options = page.locator('[role="option"]').all()
                                for opt in all_options:
                                    try:
                                        text = opt.text_content().strip()
                                        if text == birth_month_czech:
                                            opt.click()
                                            month_filled = True
                                            print(f"✅ Selected month: {text}")
                                            break
                                    except:
                                        continue
                            except:
                                pass
                        
                        # Method 3: Try hidden select with both "6" and "06" if visible methods failed
                        if not month_filled:
                            try:
                                month_select = month_combobox.locator('xpath=ancestor::div[1]//select').first
                                if month_select.count() > 0:
                                    # Try with numeric value without leading zero first
                                    month_value = str(int(birth_month))  # Convert "06" to "6"
                                    try:
                                        month_select.select_option(value=month_value, timeout=1000)  # Reduced from 2000ms
                                        month_filled = True
                                        print(f"✅ Selected month via select: {birth_month_czech}")
                                    except:
                                        # Try with original value
                                        try:
                                            month_select.select_option(value=birth_month, timeout=1000)  # Reduced from 2000ms
                                            month_filled = True
                                            print(f"✅ Selected month via select: {birth_month_czech}")
                                        except:
                                            pass
                            except:
                                pass
                        
                        # Wait briefly after selection
                        if month_filled:
                            page.wait_for_timeout(200)  # Reduced from 300ms
                            # Close dropdown if still open
                            try:
                                if month_combobox.get_attribute('aria-expanded') == 'true':
                                    page.keyboard.press("Escape")
                            except:
                                pass
            except Exception as e:
                print(f"⚠️  Error finding month combobox: {e}")
            
            # If we couldn't find separate day/month fields, try a combined date field
            if not (day_filled and month_filled):
                print("🔍 Trying to find combined date field...")
                date_selectors = [
                    'input[name*="date"]',
                    'input[name*="birthday"]',
                    'input[name*="birth"]',
                    'input[id*="date"]',
                    'input[id*="birthday"]',
                    'input[type="date"]',
                    'input[placeholder*="date" i]',
                    'input[placeholder*="datum" i]',  # Czech: datum = date
                ]
                
                for selector in date_selectors:
                    try:
                        date_field = page.locator(selector).first
                        if date_field.is_visible(timeout=2000):
                            print(f"✅ Found date field with selector: {selector}")
                            # Try different date formats
                            date_formats = ["27.6.", "27.06.", "27/6", "27/06", "2024-06-27", "27-06"]
                            for date_format in date_formats:
                                try:
                                    date_field.fill(date_format)
                                    birthday_filled = True
                                    print(f"✅ Filled date: {date_format}")
                                    break
                                except:
                                    continue
                            if birthday_filled:
                                break
                    except:
                        continue
            
            birthday_filled = (day_filled and month_filled) or birthday_filled
            
            # Wait a moment after filling
            if birthday_filled:
                page.wait_for_timeout(200)  # Reduced from 500ms
            else:
                print("⚠️  Could not fill birthday fields automatically")
                page.wait_for_timeout(300)  # Reduced from 1000ms
            
            # Find and click continue button after filling birthday
            print("\n🔍 Looking for continue button after birthday entry...")
            continue_clicked = False
            
            continue_button_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Confirm")',
                'button:has-text("Submit")',
                'button[type="submit"]',
                'input[type="submit"]',
                'button.primary',
                'button.btn-primary',
                'button[class*="continue"]',
                'button[class*="next"]',
                'a:has-text("Continue")',
                'a:has-text("Next")',
            ]
            
            for selector in continue_button_selectors:
                try:
                    continue_button = page.locator(selector).first
                    if continue_button.is_visible(timeout=2000):
                        print(f"✅ Found continue button with selector: {selector}")
                        button_text = continue_button.text_content() if continue_button else "N/A"
                        print(f"   Button text: {button_text}")
                        continue_button.click()
                        continue_clicked = True
                        print("✅ Continue button clicked")
                        break
                except:
                    continue
            
            if not continue_clicked:
                print("⚠️  Could not find continue button. Trying Enter key...")
                try:
                    page.keyboard.press("Enter")
                    continue_clicked = True
                    print("✅ Pressed Enter key")
                except Exception as e:
                    print(f"⚠️  Could not continue: {e}")
            
            # Wait for navigation after continue
            if continue_clicked:
                print("\n⏳ Waiting for page navigation after continue...")
                page.wait_for_load_state("networkidle", timeout=10000)
                print(f"📍 Current URL after continue: {page.url}\n")
            
            # After date confirmation, fill in password field
            print("🔍 Looking for password field...")
            page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
            page.wait_for_timeout(300)  # Reduced from 1000ms
            
            # Get password from user data if not already set
            if not password:
                if user:
                    password = user.get("password")
                if not password:
                    password = input("Enter password: ").strip()
                    if not password:
                        print("❌ Password is required")
                        return
            
            password_filled = False
            
            # Try exact id="password" first (most specific)
            try:
                print("   Trying exact id='password'...")
                password_field = page.locator('#password')
                password_field.wait_for(state='visible', timeout=5000)
                if password_field.is_visible():
                    print("✅ Found password field with id='password'")
                    password_field.fill(password)
                    password_filled = True
                    print("✅ Password filled")
            except Exception as e:
                print(f"   id='password' not found: {e}")
            
            # If that didn't work, try other selectors
            if not password_filled:
                password_selectors = [
                    'input[name="password"]',
                    'input[type="password"]',
                    'input[id*="password"]',
                    'input[name*="password"]',
                    'input[autocomplete="current-password"]',
                ]
                
                for selector in password_selectors:
                    try:
                        print(f"   Trying selector: {selector}...")
                        password_field = page.locator(selector).first
                        password_field.wait_for(state='visible', timeout=3000)
                        if password_field.is_visible():
                            print(f"✅ Found password field with selector: {selector}")
                            password_field.fill(password)
                            password_filled = True
                            print("✅ Password filled")
                            break
                    except Exception as e:
                        print(f"   Selector {selector} failed: {e}")
                        continue
            
            if not password_filled:
                print("⚠️  Could not find password field automatically")
                # Try to find any password input as last resort
                try:
                    print("   Trying to find any password input...")
                    all_password_inputs = page.locator('input[type="password"]').all()
                    print(f"   Found {len(all_password_inputs)} password input(s)")
                    if len(all_password_inputs) > 0:
                        for i, pwd_input in enumerate(all_password_inputs):
                            try:
                                if pwd_input.is_visible(timeout=2000):
                                    pwd_input.fill(password)
                                    password_filled = True
                                    print(f"✅ Password filled in password input #{i+1}")
                                    break
                            except:
                                continue
                except Exception as e:
                    print(f"⚠️  Error filling password: {e}")
            
            # Wait a moment after filling password
            if password_filled:
                page.wait_for_timeout(200)  # Reduced from 500ms
            
            # After password, handle SMS code (single OTP input field)
            print("\n🔍 Looking for SMS code input field...")
            page.wait_for_load_state("domcontentloaded", timeout=5000)  # Faster than networkidle
            page.wait_for_timeout(300)  # Reduced from 1000ms
            
            sms_code_filled = False
            sms_input_field = None
            
            # Try to find the OTP input field - it's a single field with data-input-otp="true"
            try:
                # Try exact OTP input selector first
                otp_selectors = [
                    'input[data-input-otp="true"]',
                    'input[data-input-otp]',
                    'input[autocomplete="one-time-code"]',
                    'input[inputmode="numeric"][maxlength="6"]',
                    'input[pattern="^\\d+$"][maxlength="6"]',
                ]
                
                for selector in otp_selectors:
                    try:
                        print(f"   Trying selector: {selector}...")
                        sms_input_field = page.locator(selector).first
                        sms_input_field.wait_for(state='visible', timeout=3000)
                        if sms_input_field.is_visible():
                            print(f"✅ Found SMS code input field with selector: {selector}")
                            break
                    except Exception as e:
                        print(f"   Selector {selector} failed: {e}")
                        continue
                
                # If not found, try to find in OTP container
                if not sms_input_field or not sms_input_field.is_visible():
                    try:
                        print("   Trying to find in OTP container...")
                        otp_container = page.locator('[data-input-otp-container="true"]').first
                        if otp_container.is_visible(timeout=2000):
                            sms_input_field = otp_container.locator('input').first
                            if sms_input_field.is_visible():
                                print("✅ Found SMS code input in OTP container")
                    except:
                        pass
                
                # If still not found, try other patterns
                if not sms_input_field or not sms_input_field.is_visible():
                    try:
                        print("   Trying alternative patterns...")
                        # Look for input with maxlength="6" and numeric pattern
                        all_inputs = page.locator('input[maxlength="6"]').all()
                        for inp in all_inputs:
                            try:
                                pattern = inp.get_attribute('pattern')
                                inputmode = inp.get_attribute('inputmode')
                                if (pattern and '\\d' in pattern) or inputmode == 'numeric':
                                    if inp.is_visible(timeout=1000):
                                        sms_input_field = inp
                                        print("✅ Found SMS code input with numeric pattern")
                                        break
                            except:
                                continue
                    except Exception as e:
                        print(f"   Alternative pattern search failed: {e}")
                
                # Retrieve and fill SMS code
                if sms_input_field and sms_input_field.is_visible():
                    print("\n" + "="*60)
                    print("📱 SMS CODE REQUIRED")
                    print("="*60)
                    
                    # If party_id not provided, prompt for it to enable automation
                    if party_id is None:
                        print("\n💡 To enable automatic SMS code retrieval, enter your Party ID.")
                        print("   (Press Enter to skip automation and enter code manually)")
                        party_id_input = input("Party ID (or press Enter for manual entry): ").strip()
                        
                        if party_id_input and party_id_input.isdigit():
                            party_id = int(party_id_input)
                            print(f"✅ Using Party ID: {party_id} for automatic retrieval")
                        else:
                            print("⚠️  No Party ID provided, will use manual entry")
                    
                    if party_id:
                        # Automated SMS OTP retrieval
                        print(f"\n🔍 Automatically retrieving SMS OTP for party ID: {party_id}")
                        print("   Waiting for SMS to arrive...")
                        try:
                            sms_code = wait_for_sms_otp(
                                api_request_context,
                                party_id,
                                timeout_seconds=60,
                                time_range_minutes=5
                            )
                            print(f"\n📝 Filling SMS code: {sms_code}")
                            sms_input_field.fill(sms_code)
                            sms_code_filled = True
                            print("✅ SMS code filled automatically")
                            page.wait_for_timeout(200)  # Reduced from 500ms
                        except Exception as e:
                            print(f"\n⚠️  Failed to retrieve SMS OTP automatically: {e}")
                            import traceback
                            print("\n📋 Full error details:")
                            traceback.print_exc()
                            print("\n   Falling back to manual entry...")
                            # Fall back to manual entry
                            while True:
                                sms_code = input("SMS Code (6 digits): ").strip()
                                if len(sms_code) == 6 and sms_code.isdigit():
                                    break
                                print("⚠️  Please enter exactly 6 digits")
                            sms_input_field.fill(sms_code)
                            sms_code_filled = True
                            print("✅ SMS code filled manually")
                            page.wait_for_timeout(500)
                    else:
                        # Manual entry (no party_id provided)
                        print("\nPlease enter the 6-digit SMS code:")
                        while True:
                            sms_code = input("SMS Code (6 digits): ").strip()
                            if len(sms_code) == 6 and sms_code.isdigit():
                                break
                            print("⚠️  Please enter exactly 6 digits")
                        
                        print(f"\n📝 Filling SMS code: {sms_code}")
                        try:
                            sms_input_field.fill(sms_code)
                            sms_code_filled = True
                            print("✅ SMS code filled")
                            page.wait_for_timeout(200)  # Reduced from 500ms
                        except Exception as e:
                            print(f"⚠️  Error filling SMS code: {e}")
                else:
                    print("⚠️  Could not find SMS code input field")
                    
            except Exception as e:
                print(f"⚠️  Error handling SMS code: {e}")
                import traceback
                traceback.print_exc()
            
            # Variables to capture redirect URL
            redirect_url = None
            redirect_captured = False
            
            # After SMS code is filled, click the confirm button
            if sms_code_filled:
                print("\n🔍 Looking for confirm button after SMS code entry...")
                page.wait_for_timeout(200)  # Reduced from 500ms
                                
                confirm_clicked = False
                confirm_button_selectors = [
                    'button:has-text("Confirm")',
                    'button:has-text("Potvrdit")',  # Czech: Potvrdit = Confirm
                    'button:has-text("Submit")',
                    'button:has-text("Odeslat")',  # Czech: Odeslat = Submit
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button.primary',
                    'button.btn-primary',
                    'button[class*="confirm"]',
                    'button[class*="submit"]',
                ]
                
                for selector in confirm_button_selectors:
                    try:
                        confirm_button = page.locator(selector).first
                        if confirm_button.is_visible(timeout=2000):
                            print(f"✅ Found confirm button with selector: {selector}")
                            button_text = confirm_button.text_content() if confirm_button else "N/A"
                            print(f"   Button text: {button_text}")
                            confirm_button.click()
                            confirm_clicked = True
                            print("✅ Confirm button clicked")
                            break
                    except:
                        continue
                
                if not confirm_clicked:
                    print("⚠️  Could not find confirm button. Trying Enter key...")
                    try:
                        page.keyboard.press("Enter")
                        confirm_clicked = True
                        print("✅ Pressed Enter key")
                    except Exception as e:
                        print(f"⚠️  Could not confirm: {e}")
                
                # Wait for login to complete
                if confirm_clicked:
                    print("\n⏳ Waiting for login to complete...")
                    page.wait_for_load_state("networkidle", timeout=10000)
                    print(f"📍 Current URL after login: {page.url}\n")
                    print("✅ Login process completed!")
                    print("💡 Browser will remain open for you to interact with the application.")
                    print("   Close the browser window manually when done, or press Enter here to close it.")
                    
                    # Wait for user input before closing (or keep open if stdin unavailable)
                    try:
                        input("\nPress Enter to close the browser (or close the browser window manually)...")
                    except (EOFError, KeyboardInterrupt):
                        # Handle case where stdin is not available (e.g., when run from GUI)
                        # Keep browser open - user can close it manually
                        print("\n   Browser will remain open. Close the browser window manually when done.")
                        # Wait indefinitely (or until browser is closed manually)
                        try:
                            # Check if browser is still connected every 5 seconds
                            while browser.is_connected():
                                page.wait_for_timeout(5000)
                        except:
                            # Browser was closed manually
                            pass
            
        except Exception as e:
            print(f"\n❌ Login failed: {str(e)}")
            import traceback
            traceback.print_exc()
            print("\n   Closing browser in 3 seconds...")
            page.wait_for_timeout(3000)  # Wait 3 seconds before closing
        
        finally:
            api_request_context.dispose()
            # Close browser only if it's still open and user requested it
            try:
                if browser.is_connected():
                    browser.close()
                    print("✅ Browser closed")
            except:
                # Browser already closed or error
                pass


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
    parser = argparse.ArgumentParser(description='Internet Banking Login Flow')
    parser.add_argument('--user-id', type=str, help='User ID (party_id) from context (GUI)')
    args = parser.parse_args()
    
    try:
        # If user_id provided (from GUI), use it
        if args.user_id:
            test_login_endpoint(user_id=args.user_id)
        else:
            # Otherwise, use default config (console mode)
            # Load party_id from default_auth_config.json if available
            auth_config = load_default_auth_config()
            party_id = None
            if auth_config and auth_config.get("partyId"):
                try:
                    party_id = int(auth_config.get("partyId"))
                except:
                    pass
            
            test_login_endpoint(user_id=str(party_id) if party_id else None)
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}"
        print(error_msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

