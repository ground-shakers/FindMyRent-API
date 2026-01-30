"""Integration tests for Listing endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from fastapi.responses import JSONResponse

from main import app
from services.listings_service import ListingsService, get_listings_service
from services.email import EmailService, get_email_service
from services.template import TemplateService, get_template_service
from security.helpers import get_current_active_user


# Test data
VALID_LISTING_ID = "507f1f77bcf86cd799439011"
VALID_USER_ID = "507f1f77bcf86cd799439012"


class TestGetPropertyListing:
    """Tests for GET /api/v1/listings/{listing_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_listing_success(self, async_client, override_auth_landlord):
        """Test successful listing retrieval returns JSON with message and listing."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.get_property_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Property listing retrieved successfully",
                "listing": {
                    "id": VALID_LISTING_ID, 
                    "description": "Test listing",
                    "price": 1500.00
                }
            }
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.get(f"/api/v1/listings/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Property listing retrieved successfully"
        assert "listing" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_listing_not_found(self, async_client, override_auth_landlord):
        """Test listing retrieval when listing doesn't exist returns 404."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.get_property_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Property listing not found"}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.get(f"/api/v1/listings/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Property listing not found"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_listing_invalid_id_format(self, async_client, override_auth_landlord):
        """Test listing retrieval with invalid ID format (not 24 chars) returns 422."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act - ID must be valid ObjectId (24 hex chars)
        response = await async_client.get("/api/v1/listings/invalid")
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_listing_with_owned_collection(self, async_client, override_auth_landlord):
        """Test listing retrieval from owned collection."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.get_property_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Property listing retrieved successfully",
                "listing": {"id": VALID_LISTING_ID}
            }
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.get(
            f"/api/v1/listings/{VALID_LISTING_ID}?collection=owned"
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()


class TestGetPropertyListings:
    """Tests for GET /api/v1/listings endpoint."""

    @pytest.mark.asyncio
    async def test_get_listings_success(self, async_client, override_auth_landlord):
        """Test successful listings retrieval returns JSON with listings array."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.get_property_listings = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"listings": []}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.get("/api/v1/listings")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "listings" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_listings_with_pagination(self, async_client, override_auth_landlord):
        """Test listings retrieval accepts pagination parameters."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.get_property_listings = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"listings": []}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.get("/api/v1/listings?offset=10&limit=50")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_listings_owned_collection(self, async_client, override_auth_landlord):
        """Test retrieving user's own listings with collection=owned."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.get_property_listings = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"listings": []}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.get("/api/v1/listings?collection=owned")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_listings_empty_returns_404(self, async_client, override_auth_landlord):
        """Test listings retrieval when no listings exist returns 404."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.get_property_listings = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "No property listings found"}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.get("/api/v1/listings")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "No property listings found"
        
        # Cleanup
        app.dependency_overrides.clear()


class TestVerifyListing:
    """Tests for POST /api/v1/listings/verify/{listing_id} endpoint."""

    @pytest.mark.asyncio
    async def test_verify_listing_approve_success(self, async_client, override_auth_admin):
        """Test successful listing approval returns message and listing."""
        # Arrange
        override_auth_admin()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.verify_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Property listing verification status updated successfully",
                "listing": {"id": VALID_LISTING_ID, "verified": True}
            }
        ))
        
        mock_email_service = MagicMock(spec=EmailService)
        mock_template_service = MagicMock(spec=TemplateService)
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        app.dependency_overrides[get_email_service] = lambda: mock_email_service
        app.dependency_overrides[get_template_service] = lambda: mock_template_service
        
        # Act - verified is a query parameter, not JSON body
        response = await async_client.post(
            f"/api/v1/listings/verify/{VALID_LISTING_ID}?verified=true"
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Property listing verification status updated successfully"
        assert "listing" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_verify_listing_reject_success(self, async_client, override_auth_admin):
        """Test successful listing rejection returns message and listing."""
        # Arrange
        override_auth_admin()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.verify_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Property listing verification status updated successfully",
                "listing": {"id": VALID_LISTING_ID, "verified": False}
            }
        ))
        
        mock_email_service = MagicMock(spec=EmailService)
        mock_template_service = MagicMock(spec=TemplateService)
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        app.dependency_overrides[get_email_service] = lambda: mock_email_service
        app.dependency_overrides[get_template_service] = lambda: mock_template_service
        
        # Act - verified is a query parameter, not JSON body
        response = await async_client.post(
            f"/api/v1/listings/verify/{VALID_LISTING_ID}?verified=false"
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_verify_listing_not_found(self, async_client, override_auth_admin):
        """Test verifying non-existent listing returns 404."""
        # Arrange
        override_auth_admin()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.verify_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Property listing not found"}
        ))
        
        mock_email_service = MagicMock(spec=EmailService)
        mock_template_service = MagicMock(spec=TemplateService)
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        app.dependency_overrides[get_email_service] = lambda: mock_email_service
        app.dependency_overrides[get_template_service] = lambda: mock_template_service
        
        # Act - verified is a query parameter, not JSON body
        response = await async_client.post(
            f"/api/v1/listings/verify/{VALID_LISTING_ID}?verified=true"
        )
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Property listing not found"
        
        # Cleanup
        app.dependency_overrides.clear()


class TestDeletePropertyListing:
    """Tests for DELETE /api/v1/listings/{listing_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_listing_success(self, async_client, override_auth_landlord):
        """Test successful listing deletion returns 204 with message."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.delete_property_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content={"message": "Property listing deleted successfully"}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.delete(f"/api/v1/listings/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_listing_not_found(self, async_client, override_auth_landlord):
        """Test deleting non-existent listing returns 404."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.delete_property_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Property listing not found"}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.delete(f"/api/v1/listings/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Property listing not found"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_listing_invalid_id(self, async_client, override_auth_landlord):
        """Test deleting listing with invalid ID format returns 422."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.delete("/api/v1/listings/short")
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_listing_service_unavailable(self, async_client, override_auth_landlord):
        """Test deleting listing when service unavailable returns 503."""
        # Arrange
        override_auth_landlord()
        
        mock_listings_service = MagicMock(spec=ListingsService)
        mock_listings_service.delete_property_listing = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service unavailable. Please try again later."}
        ))
        
        app.dependency_overrides[get_listings_service] = lambda: mock_listings_service
        
        # Act
        response = await async_client.delete(f"/api/v1/listings/{VALID_LISTING_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        
        # Cleanup
        app.dependency_overrides.clear()
