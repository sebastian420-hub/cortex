"""UTF-8 encoding utilities for sanitizing strings."""

import json
from typing import Any, Dict, List, Union


def sanitize_string(s: str) -> str:
    """
    Remove surrogate characters and other invalid UTF-8 characters from a string.
    
    Uses encode/decode with 'ignore' error handler to drop characters that
    cannot be encoded as UTF-8 (including surrogate pairs).
    
    Args:
        s: Input string
        
    Returns:
        Sanitized string
    """
    # Encode to UTF-8 ignoring characters that can't be encoded, then decode back
    return s.encode('utf-8', 'ignore').decode('utf-8')


def sanitize_object(obj: Any) -> Any:
    """
    Recursively sanitize strings in an object (dict, list, tuple, etc.).
    
    Args:
        obj: Any Python object
        
    Returns:
        Sanitized object with all strings cleaned
    """
    if isinstance(obj, str):
        return sanitize_string(obj)
    elif isinstance(obj, dict):
        return {k: sanitize_object(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_object(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(sanitize_object(v) for v in obj)
    else:
        return obj


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely serialize object to JSON, ensuring all strings are UTF-8 clean.
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments to json.dumps
        
    Returns:
        JSON string
    """
    # Ensure ensure_ascii=False is default to preserve Unicode characters
    kwargs.setdefault('ensure_ascii', False)
    # Sanitize object before serialization
    sanitized = sanitize_object(obj)
    return json.dumps(sanitized, **kwargs)