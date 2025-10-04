"""Defines the structure of the email verification request."""

from pydantic import BaseModel, EmailStr


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