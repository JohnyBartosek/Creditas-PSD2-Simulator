"""
Access Token Helper
Parses JWT access tokens and extracts useful information
"""

import json
import base64
from datetime import datetime, timezone
from typing import Dict, Optional, Any


def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token payload without verification
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload as dictionary, or None if invalid
    """
    try:
        # JWT has 3 parts separated by dots: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError('Invalid JWT format: expected 3 parts separated by dots')
        
        # Decode payload (middle part)
        payload = parts[1]
        
        # Add padding if needed (base64url may not have padding)
        padding = len(payload) % 4
        if padding:
            payload += '=' * (4 - padding)
        
        # Base64 URL decode
        decoded_bytes = base64.urlsafe_b64decode(payload)
        decoded_str = decoded_bytes.decode('utf-8')
        
        return json.loads(decoded_str)
    except Exception as e:
        print(f"❌ Error decoding JWT: {e}")
        return None


def decode_jwt_header(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token header without verification
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded header as dictionary, or None if invalid
    """
    try:
        # JWT has 3 parts separated by dots: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError('Invalid JWT format: expected 3 parts separated by dots')
        
        # Decode header (first part)
        header = parts[0]
        
        # Add padding if needed
        padding = len(header) % 4
        if padding:
            header += '=' * (4 - padding)
        
        # Base64 URL decode
        decoded_bytes = base64.urlsafe_b64decode(header)
        decoded_str = decoded_bytes.decode('utf-8')
        
        return json.loads(decoded_str)
    except Exception as e:
        print(f"❌ Error decoding JWT header: {e}")
        return None


