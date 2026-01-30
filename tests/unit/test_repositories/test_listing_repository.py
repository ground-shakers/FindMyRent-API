"""Unit tests for ListingRepository.

These tests use mock patching to test repository methods without requiring
a real MongoDB connection or Beanie initialization.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from beanie import PydanticObjectId

from repositories.listing_repository import ListingRepository, get_listing_repository


class TestListingRepository:
    """Test cases for ListingRepository."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository instance for each test."""
        return ListingRepository()

    # =========================================================================
    # get_by_id tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_by_id_returns_listing_when_found(self, repository):
        """Test that get_by_id returns a listing when found."""
        # Arrange
        listing_id = "507f1f77bcf86cd799439011"
        mock_listing = MagicMock()
        mock_listing.id = PydanticObjectId(listing_id)
        
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.get = AsyncMock(return_value=mock_listing)
            
            # Act
            result = await repository.get_by_id(listing_id)
            
            # Assert
            assert result == mock_listing
            MockListing.get.assert_called_once_with(PydanticObjectId(listing_id))

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self, repository):
        """Test that get_by_id returns None when listing is not found."""
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.get = AsyncMock(return_value=None)
            
            # Act
            result = await repository.get_by_id("507f1f77bcf86cd799439011")
            
            # Assert
            assert result is None

    # =========================================================================
    # find_by_landlord_and_id tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_find_by_landlord_and_id_returns_listing(self, repository):
        """Test finding a listing by landlord ID and listing ID."""
        # Arrange
        mock_listing = MagicMock()
        mock_listing.id = PydanticObjectId("507f1f77bcf86cd799439011")
        
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find_one = AsyncMock(return_value=mock_listing)
            
            # Act
            result = await repository.find_by_landlord_and_id(
                landlord_id="landlord123",
                listing_id="507f1f77bcf86cd799439011"
            )
            
            # Assert
            assert result == mock_listing
            MockListing.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_landlord_and_id_returns_none_when_not_owner(self, repository):
        """Test that find_by_landlord_and_id returns None if user doesn't own listing."""
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find_one = AsyncMock(return_value=None)
            
            # Act
            result = await repository.find_by_landlord_and_id(
                landlord_id="different_landlord",
                listing_id="507f1f77bcf86cd799439011"
            )
            
            # Assert
            assert result is None

    # =========================================================================
    # find_verified_by_id tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_find_verified_by_id_returns_verified_listing(self, repository):
        """Test finding a verified listing by ID."""
        # Arrange
        mock_listing = MagicMock()
        mock_listing.verified = True
        
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find_one = AsyncMock(return_value=mock_listing)
            
            # Act
            result = await repository.find_verified_by_id("507f1f77bcf86cd799439011")
            
            # Assert
            assert result == mock_listing

    @pytest.mark.asyncio
    async def test_find_verified_by_id_returns_none_for_unverified(self, repository):
        """Test that find_verified_by_id returns None for unverified listings."""
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find_one = AsyncMock(return_value=None)
            
            # Act
            result = await repository.find_verified_by_id("507f1f77bcf86cd799439011")
            
            # Assert
            assert result is None

    # =========================================================================
    # find_by_landlord tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_find_by_landlord_returns_landlord_listings(self, repository):
        """Test finding all listings for a landlord."""
        # Arrange
        mock_listings = [MagicMock(), MagicMock()]
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=mock_listings)
        
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find.return_value = mock_query
            
            # Act
            result = await repository.find_by_landlord(landlord_id="landlord123")
            
            # Assert
            assert len(result) == 2
            MockListing.find.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_by_landlord_returns_empty_when_no_listings(self, repository):
        """Test that find_by_landlord returns empty list when landlord has no listings."""
        # Arrange
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[])
        
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find.return_value = mock_query
            
            # Act
            result = await repository.find_by_landlord(landlord_id="landlord123")
            
            # Assert
            assert result == []

    # =========================================================================
    # find_verified tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_find_verified_returns_verified_listings(self, repository):
        """Test finding all verified listings."""
        # Arrange
        mock_listings = [MagicMock(), MagicMock()]
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=mock_listings)
        
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find_many.return_value = mock_query
            
            # Act
            result = await repository.find_verified()
            
            # Assert
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_find_verified_with_pagination(self, repository):
        """Test find_verified with custom pagination."""
        # Arrange
        mock_query = MagicMock()
        mock_query.skip.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.to_list = AsyncMock(return_value=[])
        
        with patch("repositories.listing_repository.Listing") as MockListing:
            MockListing.find_many.return_value = mock_query
            
            # Act
            await repository.find_verified(offset=10, limit=5)
            
            # Assert
            mock_query.skip.assert_called_once_with(10)
            mock_query.limit.assert_called_once_with(5)

    # =========================================================================
    # save tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_save_calls_document_save(self, repository):
        """Test that save calls the document's save method."""
        # Arrange
        mock_listing = MagicMock()
        mock_listing.save = AsyncMock(return_value=mock_listing)
        
        # Act
        result = await repository.save(mock_listing)
        
        # Assert
        mock_listing.save.assert_called_once()
        assert result == mock_listing

    # =========================================================================
    # delete tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_calls_document_delete(self, repository):
        """Test that delete calls the document's delete method."""
        # Arrange
        mock_listing = MagicMock()
        mock_listing.delete = AsyncMock()
        
        # Act
        await repository.delete(mock_listing)
        
        # Assert
        mock_listing.delete.assert_called_once()


class TestGetListingRepository:
    """Test cases for get_listing_repository factory function."""

    def test_returns_repository_instance(self):
        """Test that get_listing_repository returns a ListingRepository instance."""
        get_listing_repository.cache_clear()
        
        result = get_listing_repository()
        
        assert isinstance(result, ListingRepository)

    def test_returns_cached_instance(self):
        """Test that get_listing_repository returns the same cached instance."""
        get_listing_repository.cache_clear()
        
        instance1 = get_listing_repository()
        instance2 = get_listing_repository()
        
        assert instance1 is instance2
