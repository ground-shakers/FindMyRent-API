"""Defines the structure of the email verification request."""

from pydantic import BaseModel, EmailStr, Field
from typing import Annotated

from schema.users import UserInDB


class EmailVerificationRequest(BaseModel):
    """Describes the structure of the email verification request."""

    email: EmailStr


class EmailVerificationCodeValidationRequest(BaseModel):
    """Describes the structure of the email verification code validation request."""
    
    email: EmailStr
    code: str
    

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