def parse_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Parse access token and return all decoded information
    
    Args:
        token: JWT access token string
        
    Returns:
        Dictionary with header and payload, or None if invalid
    """
    if not token:
        return None
    
    header = decode_jwt_header(token)
    payload = decode_jwt_payload(token)
    
    if not header or not payload:
        return None
    
    return {
        "header": header,
        "payload": payload,
        "raw_token": token
    }


def get_user_from_token(token: str) -> Optional[int]:
    """
    Extract user/party_id (sub claim) from access token
    
    Args:
        token: JWT access token string
        
    Returns:
        User/party_id as integer, or None if not found
    """
    payload = decode_jwt_payload(token)
    if not payload:
        return None
    
    sub = payload.get("sub")
    if sub:
        try:
            return int(sub)
        except (ValueError, TypeError):
            return None
    return None


def get_client_id_from_token(token: str) -> Optional[str]:
    """
    Extract client_id (azp claim) from access token
    
    Args:
        token: JWT access token string
        
    Returns:
        Client ID string, or None if not found
    """
    payload = decode_jwt_payload(token)
    if not payload:
        return None
    
    # Try azp (authorized party) first, then client_id
    client_id = payload.get("azp") or payload.get("client_id")
    return client_id


def get_scope_from_token(token: str) -> Optional[str]:
    """
    Extract scope from access token
    
    Args:
        token: JWT access token string
        
    Returns:
        Scope string, or None if not found
    """
    payload = decode_jwt_payload(token)
    if not payload:
        return None
    
    return payload.get("scope")


def get_expiration_from_token(token: str) -> Optional[datetime]:
    """
    Extract expiration time from access token
    
    Args:
        token: JWT access token string
        
    Returns:
        Expiration datetime, or None if not found
    """
    payload = decode_jwt_payload(token)
    if not payload:
        return None
    
    exp = payload.get("exp")
    if exp:
        try:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def is_token_expired(token: str) -> bool:
    """
    Check if access token is expired
    
    Args:
        token: JWT access token string
        
    Returns:
        True if expired, False if not expired or if expiration cannot be determined
    """
    exp_datetime = get_expiration_from_token(token)
    if not exp_datetime:
        return False  # Can't determine, assume not expired
    
    if exp_datetime.tzinfo is None:
        exp_datetime = exp_datetime.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= exp_datetime


def get_issued_at_from_token(token: str) -> Optional[datetime]:
    """
    Extract issued at time from access token
    
    Args:
        token: JWT access token string
        
    Returns:
        Issued at datetime, or None if not found
    """
    payload = decode_jwt_payload(token)
    if not payload:
        return None
    
    iat = payload.get("iat")
    if iat:
        try:
            return datetime.fromtimestamp(iat, tz=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def get_token_info(token: str) -> Dict[str, Any]:
    """
    Get comprehensive information about the access token
    
    Args:
        token: JWT access token string
        
    Returns:
        Dictionary with token information
    """
    parsed = parse_access_token(token)
    if not parsed:
        return {"error": "Invalid token"}
    
    payload = parsed["payload"]
    header = parsed["header"]
    
    exp_datetime = get_expiration_from_token(token)
    iat_datetime = get_issued_at_from_token(token)
    
    info = {
        "header": header,
        "user": get_user_from_token(token),
        "client_id": get_client_id_from_token(token),
        "scope": get_scope_from_token(token),
        "issuer": payload.get("iss"),
        "audience": payload.get("aud"),
        "name": payload.get("name"),
        "client_org_id": payload.get("client_org_id"),
        "jti": payload.get("jti"),  # JWT ID
        "exp": payload.get("exp"),
        "exp_datetime": exp_datetime.isoformat() if exp_datetime else None,
        "expired": is_token_expired(token),
        "iat": payload.get("iat"),
        "iat_datetime": iat_datetime.isoformat() if iat_datetime else None,
        "nbf": payload.get("nbf"),  # Not before
        "algorithm": header.get("alg"),
        "key_id": header.get("kid"),
    }
    
    # Calculate time until expiration if not expired
    if exp_datetime and not is_token_expired(token):
        if exp_datetime.tzinfo is None:
            exp_datetime = exp_datetime.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        time_until_exp = exp_datetime - now_utc
        info["expires_in_seconds"] = int(time_until_exp.total_seconds())
        info["expires_in_minutes"] = round(time_until_exp.total_seconds() / 60, 2)
    
    return info


def print_token_info(token: str):
    """
    Pretty print token information
    
    Args:
        token: JWT access token string
    """
    info = get_token_info(token)
    
    if "error" in info:
        print(f"❌ {info['error']}")
        return
    
    print("="*60)
    print("ACCESS TOKEN INFORMATION")
    print("="*60)
    print()
    
    if info.get("user"):
        print(f"👤 User (Party ID): {info['user']}")
    
    if info.get("client_id"):
        print(f"🔑 Client ID: {info['client_id']}")
    
    if info.get("scope"):
        print(f"📋 Scope: {info['scope']}")
    
    if info.get("issuer"):
        print(f"🏢 Issuer: {info['issuer']}")
    
    if info.get("audience"):
        aud = info['audience']
        if isinstance(aud, list):
            print(f"🎯 Audience: {', '.join(aud)}")
        else:
            print(f"🎯 Audience: {aud}")
    
    if info.get("name"):
        print(f"📛 Name: {info['name']}")
    
    if info.get("client_org_id"):
        print(f"🏛️  Client Org ID: {info['client_org_id']}")
    
    if info.get("jti"):
        print(f"🆔 JWT ID: {info['jti']}")
    
    print()
    print("⏰ Time Information:")
    if info.get("iat_datetime"):
        print(f"   Issued At: {info['iat_datetime']}")
    
    if info.get("exp_datetime"):
        print(f"   Expires At: {info['exp_datetime']}")
        if info.get("expired"):
            print(f"   ⚠️  Status: EXPIRED")
        else:
            print(f"   ✅ Status: Valid")
            if info.get("expires_in_seconds"):
                print(f"   ⏳ Time Remaining: {info['expires_in_seconds']} seconds ({info.get('expires_in_minutes', 0)} minutes)")
    
    if info.get("nbf"):
        nbf_datetime = datetime.fromtimestamp(info['nbf'], tz=timezone.utc)
        print(f"   Not Before: {nbf_datetime.isoformat()}")
    
    print()
    print("🔐 Token Details:")
    if info.get("algorithm"):
        print(f"   Algorithm: {info['algorithm']}")
    
    if info.get("key_id"):
        print(f"   Key ID: {info['key_id']}")
    
    print()
    print("="*60)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print_token_info(token)
    else:
        print("Usage: python access_token_helper.py <access_token>")
        print("\nOr import and use in your code:")
        print("  from access_token_helper import parse_access_token, get_token_info, print_token_info")
        print("  token_info = get_token_info(access_token)")
        print("  print_token_info(access_token)")

