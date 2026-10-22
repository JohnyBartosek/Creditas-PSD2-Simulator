"""
Interactive Environment Switcher
Allows users to switch between environments (ITG, TST, PRE, PROD) interactively
"""

import sys
from pathlib import Path

# Get the project root directory (parent of Helpers directory)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Add project root to Python path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from Helpers.environment_config import (
    get_current_environment,
    load_environment_config,
    set_environment,
)


def _prompt_choice(prompt: str, options: list, default_index: int = 0) -> str:
    """
    Prompt user to select from a list of options
    
    Args:
        prompt: Prompt message to display
        options: List of option strings
        default_index: Index of default option (0-based)
    
    Returns:
        Selected option string
    """
    while True:
        print(f"\n{prompt}")
        for i, opt in enumerate(options, start=1):
            default_marker = " (default)" if (i - 1) == default_index else ""
            print(f"  {i}. {opt}{default_marker}")
        try:
            raw = input("> ").strip()
        except EOFError:
            # Non-interactive execution: fall back to default
            print("\nWARNING: No interactive input available; using default.")
            return options[default_index]
        if raw == "":
            return options[default_index]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print("Invalid selection, try again.")


def switch_environment_interactive() -> int:
    """
    Interactive environment switching
    
    Returns:
        0 on success, 1 on error, 2 if not in interactive terminal
    """
    if not sys.stdin.isatty():
        print("ERROR: Interactive mode requires a real terminal (TTY).")
        print("Run this in a console.")
        return 2
    
    try:
        # Load environment configuration
        cfg = load_environment_config()
        
        # Logical environment order: ITG → TST → PRE → PROD
        ENV_ORDER = ["ITG", "TST", "PRE", "PROD"]
        all_envs = list((cfg.get("environments") or {}).keys())
        
        # Sort by logical order, with any unknown environments at the end
        envs = sorted(
            all_envs,
            key=lambda e: (ENV_ORDER.index(e) if e in ENV_ORDER else 999, e)
        )
        
        if not envs:
            print("ERROR: No environments found in configuration.")
            return 1
        
        # Get current environment
        current_env = get_current_environment()
        default_env_idx = envs.index(current_env) if current_env in envs else 0
        
        # Display current environment
        print("=" * 60)
        print("ENVIRONMENT SWITCHER")
        print("=" * 60)
        print(f"\nCurrent environment: {current_env}")
        print(f"Config file: Configurations/environment_config.json")
        
        # Prompt for environment selection
        selected_env = _prompt_choice(
            "Select environment to switch to:",
            envs,
            default_index=default_env_idx
        )
        
        # Check if already selected
        if selected_env == current_env:
            print(f"\n✅ Already using environment: {selected_env}")
            print("   No change needed.")
            return 0
        
        # Switch environment
        set_environment(selected_env)
        
        # Verify switch
        new_env = get_current_environment()
        if new_env == selected_env:
            print(f"\n✅ Successfully switched to environment: {selected_env}")
            print(f"   Database directory: Database/{selected_env}/")
            return 0
        else:
            print(f"\n⚠️  Warning: Environment switch may have failed.")
            print(f"   Expected: {selected_env}, Got: {new_env}")
            return 1
            
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        return 1
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def show_current_environment() -> None:
    """Display current environment information"""
    try:
        current_env = get_current_environment()
        cfg = load_environment_config()
        env_config = cfg.get("environments", {}).get(current_env, {})
        
        print("=" * 60)
        print("CURRENT ENVIRONMENT")
        print("=" * 60)
        print(f"\nEnvironment: {current_env}")
        print(f"Database directory: Database/{current_env}/")
        
        # Show some key URLs
        if env_config:
            print("\nKey URLs:")
            if "oauth" in env_config:
                oauth = env_config["oauth"]
                if "authorize_url" in oauth:
                    print(f"  OAuth Authorize: {oauth['authorize_url']}")
                if "token_url" in oauth:
                    print(f"  OAuth Token: {oauth['token_url']}")
            if "internet_banking" in env_config:
                ib = env_config["internet_banking"]
                if "login_url" in ib:
                    print(f"  IB Login: {ib['login_url']}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error displaying environment: {e}")


if __name__ == "__main__":
    # Fix Windows console encoding for Unicode characters
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description='Switch between environments (ITG, TST, PRE, PROD)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Helpers/switch_environment.py          # Interactive mode
  python Helpers/switch_environment.py --show  # Show current environment only
  python Helpers/switch_environment.py --set TST  # Set environment to TST
        """
    )
    parser.add_argument(
        '--show',
        action='store_true',
        help='Show current environment information only (no switching)'
    )
    parser.add_argument(
        '--set',
        type=str,
        metavar='ENV',
        help='Set environment directly (ITG, TST, PRE, or PROD)'
    )
    args = parser.parse_args()
    
    # Handle different modes
    if args.show:
        show_current_environment()
        sys.exit(0)
    elif args.set:
        # Direct set mode
        try:
            env_upper = args.set.upper()
            if env_upper not in ["ITG", "TST", "PRE", "PROD"]:
                print(f"❌ Invalid environment: {args.set}")
                print("   Must be one of: ITG, TST, PRE, PROD")
                sys.exit(1)
            
            current_env = get_current_environment()
            if env_upper == current_env:
                print(f"✅ Already using environment: {env_upper}")
                sys.exit(0)
            
            set_environment(env_upper)
            new_env = get_current_environment()
            if new_env == env_upper:
                print(f"✅ Successfully switched to environment: {env_upper}")
                sys.exit(0)
            else:
                print(f"⚠️  Warning: Environment switch may have failed.")
                print(f"   Expected: {env_upper}, Got: {new_env}")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
    else:
        # Interactive mode
        exit_code = switch_environment_interactive()
        sys.exit(exit_code)

