"""
Environment Configuration Helper
Loads and provides access to environment-specific URLs
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Get project root
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Configuration file path
ENV_CONFIG_FILE = PROJECT_ROOT / "Configurations" / "environment_config.json"

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None
_current_environment: Optional[str] = None


def load_environment_config() -> Dict[str, Any]:
    """Load environment configuration from JSON file"""
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    if not ENV_CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Environment configuration file not found: {ENV_CONFIG_FILE}\n"
            "Please create Configurations/environment_config.json"
        )
    
    with open(ENV_CONFIG_FILE, 'r', encoding='utf-8') as f:
        _config_cache = json.load(f)
    
    return _config_cache


def get_current_environment() -> str:
    """Get the current environment (ITG, TST, PRE, PROD)"""
    global _current_environment
    
    if _current_environment is not None:
        return _current_environment
    
    config = load_environment_config()
    _current_environment = config.get("current_environment", "ITG").upper()
    
    # Also check environment variable (can override config file)
    env_var = os.environ.get("PSD2_ENVIRONMENT", "").upper()
    if env_var in ["ITG", "TST", "PRE", "PROD"]:
        _current_environment = env_var
    
    return _current_environment


def set_environment(environment: str) -> None:
    """Set the current environment (ITG, TST, PRE, PROD)"""
    global _current_environment, _config_cache
    
    env_upper = environment.upper()
    if env_upper not in ["ITG", "TST", "PRE", "PROD"]:
        raise ValueError(f"Invalid environment: {environment}. Must be one of: ITG, TST, PRE, PROD")
    
    _current_environment = env_upper
    
    # Update config file
    config = load_environment_config()
    config["current_environment"] = env_upper
    
    with open(ENV_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # Clear cache to force reload
    _config_cache = config


def get_environment_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """Get configuration for a specific environment (defaults to current)"""
    config = load_environment_config()
    
    if environment is None:
        environment = get_current_environment()
    else:
        environment = environment.upper()
    
    if environment not in config.get("environments", {}):
        raise ValueError(f"Environment '{environment}' not found in configuration")
    
    return config["environments"][environment]


def get_url(category: str, key: str, environment: Optional[str] = None) -> str:
    """
    Get a URL from the environment configuration
    
    Args:
        category: Category of URL (e.g., 'oauth', 'registration', 'consents', 'accounts', 'obo', 'internet_banking')
        key: Key within the category (e.g., 'authorize_url', 'token_url', 'base_url')
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        The URL string
    
    Examples:
        get_url('oauth', 'authorize_url')
        get_url('registration', 'get_url_template', 'TST')
    """
    env_config = get_environment_config(environment)
    
    if category not in env_config:
        raise ValueError(f"Category '{category}' not found in environment configuration")
    
    if key not in env_config[category]:
        raise ValueError(f"Key '{key}' not found in category '{category}'")
    
    return env_config[category][key]


# Convenience functions for common URLs
def get_oauth_authorize_url(environment: Optional[str] = None) -> str:
    """Get OAuth2 authorization URL"""
    return get_url('oauth', 'authorize_url', environment)


def get_oauth_token_url(environment: Optional[str] = None) -> str:
    """Get OAuth2 token URL"""
    return get_url('oauth', 'token_url', environment)


def get_oauth_introspect_url(environment: Optional[str] = None) -> str:
    """Get OAuth2 token introspection URL"""
    return get_url('oauth', 'introspect_url', environment)


def get_oauth_revoke_url(environment: Optional[str] = None) -> str:
    """Get OAuth2 token revocation URL"""
    return get_url('oauth', 'revoke_url', environment)


def get_registration_post_url(environment: Optional[str] = None) -> str:
    """Get registration POST URL"""
    return get_url('registration', 'post_url', environment)


def get_registration_get_url(client_id: str, environment: Optional[str] = None) -> str:
    """Get registration GET URL for a specific client_id"""
    template = get_url('registration', 'get_url_template', environment)
    return template.format(client_id=client_id)


def get_registration_delete_url(client_id: str, environment: Optional[str] = None) -> str:
    """Get registration DELETE URL for a specific client_id"""
    template = get_url('registration', 'delete_url_template', environment)
    return template.format(client_id=client_id)


def get_consents_url(environment: Optional[str] = None) -> str:
    """Get consents base URL"""
    return get_url('consents', 'base_url', environment)


def get_show_invalid_consents(environment: Optional[str] = None) -> bool:
    """
    Get whether to show invalid consents (where validTo < now) for a specific environment.
    Defaults to False (only show valid consents).
    
    Args:
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Boolean indicating whether to show invalid consents
    """
    env_config = get_environment_config(environment)
    consents_config = env_config.get('consents', {})
    return consents_config.get('show_invalid_consents', False)


def get_accounts_list_url(environment: Optional[str] = None) -> str:
    """Get accounts list URL"""
    return get_url('accounts', 'list_url', environment)


def get_obo_smc_base_url(environment: Optional[str] = None) -> str:
    """Get OBO SMC base URL"""
    return get_url('obo', 'smc_base_url', environment)


def get_ib_login_url(environment: Optional[str] = None) -> str:
    """Get Internet Banking login URL"""
    return get_url('internet_banking', 'login_url', environment)


def get_kibana_settings(environment: Optional[str] = None) -> Dict[str, str]:
    """Discover URL, optional data view id, and the default time range."""
    env_config = get_environment_config(environment)
    kibana = env_config.get("kibana") or {}
    time_from = str(kibana.get("time_from") or "now-24h").strip() or "now-24h"
    return {
        "discover_url": str(kibana.get("discover_url") or "").strip(),
        "data_view": str(kibana.get("data_view") or "").strip(),
        "time_from": time_from,
    }


def get_database_dir(environment: Optional[str] = None) -> Path:
    """
    Get the database directory path for a specific environment
    
    Args:
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Path object pointing to Database/{ENVIRONMENT}/ directory
    
    Examples:
        get_database_dir()  # Returns Database/ITG/ (or current env)
        get_database_dir('TST')  # Returns Database/TST/
    """
    if environment is None:
        environment = get_current_environment()
    else:
        environment = environment.upper()
    
    db_dir = PROJECT_ROOT / "Database" / environment
    # Ensure directory exists
    db_dir.mkdir(parents=True, exist_ok=True)
    
    return db_dir


def get_database_file(filename: str, environment: Optional[str] = None) -> Path:
    """
    Get the full path to a database file for a specific environment
    
    Args:
        filename: Name of the database file (e.g., 'tpp_registrations.json')
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Path object pointing to Database/{ENVIRONMENT}/{filename}
    
    Examples:
        get_database_file('tpp_registrations.json')  # Returns Database/ITG/tpp_registrations.json
        get_database_file('tpp_tokens.json', 'TST')  # Returns Database/TST/tpp_tokens.json
    """
    db_dir = get_database_dir(environment)
    return db_dir / filename


def get_configurations_dir(environment: Optional[str] = None) -> Path:
    """
    Get the configurations directory path for a specific environment
    
    Args:
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Path object pointing to Configurations/{ENVIRONMENT}/ directory
    
    Examples:
        get_configurations_dir()  # Returns Configurations/ITG/ (or current env)
        get_configurations_dir('TST')  # Returns Configurations/TST/
    """
    if environment is None:
        environment = get_current_environment()
    else:
        environment = environment.upper()
    
    config_dir = PROJECT_ROOT / "Configurations" / environment
    # Ensure directory exists
    config_dir.mkdir(parents=True, exist_ok=True)
    
    return config_dir


def get_entra_config_file(environment: Optional[str] = None) -> Path:
    """
    Get the full path to the Entra ID configuration file for a specific environment
    
    Args:
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Path object pointing to Configurations/{ENVIRONMENT}/entra_config.json
    
    Examples:
        get_entra_config_file()  # Returns Configurations/ITG/entra_config.json
        get_entra_config_file('TST')  # Returns Configurations/TST/entra_config.json
    """
    config_dir = get_configurations_dir(environment)
    return config_dir / "entra_config.json"


def get_db_config_file(environment: Optional[str] = None) -> Path:
    """Oracle credentials for the Datasheets tool: Configurations/{ENV}/db_config.json."""
    return get_configurations_dir(environment) / "db_config.json"


def db_config_display_path(environment: Optional[str] = None) -> str:
    """Path of the database config relative to the project root."""
    path = get_db_config_file(environment)
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def load_db_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Load the Oracle connection for an environment.

    Read from disk on every call so a password filled into the file is picked up
    without restarting the app. The password stays out of environment_config.json,
    which is rewritten from memory when the environment changes.
    """
    path = get_db_config_file(environment)
    display = db_config_display_path(environment)
    empty: Dict[str, Any] = {
        "host": "",
        "port": "",
        "database": "",
        "username": "",
        "password": "",
        "configured": False,
        "config_path": display,
    }
    if not path.exists():
        return empty

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    port = data.get("port", "")
    host = str(data.get("host") or "").strip()
    database = str(data.get("database") or "").strip()
    username = str(data.get("username") or "").strip()
    return {
        "host": host,
        "port": "" if port is None else str(port).strip(),
        "database": database,
        "username": username,
        "password": str(data.get("password") or ""),
        "configured": bool(host or database or username),
        "config_path": display,
    }


