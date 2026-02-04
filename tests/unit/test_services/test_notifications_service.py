"""Unit tests for NotificationsService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from services.notifications_service import NotificationsService
from models.users import User

class TestNotificationsService:
    """Tests for NotificationsService."""

    @pytest.mark.asyncio
    async def test_register_device_token_success(self):
        """Test registering device token updates user and returns 200."""
        # Arrange
        service = NotificationsService()
        mock_user = MagicMock(spec=User)
        mock_user.id = "user123"
        mock_user.device_token = None
        mock_user.save = AsyncMock()
        
        token = "test-token-123"
        
        # Act
        response = await service.register_device_token(mock_user, token)
        
        # Assert
        assert mock_user.device_token == token
        mock_user.save.assert_awaited_once()
        assert response.status_code == status.HTTP_200_OK
        assert response.body  # content exists (in json)

    @pytest.mark.asyncio
    async def test_register_device_token_failure(self):
        """Test exception during registration returns 500."""
        # Arrange
        service = NotificationsService()
        mock_user = MagicMock(spec=User)
        mock_user.id = "user123"
        mock_user.save = AsyncMock(side_effect=Exception("DB Error"))
        
        # Act
        response = await service.register_device_token(mock_user, "token")
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
