from enum import Enum

from pydantic import Field, EmailStr, BaseModel, field_serializer
from typing import Annotated, List

import pymongo
from beanie import Document, Link, Indexed, PydanticObjectId

from .messages import Chat
from .listings import Listing
from .helpers import UserType


class User(Document):
    """Base model for user-related entities.
    """
    first_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="firstName")]
    last_name: Annotated[str, Field(max_length=50, min_length=2, serialization_alias="lastName")]
    email: Annotated[EmailStr, Indexed(index_type=pymongo.TEXT, unique=True), Field(max_length=50)]
    phone_number: Annotated[str, Field(serialization_alias="phoneNumber")]
    password: Annotated[str, Field(min_length=8)]
    is_active: Annotated[bool, Field(default=True, serialization_alias="isActive")]
    user_type: Annotated[UserType, Field(serialization_alias="userType")]  # e.g., 'tenant', 'landlord', 'admin'

    @field_serializer("id")
    def convert_pydantic_object_id_to_string(self, id: PydanticObjectId):
        return str(id)

    class Settings:
        """Pydantic model settings."""
        is_root = True

class LandLord(User):
    """Landlord model representing a user who owns and rents out properties.
    """
    chats: Annotated[List[Link[Chat]], Field(default=[])]  # List of chats the user is part of
    verified: Annotated[bool, Field(default=False)]
    kyc_verified: Annotated[bool, Field(default=False)]  # Know Your Customer verification status
    listings: Annotated[List[Link[Listing]], Field(default=[])]  # List of properties listed by the landlord

    @field_serializer("id")
    def convert_pydantic_object_id_to_string(self, id: PydanticObjectId):
        return str(id)

class Admin(User):
    """Admin model representing a user with administrative privileges.
    """
    chats: Annotated[List[Link[Chat]], Field(default=[])]  # List of chats the user is part of

    @field_serializer("id")
    def convert_pydantic_object_id_to_string(self, id: PydanticObjectId):
        return str(id)