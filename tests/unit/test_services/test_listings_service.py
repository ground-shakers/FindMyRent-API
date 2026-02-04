"""Unit tests for ListingsService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from fastapi.responses import JSONResponse
from services.listings_service import ListingsService
from schema.listings import ListingAnalyticsResponse

class TestListingsService:
    """Tests for ListingsService."""

    @pytest.mark.asyncio
    async def test_get_analytics_for_listings_success(self):
        """Test analytics retrieval returns response model."""
        # Arrange
        with patch("services.listings_service.get_listing_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_get_repo.return_value = mock_repo
            
            service = ListingsService()
            
            mock_view_data = {
                "totalListings": 10,
                "verifiedListings": 5,
                "unverifiedListings": 5,
                "rejectedListings": 0,
                "availableListings": 8,
                "averagePrice": 1000.0,
                "minPrice": 500.0,
                "maxPrice": 1500.0,
                "singleListings": 2,
                "sharedListings": 2,
                "studioListings": 2,
                "flatListings": 2,
                "roomListings": 2,
                "listingsToday": 1,
                "listingsThisMonth": 5
            }
            
            # Mock the view object
            mock_view = MagicMock()
            mock_view.model_dump.return_value = mock_view_data
            
            mock_repo.get_analytics = AsyncMock(return_value=[mock_view])
            
            # Act
            result = await service.get_analytics_for_listings()
            
            # Assert
            assert isinstance(result, ListingAnalyticsResponse)
            assert result.total_listings == 10
            assert result.average_price == 1000.0

    @pytest.mark.asyncio
    async def test_get_analytics_for_listings_no_data(self):
        """Test analytics returns 404 when no data."""
        # Arrange
        with patch("services.listings_service.get_listing_repository") as mock_get_repo:
            mock_repo = MagicMock()
            mock_get_repo.return_value = mock_repo
            
            service = ListingsService()
            
            mock_repo.get_analytics = AsyncMock(return_value=[])
            
            # Act
            result = await service.get_analytics_for_listings()
            
            # Assert
            assert isinstance(result, JSONResponse)
            assert result.status_code == status.HTTP_404_NOT_FOUND
            assert result.body # content exists
