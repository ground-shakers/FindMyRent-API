"""Contains the schema definition for requests and responses related to users
"""

import re

from datetime import date

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

from typing import Annotated, Self, List, Literal, Optional

from models.messages import Chat

from fastapi import HTTPException
from fastapi import status

from models.helpers import UserType

class UserDateOfBirth(BaseModel):
    """Model representing a user's date of birth.
    """
    day: Annotated[int, Field(ge=1, le=31)]
    month: Annotated[int, Field(ge=1, le=12)]
    year: Annotated[int, Field(ge=1900, le=2100)]  # Assuming reasonable year range

    @model_validator(mode="after")
    def validate_minimum_age(self) -> "UserDateOfBirth":
        today = date.today()

        try:
            dob = date(self.year, self.month, self.day)
        except ValueError:
            # Invalid dates like 31 Feb
            raise ValueError("Invalid date of birth")

        age = (
            today.year
            - dob.year
            - ((today.month, today.day) < (dob.month, dob.day))
        )

        if age < 18:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You must be at least 18 years old to sign up"
            )

        return self

class CreateUserRequest(BaseModel):
    """Describes the structure of the create user request."""

    first_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="lastName")]
    email: Annotated[EmailStr, Field(max_length=50)]
    date_of_birth: Annotated[UserDateOfBirth, Field(serialization_alias="dateOfBirth")]
    gender: Annotated[Literal["male", "female", "other"], Field(max_length=6)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    password: Annotated[str, Field(min_length=8)]
    verify_password: Annotated[str, Field(min_length=8, serialization_alias="verifyPassword")]

    # * Validate the password to ensure it has at least one uppercase letter,
    # * one special character, one lowercase letter, and one number
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not re.search(r"[A-Z]", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password must contain at least one uppercase letter",
            )
        if not re.search(r"[a-z]", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password must contain at least one lowercase letter",
            )
        if not re.search(r"\d", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Password must contain at least one number",
            )
        if not re.search(r"[@$!%*?&#]", v):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"message": "Passwords do not match"},
            )
        return self


class CreateUserResponse(BaseModel):
    """Describes the structure of the create user response."""

    message: Annotated[str, Field(default="User created successfully")]
    email: Annotated[EmailStr, Field(description="Email address the verification code was sent to")]
    expires_in_minutes: Annotated[int, Field(serialization_alias="expiresInMinutes", description="Time in minutes before the verification code expires")]  # Time in minutes before the verification code expires
    user_id: Annotated[str, Field(default="", serialization_alias="userId", max_length=24, min_length=24, description="ID of the created user")]  # ID of the created user
    
    
class CreateAdminUserResponse(BaseModel):
    """Describes the structure of the create admin user request."""
    message: Annotated[str, Field(default="Admin user created successfully")]
    user: Annotated[dict, Field(description="Details of the created admin user")]

class UserInDB(BaseModel):
    """Describes the structure of the user data stored in the database."""
    
    id: Annotated[str, Field(description="Unique identifier for the user")]
    first_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="lastName")]
    email: Annotated[EmailStr, Field(max_length=50)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    user_type: Annotated[UserType, Field(serialization_alias="userType")]  # e.g., 'tenant', 'landlord', 'admin'


class GetUserResponse(BaseModel):
    """Describes the structure of the get user response."""

    first_name: Annotated[
        str, Field(max_length=50, min_length=2, serialization_alias="firstName")
    ]
    last_name: Annotated[
        str, Field(max_length=50, min_length=2, serialization_alias="lastName")
    ]
    # Use a regular unique ascending index for email (text indexes cannot be unique)
    email: Annotated[EmailStr, Field(max_length=50)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    date_of_birth: Annotated[UserDateOfBirth, Field(serialization_alias="dateOfBirth")]
    gender: Annotated[Literal["male", "female", "other"] | None, Field(default=None, max_length=6)]
    is_active: Annotated[bool, Field(default=True, serialization_alias="isActive")]
    user_type: Annotated[
        UserType, Field(serialization_alias="userType")
    ]  # e.g., 'tenant', 'landlord', 'admin'
    chats: Annotated[
        List[Chat], Field(default=[])
    ]  # List of chats the user is part of
    verified: Annotated[bool, Field(default=False)]
    kyc_verified: Annotated[
        bool, Field(default=False)
    ]  # Know Your Customer verification status
    listings: Annotated[
        List[str], Field(default=[])
    ]  # List of IDs of properties listed by the landlord


class UpdateUserRequest(BaseModel):
    """Describes the structure of the update user request.
    All fields are optional to allow partial updates.
    """

    first_name: Annotated[Optional[str], Field(default=None, max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[Optional[str], Field(default=None, max_length=50, min_length=2, serialization_alias="lastName")]
    phone_number: Annotated[Optional[str], Field(default=None, serialization_alias="phoneNumber")]
    gender: Annotated[Optional[Literal["male", "female", "other"]], Field(default=None, max_length=6)]


class UpdateUserResponse(BaseModel):
    """Describes the structure of the update user response."""

    message: Annotated[str, Field(default="User updated successfully")]
    user: Annotated[dict, Field(description="Updated user details")]


class UserAnalyticsResponse(BaseModel):
    """Describes the structure of the user analytics response."""
    
    total_users: Annotated[int, Field(serialization_alias="totalUsers")]
    
    verified_kyc_users: Annotated[int, Field(serialization_alias="verifiedKycUsers")]
    unverified_kyc_users: Annotated[int, Field(serialization_alias="unverifiedKycUsers")]
    kyc_completion_rate: Annotated[float, Field(serialization_alias="kycCompletionRate")]
    
    landlords_with_properties: Annotated[int, Field(serialization_alias="landlordsWithProperties")]
    landlords_without_properties: Annotated[int, Field(serialization_alias="landlordsWithoutProperties")]
    
    top_landlord_id: Annotated[Optional[str], Field(serialization_alias="topLandlordId")]
    
    average_age: Annotated[Optional[float], Field(serialization_alias="averageAge")]
    
    age_18_25: Annotated[int, Field(serialization_alias="age18to25")]
    age_26_35: Annotated[int, Field(serialization_alias="age26to35")]
    age_36_45: Annotated[int, Field(serialization_alias="age36to45")]
    age_46_60: Annotated[int, Field(serialization_alias="age46to60")]
    age_60_plus: Annotated[int, Field(serialization_alias="age60Plus")]
    
    users_today: Annotated[int, Field(serialization_alias="usersToday")]
    users_this_month: Annotated[int, Field(serialization_alias="usersThisMonth")]
    
    male_users: Annotated[int, Field(serialization_alias="maleUsers")]
    female_users: Annotated[int, Field(serialization_alias="femaleUsers")]
    
    male_landlords: Annotated[int, Field(serialization_alias="maleLandlords")]
    female_landlords: Annotated[int, Field(serialization_alias="femaleLandlords")]