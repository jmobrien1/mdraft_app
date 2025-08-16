"""
Reliability engineering utilities for external service calls.

This module provides:
- Standardized error enums for external service failures
- Retry decorators using tenacity with jittered backoff
- Lightweight in-process circuit breakers
- Timeout handling for all external calls
"""

import time
import random
import logging
from typing import Dict, Any, Optional, Callable, TypeVar, Union
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
import threading

try:
    from tenacity import (
        retry, stop_after_attempt, wait_exponential, 
        retry_if_exception_type, before_sleep_log
    )
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    # Fallback retry implementation
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    stop_after_attempt = lambda x: None
    wait_exponential = lambda *args, **kwargs: None
    retry_if_exception_type = lambda *args: None
    before_sleep_log = lambda *args, **kwargs: None

from ..config import get_config

logger = logging.getLogger(__name__)

# Type variable for generic functions
T = TypeVar('T')


class ExternalServiceError(Enum):
    """Standardized error types for external service failures."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_DENIED = "permission_denied"
    NOT_FOUND = "not_found"
    BAD_REQUEST = "bad_request"
    SERVER_ERROR = "server_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ReliabilityError(Exception):
    """Standardized error for external service failures."""
    error_type: ExternalServiceError
    service_name: str
    endpoint: str
    original_error: Optional[Exception] = None
    retry_count: int = 0
    
    def __str__(self) -> str:
        base_msg = f"{self.service_name} ({self.endpoint}): {self.error_type.value}"
        if self.retry_count > 0:
            base_msg += f" (retried {self.retry_count} times)"
        if self.original_error:
            # Only include safe parts of the original error
            safe_msg = str(self.original_error).replace('\n', ' ')[:100]
            base_msg += f" - {safe_msg}"
        return base_msg


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Lightweight in-process circuit breaker."""
    endpoint: str
    failure_threshold: int
    reset_timeout_sec: int
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)
    
    def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution."""
        with self.lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            
            if self.state == CircuitBreakerState.OPEN:
                # Check if reset timeout has passed
                if time.time() - self.last_failure_time >= self.reset_timeout_sec:
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.endpoint}: transitioning to HALF_OPEN")
                    return True
                return False
            
            # HALF_OPEN state - allow one request to test
            return True
    
    def on_success(self) -> None:
        """Record successful execution."""
        with self.lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info(f"Circuit breaker {self.endpoint}: transitioning to CLOSED")
    
    def on_failure(self) -> None:
        """Record failed execution."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                # Half-open request failed, go back to open
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker {self.endpoint}: transitioning to OPEN (half-open failed)")
            elif self.state == CircuitBreakerState.CLOSED and self.failure_count >= self.failure_threshold:
                # Threshold reached, open the circuit
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker {self.endpoint}: transitioning to OPEN (threshold reached)")


class CircuitBreakerManager:
    """Manager for circuit breakers keyed by endpoint."""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self.lock = threading.Lock()
        self.config = get_config().reliability
    
    def get_breaker(self, endpoint: str) -> CircuitBreaker:
        """Get or create a circuit breaker for the endpoint."""
        with self.lock:
            if endpoint not in self.breakers:
                self.breakers[endpoint] = CircuitBreaker(
                    endpoint=endpoint,
                    failure_threshold=self.config.CB_FAIL_THRESHOLD,
                    reset_timeout_sec=self.config.CB_RESET_SEC
                )
            return self.breakers[endpoint]