def get_token_config_file(environment: Optional[str] = None) -> Path:
    """
    Get the full path to the token configuration file for a specific environment
    
    Args:
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Path object pointing to Configurations/{ENVIRONMENT}/token_config.json
    
    Examples:
        get_token_config_file()  # Returns Configurations/ITG/token_config.json
        get_token_config_file('TST')  # Returns Configurations/TST/token_config.json
    """
    config_dir = get_configurations_dir(environment)
    return config_dir / "token_config.json"


def load_token_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Load token configuration for a specific environment
    
    Args:
        environment: Optional environment override (defaults to current environment)
    
    Returns:
        Dictionary with token configuration:
        - access_token_expiration_seconds: Access token expiration time in seconds
        - refresh_token_expiration_seconds: Refresh token expiration time in seconds
        - authorization_code_expiration_seconds: Authorization code expiration time in seconds
    
    Examples:
        config = load_token_config()  # Loads for current environment
        config = load_token_config('TST')  # Loads for TST environment
    """
    config_path = get_token_config_file(environment)
    
    if not config_path.exists():
        # Return default values if config file doesn't exist
        return {
            "access_token_expiration_seconds": 300,  # 5 minutes default
            "refresh_token_expiration_seconds": 3600,  # 60 minutes default
            "authorization_code_expiration_seconds": 300  # 5 minutes default
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Validate and provide defaults for missing fields
    return {
        "access_token_expiration_seconds": config.get("access_token_expiration_seconds", 300),
        "refresh_token_expiration_seconds": config.get("refresh_token_expiration_seconds", 3600),
        "authorization_code_expiration_seconds": config.get("authorization_code_expiration_seconds", 300)
    }

