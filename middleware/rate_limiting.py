"""
FastAPI Rate Limiting Middleware using Token Bucket Algorithm

This module provides a thread-safe rate limiting middleware for FastAPI applications
using the token bucket algorithm to control request rates per client.
"""

import time
import logging
from typing import Callable, Dict, Optional
from threading import Lock
from fastapi import FastAPI, Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TokenBucket:
    """
    Token Bucket implementation for rate limiting.

    The token bucket algorithm allows bursts while maintaining an average rate.
    Tokens are added at a constant rate, and each request consumes one token.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize a token bucket.

        Args:
            capacity: Maximum number of tokens the bucket can hold
            refill_rate: Number of tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = Lock()

    def _refill(self) -> None:
        """
        Refill the bucket with tokens based on elapsed time.

        This method calculates how many tokens should be added based on
        the time elapsed since the last refill.
        """
        now = time.time()
        elapsed = now - self.last_refill

        # Calculate tokens to add based on refill rate and elapsed time
        tokens_to_add = elapsed * self.refill_rate

        # Update token count, capping at capacity
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume (default: 1)

        Returns:
            True if tokens were successfully consumed, False otherwise
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_available_tokens(self) -> float:
        """
        Get the current number of available tokens.

        Returns:
            Current token count
        """
        with self.lock:
            self._refill()
            return self.tokens


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting using the token bucket algorithm.

    This middleware tracks requests per client IP address and enforces
    rate limits using individual token buckets for each client.
    """

    def __init__(
        self,
        app: FastAPI,
        requests_per_minute: int = 100,
        bucket_capacity: Optional[int] = None,
        cleanup_interval: int = 3600,
        exclude_paths: Optional[list] = None,
    ):
        """
        Initialize the rate limiting middleware.

        Args:
            app: FastAPI application instance
            requests_per_minute: Maximum requests allowed per minute (default: 100)
            bucket_capacity: Maximum burst capacity (default: same as requests_per_minute)
            cleanup_interval: Interval in seconds to clean up old buckets (default: 3600)
            exclude_paths: List of paths to exclude from rate limiting (default: None)
        """
        super().__init__(app)

        # Configuration
        self.requests_per_minute = requests_per_minute
        self.bucket_capacity = bucket_capacity or requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # Convert to per-second rate
        self.cleanup_interval = cleanup_interval
        self.exclude_paths = set(exclude_paths) if exclude_paths else set()

        # Storage for client buckets
        self.buckets: Dict[str, TokenBucket] = {}
        self.bucket_lock = Lock()
        self.last_cleanup = time.time()

        logger.info(
            f"Rate limiter initialized: {requests_per_minute} req/min, "
            f"capacity: {self.bucket_capacity}, refill rate: {self.refill_rate:.2f} tokens/sec"
        )

    def _get_client_identifier(self, request: Request) -> str:
        """
        Extract client identifier from the request.

        Uses X-Forwarded-For header if available (for proxied requests),
        otherwise falls back to direct client IP.

        Args:
            request: FastAPI Request object

        Returns:
            Client identifier string (typically IP address)
        """
        # Check for forwarded IP (useful when behind a proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    def _get_or_create_bucket(self, client_id: str) -> TokenBucket:
        """
        Get existing bucket for client or create a new one.

        Args:
            client_id: Client identifier

        Returns:
            TokenBucket instance for the client
        """
        with self.bucket_lock:
            if client_id not in self.buckets:
                self.buckets[client_id] = TokenBucket(
                    capacity=self.bucket_capacity, refill_rate=self.refill_rate
                )
                logger.debug(f"Created new token bucket for client: {client_id}")

            return self.buckets[client_id]

    def _cleanup_old_buckets(self) -> None:
        """
        Remove buckets that haven't been used recently to prevent memory leaks.

        This method runs periodically based on cleanup_interval and removes
        buckets that are full (indicating no recent activity).
        """
        now = time.time()

        # Only cleanup if enough time has passed
        if now - self.last_cleanup < self.cleanup_interval:
            return

        with self.bucket_lock:
            # Find buckets that are full (haven't been used recently)
            to_remove = [
                client_id
                for client_id, bucket in self.buckets.items()
                if bucket.get_available_tokens() >= bucket.capacity
                and (now - bucket.last_refill) > self.cleanup_interval
            ]

            # Remove old buckets
            for client_id in to_remove:
                del self.buckets[client_id]

            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} inactive token buckets")

            self.last_cleanup = now

    def _should_exclude_path(self, path: str) -> bool:
        """
        Check if the request path should be excluded from rate limiting.

        Args:
            path: Request path

        Returns:
            True if path should be excluded, False otherwise
        """
        return path in self.exclude_paths

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process incoming requests and enforce rate limiting.

        Args:
            request: FastAPI Request object
            call_next: Next middleware or route handler

        Returns:
            Response object

        Raises:
            HTTPException: When rate limit is exceeded
        """
        # Check if path should be excluded from rate limiting
        if self._should_exclude_path(request.url.path):
            return await call_next(request)

        # Perform periodic cleanup
        self._cleanup_old_buckets()

        # Get client identifier
        client_id = self._get_client_identifier(request)

        # Get or create token bucket for this client
        bucket = self._get_or_create_bucket(client_id)

        # Try to consume a token
        if bucket.consume():
            # Request allowed
            logger.debug(
                f"Request allowed for {client_id} on {request.url.path} "
                f"({bucket.get_available_tokens():.2f} tokens remaining)"
            )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(
                int(bucket.get_available_tokens())
            )

            return response
        else:
            # Rate limit exceeded
            logger.warning(f"Rate limit exceeded for {client_id} on {request.url.path}")

            # Calculate retry-after time (time to get one token back)
            retry_after = int(1 / self.refill_rate) + 1

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Maximum {self.requests_per_minute} requests per minute allowed.",
                    "retry_after": retry_after,
                },
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(retry_after),
                },
            )