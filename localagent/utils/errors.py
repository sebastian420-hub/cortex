"""Error handling and recovery utilities"""

import time
import logging
from typing import Callable, TypeVar, Optional, Any, Dict
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorType:
    """Error type constants for standardized error responses"""
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    NETWORK = "network"
    SECURITY = "security"


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {max_retries} attempts failed")
            
            if last_exception:
                raise last_exception
            
            raise RuntimeError("Unexpected error in retry logic")
        
        return wrapper
    return decorator


class AgentError(Exception):
    """Base exception for agent errors"""
    pass


class ToolExecutionError(AgentError):
    """Error during tool execution"""
    pass


class ModelError(AgentError):
    """Error communicating with the model"""
    pass


def create_error_response(
    error_message: str,
    error_type: str,
    context: Optional[Dict[str, Any]] = None,
    retryable: bool = False
) -> Dict[str, Any]:
    """
    Create standardized error response.
    
    Args:
        error_message: Human-readable error message
        error_type: Type of error (use ErrorType constants)
        context: Optional additional context about the error
        retryable: Whether this error can be retried (default: False)
        
    Returns:
        Standardized error response dictionary
    """
    result: Dict[str, Any] = {
        "success": False,
        "error": error_message,
        "error_type": error_type,
        "retryable": retryable
    }
    if context:
        result["error_context"] = context
    return result


def create_permission_denial(
    reason: str,
    action: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create standardized permission denial response.
    Distinct from errors - indicates user/system blocked action.
    
    Args:
        reason: Why permission was denied
        action: What action was attempted
        context: Optional additional context
        
    Returns:
        Standardized permission denial response
    """
    result: Dict[str, Any] = {
        "success": False,
        "permission_denied": True,
        "error_type": ErrorType.PERMISSION,
        "reason": reason,
        "action": action,
        "retryable": False
    }
    if context:
        result["error_context"] = context
    return result


def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create standardized success response.
    
    Args:
        data: Additional data to include in success response
        
    Returns:
        Standardized success response dictionary with success=True
    """
    return {"success": True, **data}

