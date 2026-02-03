"""Integration tests for Notifications endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import status
from fastapi.responses import JSONResponse

from main import app
from services.notifications_service import NotificationsService, get_notifications_service


# Test data
VALID_NOTIFICATION_ID = "507f1f77bcf86cd799439011"


class TestGetNotifications:
    """Tests for GET /api/v1/notifications endpoint."""

    @pytest.mark.asyncio
    async def test_get_notifications_success(self, async_client, override_auth_landlord):
        """Test getting notifications returns list with pagination."""
        # Arrange
        override_auth_landlord()
        
        mock_service = MagicMock(spec=NotificationsService)
        mock_service.get_user_notifications = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "notifications": [
                    {
                        "id": VALID_NOTIFICATION_ID,
                        "type": "listing_approved",
                        "title": "Listing Approved",
                        "message": "Your listing has been approved.",
                        "isRead": False
                    }
                ],
                "total": 1,
                "offset": 0,
                "limit": 20,
                "has_more": False
            }
        ))
        
        app.dependency_overrides[get_notifications_service] = lambda: mock_service
        
        # Act
        response = await async_client.get("/api/v1/notifications")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "notifications" in data
        assert "total" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_notifications_unread_only(self, async_client, override_auth_landlord):
        """Test getting only unread notifications."""
        # Arrange
        override_auth_landlord()
        
        mock_service = MagicMock(spec=NotificationsService)
        mock_service.get_user_notifications = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"notifications": [], "total": 0, "offset": 0, "limit": 20, "has_more": False}
        ))
        
        app.dependency_overrides[get_notifications_service] = lambda: mock_service
        
        # Act
        response = await async_client.get("/api/v1/notifications?unreadOnly=true")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()


class TestGetUnreadCount:
    """Tests for GET /api/v1/notifications/unread-count endpoint."""

    @pytest.mark.asyncio
    async def test_get_unread_count_success(self, async_client, override_auth_landlord):
        """Test getting unread count."""
        # Arrange
        override_auth_landlord()
        
        mock_service = MagicMock(spec=NotificationsService)
        mock_service.get_unread_count = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"unread_count": 5}
        ))
        
        app.dependency_overrides[get_notifications_service] = lambda: mock_service
        
        # Act
        response = await async_client.get("/api/v1/notifications/unread-count")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["unread_count"] == 5
        
        # Cleanup
        app.dependency_overrides.clear()


class TestMarkAsRead:
    """Tests for PATCH /api/v1/notifications/{id}/read endpoint."""

    @pytest.mark.asyncio
    async def test_mark_as_read_success(self, async_client, override_auth_landlord):
        """Test marking a notification as read."""
        # Arrange
        override_auth_landlord()
        
        mock_service = MagicMock(spec=NotificationsService)
        mock_service.mark_as_read = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Notification marked as read"}
        ))
        
        app.dependency_overrides[get_notifications_service] = lambda: mock_service
        
        # Act
        response = await async_client.patch(f"/api/v1/notifications/{VALID_NOTIFICATION_ID}/read")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_mark_as_read_not_found(self, async_client, override_auth_landlord):
        """Test marking non-existent notification returns 404."""
        # Arrange
        override_auth_landlord()
        
        mock_service = MagicMock(spec=NotificationsService)
        mock_service.mark_as_read = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Notification not found"}
        ))
        
        app.dependency_overrides[get_notifications_service] = lambda: mock_service
        
        # Act
        response = await async_client.patch(f"/api/v1/notifications/{VALID_NOTIFICATION_ID}/read")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Cleanup
        app.dependency_overrides.clear()


class TestMarkAllAsRead:
    """Tests for PATCH /api/v1/notifications/read-all endpoint."""

    @pytest.mark.asyncio
    async def test_mark_all_as_read_success(self, async_client, override_auth_landlord):
        """Test marking all notifications as read."""
        # Arrange
        override_auth_landlord()
        
        mock_service = MagicMock(spec=NotificationsService)
        mock_service.mark_all_as_read = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "All notifications marked as read", "count": 5}
        ))
        
        app.dependency_overrides[get_notifications_service] = lambda: mock_service
        
        # Act
        response = await async_client.patch("/api/v1/notifications/read-all")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 5
        
        # Cleanup
        app.dependency_overrides.clear()
