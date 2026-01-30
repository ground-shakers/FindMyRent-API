"""Unit tests for LandLordRepository.

These tests use mock patching to test repository methods without requiring
a real MongoDB connection or Beanie initialization.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from beanie import PydanticObjectId

from repositories.landlord_repository import LandLordRepository, get_landlord_repository


class TestLandLordRepository:
    """Test cases for LandLordRepository."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository instance for each test."""
        return LandLordRepository()

    # =========================================================================
    # get_by_id tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_by_id_returns_landlord_when_found(self, repository):
        """Test that get_by_id returns a landlord when found."""
        # Arrange
        user_id = "507f1f77bcf86cd799439011"
        mock_landlord = MagicMock()
        mock_landlord.id = PydanticObjectId(user_id)
        
        with patch("repositories.landlord_repository.LandLord") as MockLandLord:
            MockLandLord.get = AsyncMock(return_value=mock_landlord)
            
            # Act
            result = await repository.get_by_id(user_id)
            
            # Assert
            assert result == mock_landlord
            MockLandLord.get.assert_called_once_with(PydanticObjectId(user_id))

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self, repository):
        """Test that get_by_id returns None when landlord is not found."""
        with patch("repositories.landlord_repository.LandLord") as MockLandLord:
            MockLandLord.get = AsyncMock(return_value=None)
            
            # Act
            result = await repository.get_by_id("507f1f77bcf86cd799439011")
            
            # Assert
            assert result is None

    # =========================================================================
    # find_unverified_by_email tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_find_unverified_by_email_returns_user_when_found(self, repository):
        """Test finding an unverified user by email."""
        # Arrange
        mock_landlord = MagicMock()
        mock_landlord.email = "test@example.com"
        mock_landlord.verified = False
        
        with patch("repositories.landlord_repository.LandLord") as MockLandLord:
            MockLandLord.find_one = AsyncMock(return_value=mock_landlord)
            
            # Act
            result = await repository.find_unverified_by_email("test@example.com")
            
            # Assert
            assert result == mock_landlord
            MockLandLord.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_unverified_by_email_returns_none_when_not_found(self, repository):
        """Test that find_unverified returns None when no matching user exists."""
        with patch("repositories.landlord_repository.LandLord") as MockLandLord:
            MockLandLord.find_one = AsyncMock(return_value=None)
            
            # Act
            result = await repository.find_unverified_by_email("nonexistent@example.com")
            
            # Assert
            assert result is None

    # =========================================================================
    # find_all tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_find_all_returns_paginated_results(self, repository):
        """Test that find_all returns paginated landlord list."""
        # Arrange
        mock_landlords = [MagicMock() for _ in range(3)]
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=mock_landlords)
        
        with patch("repositories.landlord_repository.LandLord") as MockLandLord:
            MockLandLord.find.return_value = mock_query
            
            # Act
            result = await repository.find_all(offset=0, limit=10)
            
            # Assert
            assert result == mock_landlords
            assert len(result) == 3
            mock_query.skip.assert_called_once_with(0)
            mock_query.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_find_all_returns_empty_list_when_no_users(self, repository):
        """Test that find_all returns empty list when no landlords exist."""
        # Arrange
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[])
        
        with patch("repositories.landlord_repository.LandLord") as MockLandLord:
            MockLandLord.find.return_value = mock_query
            
            # Act
            result = await repository.find_all()
            
            # Assert
            assert result == []

    @pytest.mark.asyncio
    async def test_find_all_uses_default_pagination(self, repository):
        """Test find_all with default pagination values (offset=0, limit=100)."""
        # Arrange
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[])
        
        with patch("repositories.landlord_repository.LandLord") as MockLandLord:
            MockLandLord.find.return_value = mock_query
            
            # Act
            await repository.find_all()
            
            # Assert - default values
            mock_query.skip.assert_called_once_with(0)
            mock_query.limit.assert_called_once_with(100)

    # =========================================================================
    # insert tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_insert_calls_document_insert(self, repository):
        """Test that insert calls the document's insert method."""
        # Arrange
        mock_landlord = MagicMock()
        mock_landlord.insert = AsyncMock(return_value=mock_landlord)
        
        # Act
        result = await repository.insert(mock_landlord)
        
        # Assert
        mock_landlord.insert.assert_called_once()
        assert result == mock_landlord

    # =========================================================================
    # save tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_save_calls_document_save(self, repository):
        """Test that save calls the document's save method."""
        # Arrange
        mock_landlord = MagicMock()
        mock_landlord.save = AsyncMock(return_value=mock_landlord)
        
        # Act
        result = await repository.save(mock_landlord)
        
        # Assert
        mock_landlord.save.assert_called_once()
        assert result == mock_landlord

    # =========================================================================
    # delete tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_calls_document_delete(self, repository):
        """Test that delete calls the document's delete method."""
        # Arrange
        mock_landlord = MagicMock()
        mock_landlord.delete = AsyncMock()
        
        # Act
        await repository.delete(mock_landlord)
        
        # Assert
        mock_landlord.delete.assert_called_once()

    # =========================================================================
    # get_analytics tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_analytics_returns_analytics_data(self, repository):
        """Test that get_analytics returns user analytics."""
        # Arrange
        mock_analytics = [MagicMock()]
        mock_query = MagicMock()
        mock_query.to_list = AsyncMock(return_value=mock_analytics)
        
        with patch("repositories.landlord_repository.UserAnalyticsView") as MockView:
            MockView.find_all.return_value = mock_query
            
            # Act
            result = await repository.get_analytics()
            
            # Assert
            assert result == mock_analytics
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_analytics_returns_empty_list_when_no_data(self, repository):
        """Test that get_analytics returns empty list when no analytics data."""
        # Arrange
        mock_query = MagicMock()
        mock_query.to_list = AsyncMock(return_value=[])
        
        with patch("repositories.landlord_repository.UserAnalyticsView") as MockView:
            MockView.find_all.return_value = mock_query
            
            # Act
            result = await repository.get_analytics()
            
            # Assert
            assert result == []


class TestGetLandLordRepository:
    """Test cases for get_landlord_repository factory function."""

    def test_returns_repository_instance(self):
        """Test that get_landlord_repository returns a LandLordRepository instance."""
        # Clear the cache before testing
        get_landlord_repository.cache_clear()
        
        result = get_landlord_repository()
        
        assert isinstance(result, LandLordRepository)

    def test_returns_cached_instance(self):
        """Test that get_landlord_repository returns the same cached instance."""
        get_landlord_repository.cache_clear()
        
        instance1 = get_landlord_repository()
        instance2 = get_landlord_repository()
        
        assert instance1 is instance2
