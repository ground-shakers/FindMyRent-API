"""
Notifications service for handling in-app notification operations.
"""

import logfire

from functools import lru_cache
from datetime import datetime
from typing import Optional, List, Tuple

from fastapi import status
from fastapi.responses import JSONResponse

from beanie import PydanticObjectId
from pymongo.errors import ConnectionFailure, PyMongoError

from models.notifications import Notification, NotificationType
from models.users import User


class NotificationsService:
    """Service class for handling notification operations.

    This service encapsulates the business logic for creating, retrieving,
    and managing user notifications.
    """

    async def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        related_id: Optional[str] = None,
    ) -> Notification:
        """Create a new notification for a user.

        Args:
            user_id: The ID of the user to notify.
            notification_type: Type of notification.
            title: Short notification title.
            message: Notification message body.
            related_id: Optional ID of related entity (listing, etc).

        Returns:
            Notification: The created notification document.
        """
        try:
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                title=title,
                message=message,
                related_id=related_id,
                is_read=False,
                created_at=datetime.utcnow(),
            )
            await notification.insert()
            logfire.info(f"Created {notification_type} notification for user {user_id}")
            return notification
        except Exception as e:
            logfire.error(f"Failed to create notification for user {user_id}: {e}")
            raise

    async def get_user_notifications(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
        unread_only: bool = False,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        """Get paginated notifications for a user.

        Args:
            user_id: The ID of the user.
            offset: Number of notifications to skip.
            limit: Maximum notifications to return.
            unread_only: If True, return only unread notifications.
            start_date: Optional start of date range filter.
            end_date: Optional end of date range filter.

        Returns:
            JSONResponse: List of notifications with pagination info.
        """
        try:
            with logfire.span(f"Getting notifications for user {user_id}"):
                # Build query - include user's own notifications AND system-wide broadcasts
                query = {
                    "$or": [
                        {"user_id": user_id},
                        {"user_id": None}  # System-wide notifications
                    ]
                }
                if unread_only:
                    query["is_read"] = False
                
                # Add date range filter
                if start_date or end_date:
                    query["created_at"] = {}
                    if start_date:
                        query["created_at"]["$gte"] = start_date
                    if end_date:
                        query["created_at"]["$lte"] = end_date

                # Get total count
                total = await Notification.find(query).count()

                # Get paginated notifications (newest first)
                notifications = await (
                    Notification.find(query)
                    .sort("-created_at")
                    .skip(offset)
                    .limit(limit)
                    .to_list()
                )

                serialized = [
                    n.model_dump(mode="json", by_alias=True)
                    for n in notifications
                ]

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "notifications": serialized,
                        "total": total,
                        "offset": offset,
                        "limit": limit,
                        "has_more": (offset + len(notifications)) < total,
                    },
                )

        except ConnectionFailure:
            logfire.error("Database connection failure getting notifications")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(f"Database error getting notifications: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred."},
            )

    async def get_unread_count(self, user_id: str):
        """Get count of unread notifications for a user.

        Args:
            user_id: The ID of the user.

        Returns:
            JSONResponse: Unread notification count.
        """
        try:
            count = await Notification.find(
                {"user_id": user_id, "is_read": False}
            ).count()

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"unread_count": count},
            )

        except PyMongoError as e:
            logfire.error(f"Database error getting unread count: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred."},
            )

    async def mark_as_read(self, notification_id: str, user_id: str):
        """Mark a single notification as read.

        Args:
            notification_id: The ID of the notification.
            user_id: The ID of the user (for ownership verification).

        Returns:
            JSONResponse: Success or error response.
        """
        try:
            notification = await Notification.get(PydanticObjectId(notification_id))

            if not notification:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Notification not found"},
                )

            # Verify ownership
            if notification.user_id != user_id:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Cannot access this notification"},
                )

            notification.is_read = True
            await notification.save()

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "Notification marked as read"},
            )

        except PyMongoError as e:
            logfire.error(f"Database error marking notification read: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred."},
            )

    async def mark_all_as_read(self, user_id: str):
        """Mark all notifications as read for a user.

        Args:
            user_id: The ID of the user.

        Returns:
            JSONResponse: Success response with count of updated notifications.
        """
        try:
            result = await Notification.find(
                {"user_id": user_id, "is_read": False}
            ).update_many({"$set": {"is_read": True}})

            count = result.modified_count if result else 0
            logfire.info(f"Marked {count} notifications as read for user {user_id}")

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "All notifications marked as read",
                    "count": count,
                },
            )

        except PyMongoError as e:
            logfire.error(f"Database error marking all notifications read: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred."},
            )

    async def register_device_token(self, user: User, token: str):
        """Registers a device token for the user.
        
        Args:
            user: The user object (Landlord or Admin).
            token: The FCM device token.
            
        Returns:
            JSONResponse: Success message.
        """
        try:
            user.device_token = token
            await user.save()
            
            logfire.info(f"Registered device token for user {user.id}")
            
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "Device token registered successfully"},
            )
        except Exception as e:
            logfire.error(f"Error registering device token for user {user.id}: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to register device token"},
            )


@lru_cache()
def get_notifications_service():
    """Returns a cached instance of NotificationsService.

    Returns:
        NotificationsService: The singleton service instance.
    """
    return NotificationsService()
