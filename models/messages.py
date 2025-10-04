"""Defines message-related models for the application.
"""
import pytz

from enum import Enum

from datetime import datetime

from pydantic import Field

from beanie import Document, Link

from typing import Annotated, List

from .helpers import UserType


class ChatType(str, Enum):
    """Model representing the type of chat."""
    TENANT_LANDLORD: str = "tenant-landlord"
    TENANT_ADMIN: str = "tenant-admin"
    LANDLORD_ADMIN: str = "landlord-admin"


class Message(Document):
    """Message model representing a message sent between users.
    """
    content: Annotated[str, Field(max_length=1000)]
    timestamp: Annotated[datetime, Field(default_factory=lambda: datetime.now(pytz.utc))]
    sender: Annotated[List[str], Field()]  # user who sent the message
    sender_type: Annotated[UserType, Field()]  # Type of user: 'tenant', 'landlord', or 'admin'
    chat_id: Annotated[int, Field()]
    read: Annotated[bool, Field(default=False)]  # Read status of the message


class Chat(Document):
    """Chat model representing a conversation between users.
    """
    messages: Annotated[List[Link[Message]], Field()]  # List of messages in the chat
    participants: Annotated[List[str], Field()]  # List of users participating in the chat
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(pytz.utc))]
    updated_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(pytz.utc))]
    chat_type: Annotated[ChatType, Field()]  # Type of chat based on participants
