from datetime import date

from enum import Enum

from pydantic import Field, EmailStr, BaseModel, model_validator
from typing import Annotated, List

from beanie import Document, Link, Indexed, PydanticObjectId

from .messages import Chat
from .listings import Listing
from .helpers import UserType

from schema.kyc import KYCWebhookResponse, CreateKYCSessionResponse
from schema.users import UserDateOfBirth
from typing import Union, Literal


class User(Document):
    """Base model for user-related entities.
    """
    first_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="lastName")]
    # Use a regular unique ascending index for email (text indexes cannot be unique)
    email: Annotated[EmailStr, Indexed(unique=True), Field(max_length=50)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    password: Annotated[str, Field(min_length=8)]
    is_active: Annotated[bool, Field(default=True, serialization_alias="isActive")]
    user_type: Annotated[UserType, Field(serialization_alias="userType")]  # e.g., 'tenant', 'landlord', 'admin'
    date_of_birth: Annotated[UserDateOfBirth, Field(serialization_alias="dateOfBirth")]
    gender: Annotated[Literal["male", "female", "other"], Field(max_length=6)]

    class Settings:
        """Pydantic model settings."""
        is_root = True


class LandLord(User):
    """Landlord model representing a user who owns and rents out properties.
    """
    chats: Annotated[List[Link[Chat]], Field(default=[])]  # List of chats the user is part of
    verified: Annotated[bool, Field(default=False)]
    kyc_verified: Annotated[bool, Field(default=False, serialization_alias="kycVerified")]  # Know Your Customer verification status
    listings: Annotated[List[str], Field(default=[])]  # List of properties listed by the landlord
    favorites: Annotated[List[str], Field(default=[])]  # List of saved/favorited listing IDs
    premium: Annotated[bool, Field(default=False)]  # Premium subscription status
    # Temporarily allow both session responses and webhook responses until data migration
    kyc_verification_trail: Annotated[List[Union[KYCWebhookResponse, CreateKYCSessionResponse]], Field(default=[])]


class Admin(User):
    """Admin model representing a user with administrative privileges.
    """
    chats: Annotated[List[Link[Chat]], Field(default=[])]  # List of chats the user is part of
