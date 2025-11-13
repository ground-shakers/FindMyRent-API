"""Defines the structure of the email verification request."""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Annotated

from fastapi import HTTPException, status

from schema.users import UserInDB


class EmailVerificationRequest(BaseModel):
    """Describes the structure of the email verification request."""

    email: EmailStr


class EmailVerificationCodeValidationRequest(BaseModel):
    """Describes the structure of the email verification code validation request."""
    
    email: EmailStr
    code: Annotated[str, Field(description="Verification code sent to email address", min_length=6, max_length=6)]
    
    @field_validator("code")
    def check_that_code_is_numeric(cls, value: str) -> str:
        if not value.isdigit():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code must be numeric")
        return value
    

class EmailVerificationResponse(BaseModel):
    """Describes the structure of the email verification response."""
    
    message: str
    email: EmailStr
    expires_in_minutes: int
    
    
class EmailVerificationCodeValidationResponse(BaseModel):
    """Describes the structure of the email verification code validation response."""
    
    message: str
    email: EmailStr
    verified: bool
    

class VerifiedEmailResponse(BaseModel):
    """Describes the structure of the response once an email is verified successfully."""
    message: Annotated[str, Field(default="Email verified successfully")]
    user: Annotated[UserInDB, Field(description="Details of the user associated with the verified email")]  # User ID