"""Unit tests for PermissionsRepository.

These tests use mock patching to test repository methods without requiring
a real MongoDB connection or Beanie initialization.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from repositories.permissions_repository import PermissionsRepository, get_permissions_repository


class TestPermissionsRepository:
    """Test cases for PermissionsRepository."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository instance for each test."""
        return PermissionsRepository()

    # =========================================================================
    # get_by_user_type tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_by_user_type_returns_permissions_when_found(self, repository):
        """Test that get_by_user_type returns permissions when found."""
        # Arrange
        mock_permissions = MagicMock()
        mock_permissions.user_type = "landlord"
        mock_permissions.scopes = ["me", "upd:user"]
        
        with patch("repositories.permissions_repository.Permissions") as MockPermissions:
            MockPermissions.find_one = AsyncMock(return_value=mock_permissions)
            
            # Act
            result = await repository.get_by_user_type("landlord")
            
            # Assert
            assert result == mock_permissions
            MockPermissions.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_user_type_returns_none_when_not_found(self, repository):
        """Test that get_by_user_type returns None when permissions not found."""
        with patch("repositories.permissions_repository.Permissions") as MockPermissions:
            MockPermissions.find_one = AsyncMock(return_value=None)
            
            # Act
            result = await repository.get_by_user_type("super_user")
            
            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_user_type_admin(self, repository):
        """Test getting permissions for admin user type."""
        # Arrange
        mock_permissions = MagicMock()
        mock_permissions.user_type = "admin"
        mock_permissions.scopes = ["adm:read:users", "ver:listing"]
        
        with patch("repositories.permissions_repository.Permissions") as MockPermissions:
            MockPermissions.find_one = AsyncMock(return_value=mock_permissions)
            
            # Act
            result = await repository.get_by_user_type("admin")
            
            # Assert
            assert result == mock_permissions
            assert result.user_type == "admin"

    @pytest.mark.asyncio
    async def test_get_by_user_type_landlord(self, repository):
        """Test getting permissions for landlord user type."""
        # Arrange
        mock_permissions = MagicMock()
        mock_permissions.user_type = "landlord"
        mock_permissions.scopes = ["upd:listing", "del:listing"]
        
        with patch("repositories.permissions_repository.Permissions") as MockPermissions:
            MockPermissions.find_one = AsyncMock(return_value=mock_permissions)
            
            # Act
            result = await repository.get_by_user_type("landlord")
            
            # Assert
            assert result == mock_permissions


class TestGetPermissionsRepository:
    """Test cases for get_permissions_repository factory function."""

    def test_returns_repository_instance(self):
        """Test that get_permissions_repository returns a PermissionsRepository instance."""
        get_permissions_repository.cache_clear()
        
        result = get_permissions_repository()
        
        assert isinstance(result, PermissionsRepository)

    def test_returns_cached_instance(self):
        """Test that get_permissions_repository returns the same cached instance."""
        get_permissions_repository.cache_clear()
        
        instance1 = get_permissions_repository()
        instance2 = get_permissions_repository()
        
        assert instance1 is instance2
