"""Integration tests for Favorites endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import status
from fastapi.responses import JSONResponse

from main import app
from services.favorites_service import FavoritesService, get_favorites_service


# Test data
VALID_LISTING_ID = "507f1f77bcf86cd799439011"


class TestAddToFavorites:
    """Tests for POST /api/v1/favorites/{listing_id} endpoint."""

    @pytest.mark.asyncio
    async def test_add_favorite_success(self, async_client, override_auth_landlord):
        """Test successfully adding a listing to favorites."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.add_favorite = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Listing added to favorites",
                "listing_id": VALID_LISTING_ID,
                "total_favorites": 1
            }
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.post(f"/api/v1/favorites/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["message"] == "Listing added to favorites"
        assert data["listing_id"] == VALID_LISTING_ID
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_add_favorite_not_found(self, async_client, override_auth_landlord):
        """Test adding a non-existent listing returns 404."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.add_favorite = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Listing not found"}
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.post(f"/api/v1/favorites/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_add_favorite_already_exists(self, async_client, override_auth_landlord):
        """Test adding an already favorited listing returns 409."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.add_favorite = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Listing already in favorites"}
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.post(f"/api/v1/favorites/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        
        # Cleanup
        app.dependency_overrides.clear()


class TestRemoveFromFavorites:
    """Tests for DELETE /api/v1/favorites/{listing_id} endpoint."""

    @pytest.mark.asyncio
    async def test_remove_favorite_success(self, async_client, override_auth_landlord):
        """Test successfully removing a listing from favorites."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.remove_favorite = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Listing removed from favorites",
                "listing_id": VALID_LISTING_ID,
                "total_favorites": 0
            }
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.delete(f"/api/v1/favorites/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Listing removed from favorites"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_remove_favorite_not_in_favorites(self, async_client, override_auth_landlord):
        """Test removing a listing not in favorites returns 404."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.remove_favorite = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Listing not in favorites"}
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.delete(f"/api/v1/favorites/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Cleanup
        app.dependency_overrides.clear()


class TestGetFavorites:
    """Tests for GET /api/v1/favorites endpoint."""

    @pytest.mark.asyncio
    async def test_get_favorites_success(self, async_client, override_auth_landlord):
        """Test getting favorites returns list with pagination."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.get_favorites = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "favorites": [{"id": VALID_LISTING_ID}],
                "total": 1,
                "offset": 0,
                "limit": 20,
                "has_more": False
            }
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.get("/api/v1/favorites")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "favorites" in data
        assert "total" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_favorites_empty(self, async_client, override_auth_landlord):
        """Test getting favorites when none exist returns empty array."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.get_favorites = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "favorites": [],
                "total": 0,
                "offset": 0,
                "limit": 20,
                "has_more": False
            }
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.get("/api/v1/favorites")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["favorites"] == []
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_favorites_with_pagination(self, async_client, override_auth_landlord):
        """Test getting favorites respects pagination params."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.get_favorites = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "favorites": [],
                "total": 50,
                "offset": 10,
                "limit": 5,
                "has_more": True
            }
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.get("/api/v1/favorites?offset=10&limit=5")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["offset"] == 10
        assert data["limit"] == 5
        
        # Cleanup
        app.dependency_overrides.clear()


class TestCheckIsFavorite:
    """Tests for GET /api/v1/favorites/{listing_id}/check endpoint."""

    @pytest.mark.asyncio
    async def test_check_is_favorite_true(self, async_client, override_auth_landlord):
        """Test checking a favorited listing returns true."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.check_is_favorite = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "listing_id": VALID_LISTING_ID,
                "is_favorite": True
            }
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.get(f"/api/v1/favorites/{VALID_LISTING_ID}/check")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_favorite"] == True
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_check_is_favorite_false(self, async_client, override_auth_landlord):
        """Test checking a non-favorited listing returns false."""
        # Arrange
        override_auth_landlord()
        
        mock_favorites_service = MagicMock(spec=FavoritesService)
        mock_favorites_service.check_is_favorite = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "listing_id": VALID_LISTING_ID,
                "is_favorite": False
            }
        ))
        
        app.dependency_overrides[get_favorites_service] = lambda: mock_favorites_service
        
        # Act
        response = await async_client.get(f"/api/v1/favorites/{VALID_LISTING_ID}/check")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_favorite"] == False
        
        # Cleanup
        app.dependency_overrides.clear()
