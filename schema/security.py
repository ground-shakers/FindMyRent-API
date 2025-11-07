"""Defines schema of requests and responses related to security"""

from pydantic import BaseModel

from pydantic import BaseModel


class Token(BaseModel):
    """Model representing an authentication token."""

    access_token: str
    token_type: str


class TokenPair(BaseModel):
    """Model representing both access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int  # Access token expiry in seconds


class RefreshTokenRequest(BaseModel):
    """Model for refresh token request."""

    refresh_token: str


class TokenData(BaseModel):
    """Model representing data contained in an authentication token."""

    username: str | None = None
    scopes: list[str] = []


class RefreshTokenData(BaseModel):
    """Model representing data contained in a refresh token."""

    user_id: str
    token_family: str  # For refresh token rotation
    jti: str  # Unique token identifier for replay protection
    issued_at: float  # Unix timestamp