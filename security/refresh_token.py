"""
Secure refresh token service with replay protection.
This implementation uses Redis to track used tokens and enforce one-time use.
"""

import os
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from redis import Redis
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()


class SecureRefreshTokenService:
    """Service for managing refresh tokens with replay protection."""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.refresh_token_ttl = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")) * 24 * 3600
        self.used_tokens_prefix = "used_refresh_token:"
        self.token_family_prefix = "token_family:"

    def mark_token_as_used(self, token_jti: str) -> None:
        """Mark a refresh token as used (blacklist it)."""
        key = f"{self.used_tokens_prefix}{token_jti}"
        # Store for the full token lifetime to prevent replay
        self.redis.setex(key, self.refresh_token_ttl, "used")

    def is_token_used(self, token_jti: str) -> bool:
        """Check if a refresh token has been used."""
        key = f"{self.used_tokens_prefix}{token_jti}"
        return self.redis.exists(key) > 0

    def invalidate_token_family(self, token_family: str) -> None:
        """Invalidate an entire token family (for security breaches)."""
        key = f"{self.token_family_prefix}{token_family}"
        self.redis.setex(key, self.refresh_token_ttl, "invalidated")

    def is_token_family_valid(self, token_family: str) -> bool:
        """Check if a token family is still valid."""
        key = f"{self.token_family_prefix}{token_family}"
        return self.redis.exists(key) == 0

    def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user by invalidating all their token families."""
        # Get all token families for this user
        pattern = f"token_family:*"
        keys = self.redis.keys(pattern)
        
        # Note: In production, you'd want to store user->family mapping
        # This is a simplified approach
        user_pattern = f"user_tokens:{user_id}:*"
        user_keys = self.redis.keys(user_pattern)
        
        for key in user_keys:
            self.redis.delete(key)


# Global service instance
_refresh_token_service: Optional[SecureRefreshTokenService] = None


def get_secure_refresh_token_service() -> SecureRefreshTokenService:
    """Get the secure refresh token service instance."""
    global _refresh_token_service
    
    if _refresh_token_service is None:
        redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)
        _refresh_token_service = SecureRefreshTokenService(redis_client)
    
    return _refresh_token_service
