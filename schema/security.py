"""Defines schema of requests and responses related to security"""

import re

from typing import Annotated

from pydantic import BaseModel, Field, EmailStr, model_validator
from fastapi import HTTPException, status


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


# =============================================================================
# Password Reset Schemas
# =============================================================================


class ForgotPasswordRequest(BaseModel):
    """Request model for initiating a password reset.
    
    Attributes:
        email: The email address associated with the account.
    """
    email: Annotated[EmailStr, Field(
        description="Email address associated with the account",
        examples=["user@example.com"]
    )]


class ForgotPasswordResponse(BaseModel):
    """Response model for forgot password request.
    
    Note: For security, this response is the same whether the email
    exists in our system or not, to prevent user enumeration attacks.
    
    Attributes:
        message: Status message (always indicates email was sent if valid).
        email: The email address the reset link was sent to.
    """
    message: Annotated[str, Field(
        description="Status message",
        examples=["If an account with this email exists, a password reset link has been sent."]
    )]
    email: Annotated[EmailStr, Field(
        description="The email address provided"
    )]


class ResetPasswordRequest(BaseModel):
    """Request model for completing a password reset.
    
    Attributes:
        token: The password reset token from the email link.
        password: The new password (must meet strength requirements).
        confirm_password: Confirmation of the new password.
    """
    token: Annotated[str, Field(
        min_length=64,
        max_length=128,
        description="Password reset token from the email link"
    )]
    password: Annotated[str, Field(
        min_length=8,
        max_length=128,
        description="New password (min 8 chars, must include uppercase, lowercase, number, special char)"
    )]
    confirm_password: Annotated[str, Field(
        min_length=8,
        max_length=128,
        description="Confirmation of the new password"
    )]

    @model_validator(mode="after")
    def validate_passwords(self):
        """Validate password strength and confirmation match."""
        password = self.password
        confirm_password = self.confirm_password
        
        # Check password strength
        if not re.search(r"[A-Z]", password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password must contain at least one uppercase letter",
            )
        if not re.search(r"[a-z]", password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password must contain at least one lowercase letter",
            )
        if not re.search(r"\d", password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password must contain at least one number",
            )
        if not re.search(r"[@$!%*?&#]", password):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password must contain at least one special character (@$!%*?&#)",
            )
        
        # Check passwords match
        if password != confirm_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Passwords do not match",
            )
        
        return self


class ResetPasswordResponse(BaseModel):
    """Response model for successful password reset.
    
    Attributes:
        message: Success message.
    """
    message: Annotated[str, Field(
        description="Success message",
        examples=["Password has been reset successfully. You can now log in with your new password."]
    )]
