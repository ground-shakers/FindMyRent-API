"""
Notification model for in-app notifications.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import Field
from beanie import Document, Indexed


class NotificationType(str, Enum):
    """Types of notifications that can be sent to users."""
    KYC_VERIFIED = "kyc_verified"
    LISTING_APPROVED = "listing_approved"
    LISTING_REJECTED = "listing_rejected"
    LISTING_PENDING = "listing_pending"
    # System notifications (admin-created)
    SYSTEM_MAINTENANCE = "system_maintenance"
    SYSTEM_ANNOUNCEMENT = "system_announcement"
    SYSTEM_UPDATE = "system_update"


class Notification(Document):
    """Model representing an in-app notification for a user.
    
    Notifications are created automatically when certain events occur,
    such as KYC verification or listing status changes.
    """
    # user_id is None for system-wide broadcasts
    user_id: Annotated[Optional[str], Indexed(), Field(default=None, serialization_alias="userId", description="User ID or None for system-wide notifications")]
    type: Annotated[NotificationType, Field(description="Type/category of notification")]
    title: Annotated[str, Field(max_length=100, description="Short notification title")]
    message: Annotated[str, Field(max_length=500, description="Notification message body")]
    is_read: Annotated[bool, Field(default=False, serialization_alias="isRead")]
    related_id: Annotated[Optional[str], Field(default=None, serialization_alias="relatedId", description="ID of related entity (listing, etc)")]
    created_at: Annotated[datetime, Field(default_factory=datetime.utcnow, serialization_alias="createdAt")]

    class Settings:
        name = "notifications"
