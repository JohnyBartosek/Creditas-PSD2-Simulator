"""
File Lock Helper
Provides thread-safe file operations with file locking to prevent concurrent write conflicts
"""

import json
import os
import time
import sys
from pathlib import Path
from typing import Any, Optional, Callable

# Platform-specific file locking
if sys.platform == 'win32':
    import msvcrt
    def lock_file(file_handle):
        """Lock file on Windows"""
        msvcrt.locking(file_handle.fileno(), msvcrt.LK_LOCK, 1)
    
    def unlock_file(file_handle):
        """Unlock file on Windows"""
        try:
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
        except:
            pass
else:
    import fcntl
    def lock_file(file_handle):
        """Lock file on Unix/Linux/Mac"""
        fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX)
    
    def unlock_file(file_handle):
        """Unlock file on Unix/Linux/Mac"""
        try:
            fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
        except:
            pass


def safe_read_json(filepath: str, max_retries: int = 5, retry_delay: float = 0.1) -> Optional[Any]:
    """
    Safely read JSON file with file locking and retry logic
    
    Args:
        filepath: Path to JSON file
        max_retries: Maximum number of retry attempts if file is locked
        retry_delay: Delay between retries in seconds
    
    Returns:
        Parsed JSON data or None if file doesn't exist or can't be read
    """
    if not os.path.exists(filepath):
        return None
    
    for attempt in range(max_retries):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lock_file(f)
                try:
                    data = json.load(f)
                    return data
                finally:
                    unlock_file(f)
        except (IOError, OSError, json.JSONDecodeError) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                print(f"⚠️  Error reading {filepath} after {max_retries} attempts: {e}")
                return None
    
    return None


def safe_write_json(filepath: str, data: Any, max_retries: int = 5, retry_delay: float = 0.1) -> bool:
    """
    Safely write JSON file with file locking and retry logic
    Uses atomic write: writes to temp file first, then renames
    
    Args:
        filepath: Path to JSON file
        data: Data to write (will be JSON serialized)
        max_retries: Maximum number of retry attempts if file is locked
        retry_delay: Delay between retries in seconds
    
    Returns:
        True if successful, False otherwise
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Use atomic write: write to temp file, then rename
    temp_filepath = f"{filepath}.tmp"
    
    for attempt in range(max_retries):
        try:
            # Write to temporary file first
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                lock_file(f)
                try:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk
                finally:
                    unlock_file(f)
            
            # Atomic rename (works on most filesystems)
            if sys.platform == 'win32':
                # On Windows, need to remove target first if it exists
                if os.path.exists(filepath):
                    os.remove(filepath)
            os.rename(temp_filepath, filepath)
            return True
            
        except (IOError, OSError) as e:
            # Clean up temp file if it exists
            try:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                print(f"⚠️  Error writing {filepath} after {max_retries} attempts: {e}")
                return False
    
    return False


def safe_update_json(
    filepath: str,
    update_func: Callable[[Any], Any],
    default_value: Any = None,
    max_retries: int = 5,
    retry_delay: float = 0.1
) -> bool:
    """
    Safely update JSON file by reading, modifying, and writing back
    Uses file locking to prevent concurrent modifications
    
    Args:
        filepath: Path to JSON file
        update_func: Function that takes current data and returns updated data
        default_value: Default value if file doesn't exist
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        True if successful, False otherwise
    
    Example:
        def add_entry(data):
            if "items" not in data:
                data["items"] = []
            data["items"].append({"id": 1})
            return data
        
        safe_update_json("data.json", add_entry, default_value={"items": []})
    """
    for attempt in range(max_retries):
        try:
            # Read current data
            current_data = safe_read_json(filepath, max_retries=1)
            if current_data is None:
                current_data = default_value if default_value is not None else {}
            
            # Apply update function
            updated_data = update_func(current_data)
            
            # Write back
            return safe_write_json(filepath, updated_data, max_retries=1)
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                print(f"⚠️  Error updating {filepath} after {max_retries} attempts: {e}")
                return False
    
    return False