# Global circuit breaker manager
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager."""
    return _circuit_breaker_manager


def map_external_error(service_name: str, endpoint: str, error: Exception) -> ReliabilityError:
    """Map external service errors to standardized error types."""
    error_str = str(error).lower()
    
    # Timeout errors
    if any(keyword in error_str for keyword in ['timeout', 'timed out', 'deadline']):
        return ReliabilityError(
            error_type=ExternalServiceError.TIMEOUT,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Connection errors
    if any(keyword in error_str for keyword in ['connection', 'network', 'unreachable', 'refused']):
        return ReliabilityError(
            error_type=ExternalServiceError.CONNECTION_ERROR,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Rate limiting
    if any(keyword in error_str for keyword in ['rate limit', 'rate_limit', '429', 'too many requests']):
        return ReliabilityError(
            error_type=ExternalServiceError.RATE_LIMIT,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Authentication errors
    if any(keyword in error_str for keyword in ['auth', 'unauthorized', '401', 'invalid key', 'api key']):
        return ReliabilityError(
            error_type=ExternalServiceError.AUTHENTICATION_ERROR,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Permission errors
    if any(keyword in error_str for keyword in ['permission', 'forbidden', '403', 'access denied']):
        return ReliabilityError(
            error_type=ExternalServiceError.PERMISSION_DENIED,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Not found errors
    if any(keyword in error_str for keyword in ['not found', '404', 'missing']):
        return ReliabilityError(
            error_type=ExternalServiceError.NOT_FOUND,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Bad request errors
    if any(keyword in error_str for keyword in ['bad request', '400', 'invalid', 'malformed']):
        return ReliabilityError(
            error_type=ExternalServiceError.BAD_REQUEST,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Server errors
    if any(keyword in error_str for keyword in ['server error', '500', 'internal error']):
        return ReliabilityError(
            error_type=ExternalServiceError.SERVER_ERROR,
            service_name=service_name,
            endpoint=endpoint,
            original_error=error
        )
    
    # Default to unknown error
    return ReliabilityError(
        error_type=ExternalServiceError.UNKNOWN_ERROR,
        service_name=service_name,
        endpoint=endpoint,
        original_error=error
    )


def create_retry_decorator(
    service_name: str,
    endpoint: str,
    max_retries: Optional[int] = None,
    base_delay_ms: Optional[int] = None
) -> Callable:
    """
    Create a retry decorator with circuit breaker and error mapping.
    
    Args:
        service_name: Name of the external service
        endpoint: Specific endpoint being called
        max_retries: Maximum number of retries (uses config default if None)
        base_delay_ms: Base delay for exponential backoff (uses config default if None)
    
    Returns:
        Decorator function that adds retry and circuit breaker logic
    """
    config = get_config().reliability
    max_retries = max_retries or config.HTTP_RETRIES
    base_delay_ms = base_delay_ms or config.HTTP_BACKOFF_BASE_MS
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            circuit_breaker = get_circuit_breaker_manager().get_breaker(endpoint)
            
            # Check circuit breaker
            if not circuit_breaker.can_execute():
                raise ReliabilityError(
                    error_type=ExternalServiceError.SERVER_ERROR,
                    service_name=service_name,
                    endpoint=endpoint,
                    original_error=None
                )
            
            try:
                # Execute the function
                result = func(*args, **kwargs)
                circuit_breaker.on_success()
                return result
                
            except Exception as e:
                # Map the error and record failure
                reliability_error = map_external_error(service_name, endpoint, e)
                reliability_error.retry_count = 0
                circuit_breaker.on_failure()
                
                # If no retries configured, raise immediately
                if max_retries == 0:
                    raise reliability_error
                
                # Retry logic
                last_error = reliability_error
                for attempt in range(1, max_retries + 1):
                    try:
                        # Calculate delay with jitter
                        delay_ms = base_delay_ms * (2 ** (attempt - 1))
                        jitter_ms = random.randint(0, int(delay_ms * 0.1))  # 10% jitter
                        total_delay_ms = delay_ms + jitter_ms
                        
                        logger.warning(
                            f"Retrying {service_name} ({endpoint}) attempt {attempt}/{max_retries} "
                            f"after {total_delay_ms}ms delay"
                        )
                        
                        time.sleep(total_delay_ms / 1000.0)
                        
                        # Check circuit breaker again
                        if not circuit_breaker.can_execute():
                            raise ReliabilityError(
                                error_type=ExternalServiceError.SERVER_ERROR,
                                service_name=service_name,
                                endpoint=endpoint,
                                original_error=None
                            )
                        
                        result = func(*args, **kwargs)
                        circuit_breaker.on_success()
                        return result
                        
                    except Exception as retry_error:
                        last_error = map_external_error(service_name, endpoint, retry_error)
                        last_error.retry_count = attempt
                        circuit_breaker.on_failure()
                        
                        # Don't retry on certain error types
                        if last_error.error_type in [
                            ExternalServiceError.AUTHENTICATION_ERROR,
                            ExternalServiceError.PERMISSION_DENIED,
                            ExternalServiceError.BAD_REQUEST,
                            ExternalServiceError.NOT_FOUND
                        ]:
                            break
                
                # All retries exhausted
                logger.error(
                    f"All retries exhausted for {service_name} ({endpoint}): "
                    f"{last_error.error_type.value} after {last_error.retry_count} attempts"
                )
                raise last_error
                
        return wrapper
    
    return decorator


def with_timeout(timeout_sec: Optional[int] = None) -> Callable:
    """
    Decorator to add timeout handling to functions.
    
    Args:
        timeout_sec: Timeout in seconds (uses config default if None)
    
    Returns:
        Decorator function that adds timeout handling
    """
    config = get_config().reliability
    timeout_sec = timeout_sec or config.HTTP_TIMEOUT_SEC
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {timeout_sec} seconds")
            
            # Set up timeout handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_sec)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Restore original handler and cancel alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    
    return decorator


def resilient_call(
    service_name: str,
    endpoint: str,
    func: Callable[..., T],
    *args,
    timeout_sec: Optional[int] = None,
    max_retries: Optional[int] = None,
    **kwargs
) -> T:
    """
    Execute a function with full reliability features.
    
    Args:
        service_name: Name of the external service
        endpoint: Specific endpoint being called
        func: Function to execute
        *args: Arguments to pass to the function
        timeout_sec: Timeout in seconds (uses config default if None)
        max_retries: Maximum number of retries (uses config default if None)
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        Result of the function execution
    
    Raises:
        ReliabilityError: If the function fails after all retries
    """
    config = get_config().reliability
    timeout_sec = timeout_sec or config.HTTP_TIMEOUT_SEC
    max_retries = max_retries or config.HTTP_RETRIES
    
    # Create decorated function with all reliability features
    decorated_func = create_retry_decorator(service_name, endpoint, max_retries)(func)
    
    if timeout_sec > 0:
        decorated_func = with_timeout(timeout_sec)(decorated_func)
    
    return decorated_func(*args, **kwargs)
