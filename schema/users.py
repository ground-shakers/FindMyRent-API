"""Contains the schema definition for requests and responses related to users
"""

import re

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

from typing import Annotated, Self

from services.validation import is_phone_number_valid, is_email_valid

from fastapi import HTTPException
from fastapi import status

from models.helpers import UserType

class CreateUserRequest(BaseModel):
    """Describes the structure of the create user request."""

    first_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="lastName")]
    email: Annotated[EmailStr, Field(max_length=50)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    password: Annotated[str, Field(min_length=8)]
    verify_password: Annotated[str, Field(min_length=8, serialization_alias="verifyPassword")]

    @field_validator("phone_number")
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""

        validation_response = is_phone_number_valid(v)
        is_valid = validation_response[0]
        validation_description = validation_response[1]

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_description,
            )
        return v

    # * Validate the password to ensure it has at least one uppercase letter,
    # * one special character, one lowercase letter, and one number
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not re.search(r"[A-Z]", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must contain at least one uppercase letter",
            )
        if not re.search(r"[a-z]", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must contain at least one lowercase letter",
            )
        if not re.search(r"\d", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must contain at least one number",
            )
        if not re.search(r"[@$!%*?&#]", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must contain at least one special character",
            )
        return v

    # * Checks if password and verify password fields match
    @model_validator(mode="after")
    def check_password_match(self) -> Self:
        password = self.password
        verify_password = self.verify_password

        if (
            password is not None
            and verify_password is not None
            and password != verify_password
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Passwords do not match"},
            )
        return self
    
    
class CreateUserResponse(BaseModel):
    """Describes the structure of the create user response."""

    message: Annotated[str, Field(default="User created successfully")]
    email: Annotated[EmailStr, Field(description="Email address the verification code was sent to")]
    expires_in_minutes: Annotated[int, Field(serialization_alias="expiresInMinutes", description="Time in minutes before the verification code expires")]  # Time in minutes before the verification code expires
    user_id: Annotated[str, Field(default="", serialization_alias="userId", max_length=24, min_length=24, description="ID of the created user")]  # ID of the created user

class UserInDB(BaseModel):
    """Describes the structure of the user data stored in the database."""
    
    id: Annotated[str, Field(description="Unique identifier for the user")]
    first_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="lastName")]
    email: Annotated[EmailStr, Field(max_length=50)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    user_type: Annotated[UserType, Field(serialization_alias="userType")]  # e.g., 'tenant', 'landlord', 'admin'