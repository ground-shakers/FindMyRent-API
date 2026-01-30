"""Unit tests for AdminRepository.

These tests use mock patching to test repository methods without requiring
a real MongoDB connection or Beanie initialization.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from beanie import PydanticObjectId

from repositories.admin_repository import AdminRepository, get_admin_repository


class TestAdminRepository:
    """Test cases for AdminRepository."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository instance for each test."""
        return AdminRepository()

    # =========================================================================
    # get_by_id tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_by_id_returns_admin_when_found(self, repository):
        """Test that get_by_id returns an admin when found."""
        # Arrange
        user_id = "507f1f77bcf86cd799439011"
        mock_admin = MagicMock()
        mock_admin.id = PydanticObjectId(user_id)
        
        with patch("repositories.admin_repository.Admin") as MockAdmin:
            MockAdmin.get = AsyncMock(return_value=mock_admin)
            
            # Act
            result = await repository.get_by_id(user_id)
            
            # Assert
            assert result == mock_admin
            MockAdmin.get.assert_called_once_with(PydanticObjectId(user_id))

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self, repository):
        """Test that get_by_id returns None when admin is not found."""
        with patch("repositories.admin_repository.Admin") as MockAdmin:
            MockAdmin.get = AsyncMock(return_value=None)
            
            # Act
            result = await repository.get_by_id("507f1f77bcf86cd799439011")
            
            # Assert
            assert result is None

    # =========================================================================
    # get_by_email tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_by_email_returns_admin_when_found(self, repository):
        """Test that get_by_email returns an admin when found."""
        # Arrange
        mock_admin = MagicMock()
        mock_admin.email = "admin@example.com"
        
        with patch("repositories.admin_repository.Admin") as MockAdmin:
            MockAdmin.find_one = AsyncMock(return_value=mock_admin)
            
            # Act
            result = await repository.get_by_email("admin@example.com")
            
            # Assert
            assert result == mock_admin
            MockAdmin.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_email_returns_none_when_not_found(self, repository):
        """Test that get_by_email returns None when admin is not found."""
        with patch("repositories.admin_repository.Admin") as MockAdmin:
            MockAdmin.find_one = AsyncMock(return_value=None)
            
            # Act
            result = await repository.get_by_email("nonexistent@example.com")
            
            # Assert
            assert result is None

    # =========================================================================
    # find_all tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_find_all_returns_paginated_results(self, repository):
        """Test that find_all returns paginated admin list."""
        # Arrange
        mock_admins = [MagicMock() for _ in range(3)]
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=mock_admins)
        
        with patch("repositories.admin_repository.Admin") as MockAdmin:
            MockAdmin.find.return_value = mock_query
            
            # Act
            result = await repository.find_all(offset=0, limit=10)
            
            # Assert
            assert result == mock_admins

    @pytest.mark.asyncio
    async def test_find_all_returns_empty_list_when_no_admins(self, repository):
        """Test that find_all returns empty list when no admins exist."""
        # Arrange
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[])
        
        with patch("repositories.admin_repository.Admin") as MockAdmin:
            MockAdmin.find.return_value = mock_query
            
            # Act
            result = await repository.find_all()
            
            # Assert
            assert result == []

    # =========================================================================
    # insert tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_insert_calls_document_insert(self, repository):
        """Test that insert calls the document's insert method."""
        # Arrange
        mock_admin = MagicMock()
        mock_admin.insert = AsyncMock(return_value=mock_admin)
        
        # Act
        result = await repository.insert(mock_admin)
        
        # Assert
        mock_admin.insert.assert_called_once()
        assert result == mock_admin

    # =========================================================================
    # delete tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_calls_document_delete(self, repository):
        """Test that delete calls the document's delete method."""
        # Arrange
        mock_admin = MagicMock()
        mock_admin.delete = AsyncMock()
        
        # Act
        await repository.delete(mock_admin)
        
        # Assert
        mock_admin.delete.assert_called_once()


class TestGetAdminRepository:
    """Test cases for get_admin_repository factory function."""

    def test_returns_repository_instance(self):
        """Test that get_admin_repository returns an AdminRepository instance."""
        get_admin_repository.cache_clear()
        
        result = get_admin_repository()
        
        assert isinstance(result, AdminRepository)

    def test_returns_cached_instance(self):
        """Test that get_admin_repository returns the same cached instance."""
        get_admin_repository.cache_clear()
        
        instance1 = get_admin_repository()
        instance2 = get_admin_repository()
        
        assert instance1 is instance2
