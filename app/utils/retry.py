"""
Retry utilities with exponential backoff for resilient operations.
"""

import asyncio
import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Union

logger = logging.getLogger(__name__)

class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""
    
    def __init__(self, message: str, last_exception: Exception):
        super().__init__(message)
        self.last_exception = last_exception

def exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    backoff_factor: float = 2.0,
    retry_on: Optional[Tuple[Exception, ...]] = None
):
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Add random jitter to prevent thundering herd
        backoff_factor: Multiplier for exponential backoff
        retry_on: Tuple of exceptions to retry on (None = all exceptions)
    """
    if retry_on is None:
        retry_on = (Exception,)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"✗ {func.__name__} failed after {max_retries + 1} attempts. "
                            f"Last error: {e}"
                        )
                        raise RetryError(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts",
                            e
                        )
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"⚠ {func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    time.sleep(delay)
                except Exception as e:
                    # Don't retry on exceptions not in retry_on
                    logger.error(f"✗ {func.__name__} failed with non-retryable error: {e}")
                    raise
            
            # This should never be reached
            raise last_exception
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"✗ {func.__name__} failed after {max_retries + 1} attempts. "
                            f"Last error: {e}"
                        )
                        raise RetryError(
                            f"Function {func.__name__} failed after {max_retries + 1} attempts",
                            e
                        )
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(
                        f"⚠ {func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(delay)
                except Exception as e:
                    # Don't retry on exceptions not in retry_on
                    logger.error(f"✗ {func.__name__} failed with non-retryable error: {e}")
                    raise
            
            # This should never be reached
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Common retry configurations
retry_on_network_errors = exponential_backoff(
    max_retries=3,
    base_delay=1.0,
    retry_on=(ConnectionError, TimeoutError, OSError)
)

retry_on_http_errors = exponential_backoff(
    max_retries=3,
    base_delay=2.0,
    retry_on=(ConnectionError, TimeoutError)
)

retry_on_gcs_errors = exponential_backoff(
    max_retries=5,
    base_delay=2.0,
    max_delay=30.0,
    retry_on=(Exception,)  # GCS can have various error types
)

# Context manager for retry operations
class RetryContext:
    """Context manager for retry operations with custom logic."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        operation_name: str = "operation"
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.operation_name = operation_name
        self.attempt = 0
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return  # Success, no retry needed
        
        self.attempt += 1
        
        if self.attempt <= self.max_retries:
            delay = self.base_delay * (2 ** (self.attempt - 1))
            logger.warning(
                f"⚠ {self.operation_name} attempt {self.attempt} failed: {exc_val}. "
                f"Retrying in {delay:.1f}s..."
            )
            time.sleep(delay)
            return True  # Suppress exception, continue retrying
        else:
            logger.error(
                f"✗ {self.operation_name} failed after {self.max_retries + 1} attempts"
            )
            return False  # Let exception propagate

# Example usage:
"""
# Decorator usage
@exponential_backoff(max_retries=3, base_delay=1.0)
def download_file(url):
    # This will retry up to 3 times with exponential backoff
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.content

# Context manager usage
for _ in range(max_retries + 1):
    with RetryContext(max_retries=3, operation_name="GCS upload") as retry_ctx:
        blob.upload_from_filename(file_path)
        break  # Success, exit retry loop
"""