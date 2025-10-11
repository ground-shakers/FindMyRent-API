from enum import Enum

from pydantic import Field, EmailStr, BaseModel, field_validator
from typing import Annotated, List

from beanie import Document, Link

from .messages import Chat
from .listings import Listing
from .helpers import UserType


class User(Document):
    """Base model for user-related entities.
    """
    first_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="lastName")]
    email: Annotated[EmailStr, Field(max_length=50)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    password: Annotated[str, Field(min_length=8, max_length=100)]
    is_active: Annotated[bool, Field(default=True, serialization_alias="isActive")]
    user_type: Annotated[UserType, Field(default=UserType.TENANT, serialization_alias="userType")]  # e.g., 'tenant', 'landlord', 'admin'


    class Settings:
        """Pydantic model settings."""
        is_root = True


class Tenant(User):
    """Tenant model representing a user who rents a property.
    """
    chats: Annotated[List[Link[Chat]], Field()]  # List of chats the user is part of
    verified: Annotated[bool, Field(default=False)]
    kyc_verified: Annotated[bool, Field(default=False)]  # Know Your Customer verification status


class LandLord(User):
    """Landlord model representing a user who owns and rents out properties.
    """
    chats: Annotated[List[Link[Chat]], Field()]  # List of chats the user is part of
    verified: Annotated[bool, Field(default=False)]
    kyc_verified: Annotated[bool, Field(default=False)]  # Know Your Customer verification status
    listings: Annotated[List[Link[Listing]], Field()]  # List of properties listed by the landlord


class Admin(User):
    """Admin model representing a user with administrative privileges.
    """
    chats: Annotated[List[Link[Chat]], Field()]  # List of chats the user is part of


class Permissions(Document):
    """Model representing user permissions.
    """
    user_type: Annotated[str, Field(unique=True)]  # Unique name of the permission
    permissions: Annotated[List[str], Field()]  # List of permissions for the user type