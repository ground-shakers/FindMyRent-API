"""
Notifications router for handling user notification endpoints.
"""

import logfire

from fastapi import APIRouter, status, Depends, Security, Query, Path, Body
from fastapi.responses import JSONResponse

from models.users import LandLord, Admin
from models.notifications import NotificationType

from security.helpers import get_current_active_user
from services.notifications_service import get_notifications_service, NotificationsService

from typing import Annotated, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class CreateNotificationRequest(BaseModel):
    """Request body for admin to create a notification."""
    user_id: Annotated[Optional[str], Field(default=None, min_length=24, max_length=24, description="Target user ID (omit for system-wide broadcast)", serialization_alias="userId")]
    type: Annotated[NotificationType, Field(description="Notification type")]
    title: Annotated[str, Field(max_length=100, description="Notification title")]
    message: Annotated[str, Field(max_length=500, description="Notification message")]
    related_id: Annotated[Optional[str], Field(default=None, max_length=24, serialization_alias="relatedId", description="Related entity ID")]


router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"],
)


@router.get("")
async def get_notifications(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    notifications_service: Annotated[NotificationsService, Depends(get_notifications_service)],
    offset: Annotated[
        int,
        Query(description="Number of notifications to skip for pagination", ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(description="Maximum notifications to return (1-50)", ge=1, le=50),
    ] = 20,
    unread_only: Annotated[
        bool,
        Query(description="Only return unread notifications", alias="unreadOnly"),
    ] = False,
    start_date: Annotated[
        Optional[datetime],
        Query(description="Filter notifications from this date (ISO 8601 format)", alias="startDate"),
    ] = None,
    end_date: Annotated[
        Optional[datetime],
        Query(description="Filter notifications until this date (ISO 8601 format)", alias="endDate"),
    ] = None,
):
    """Get user's notifications.
    
    Retrieves a paginated list of notifications for the authenticated user,
    sorted by newest first. Supports filtering by date range.
    
    ## Query Parameters
    | Parameter | Default | Description |
    |-----------|---------|-------------|
    | offset | 0 | Skip N notifications |
    | limit | 20 | Return max N notifications (1-50) |
    | unreadOnly | false | Only return unread notifications |
    | startDate | null | Filter from date (ISO 8601) |
    | endDate | null | Filter until date (ISO 8601) |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "notifications": [
            {
                "id": "507f1f77bcf86cd799439011",
                "type": "listing_approved",
                "title": "Listing Approved",
                "message": "Your listing has been approved and is now live.",
                "isRead": false,
                "relatedId": "507f1f77bcf86cd799439012",
                "createdAt": "2024-01-15T10:30:00Z"
            }
        ],
        "total": 15,
        "offset": 0,
        "limit": 20,
        "has_more": false
    }
    ```
    """
    return await notifications_service.get_user_notifications(
        user_id=str(current_user.id),
        offset=offset,
        limit=limit,
        unread_only=unread_only,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    notifications_service: Annotated[NotificationsService, Depends(get_notifications_service)],
):
    """Get count of unread notifications.
    
    Quick endpoint to get the number of unread notifications for the user.
    Useful for displaying notification badges in the UI.
    
    ## Success Response (200 OK)
    ```json
    {
        "unread_count": 5
    }
    ```
    """
    return await notifications_service.get_unread_count(str(current_user.id))


@router.patch("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: Annotated[
        str,
        Path(
            description="The unique identifier of the notification",
            min_length=24,
            max_length=24,
        ),
    ],
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    notifications_service: Annotated[NotificationsService, Depends(get_notifications_service)],
):
    """Mark a single notification as read.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | notification_id | string (24 chars) | MongoDB ObjectId of the notification |
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "Notification marked as read"
    }
    ```
    
    ## Error Responses
    | Status | Description |
    |--------|-------------|
    | 403 | Cannot access this notification |
    | 404 | Notification not found |
    """
    return await notifications_service.mark_as_read(
        notification_id=notification_id,
        user_id=str(current_user.id),
    )


@router.patch("/read-all")
async def mark_all_notifications_as_read(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    notifications_service: Annotated[NotificationsService, Depends(get_notifications_service)],
):
    """Mark all notifications as read.
    
    Marks all unread notifications for the user as read in a single operation.
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "All notifications marked as read",
        "count": 5
    }
    ```
    """
    return await notifications_service.mark_all_as_read(str(current_user.id))


@router.post("/admin", status_code=status.HTTP_201_CREATED)
async def create_notification_admin(
    payload: CreateNotificationRequest,
    current_user: Annotated[
        Admin, Security(get_current_active_user, scopes=["adm:write:notifications"])
    ],
    notifications_service: Annotated[NotificationsService, Depends(get_notifications_service)],
):
    """Create a notification (Admin only).
    
    Allows administrators to send notifications to specific users or broadcast
    system-wide notifications (e.g., maintenance announcements).
    
    ## Request Body
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | userId | string (24 chars) | No | Target user ID (omit for system-wide) |
    | type | string | Yes | Notification type (see below) |
    | title | string | Yes | Notification title (max 100 chars) |
    | message | string | Yes | Notification body (max 500 chars) |
    | relatedId | string | No | Related entity ID |
    
    ## Notification Types
    - User-specific: `kyc_verified`, `listing_approved`, `listing_rejected`, `listing_pending`
    - System-wide: `system_maintenance`, `system_announcement`, `system_update`
    
    ## Example: User Notification
    ```json
    {
        "userId": "507f1f77bcf86cd799439011",
        "type": "listing_approved",
        "title": "Listing Approved",
        "message": "Your listing is now live!"
    }
    ```
    
    ## Example: System Broadcast
    ```json
    {
        "type": "system_maintenance",
        "title": "Scheduled Maintenance",
        "message": "The system will be down from 2am-4am UTC."
    }
    ```
    
    ## Success Response (201 Created)
    ```json
    {
        "message": "Notification created successfully",
        "notification": {...}
    }
    ```
    """
    try:
        notification = await notifications_service.create_notification(
            user_id=payload.user_id,
            notification_type=payload.type,
            title=payload.title,
            message=payload.message,
            related_id=payload.related_id,
        )
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Notification created successfully",
                "notification": notification.model_dump(mode="json", by_alias=True),
            },
        )
    except Exception as e:
        logfire.error(f"Error creating notification: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to create notification"},
        )
