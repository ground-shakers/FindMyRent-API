"""Integration tests for KYC endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from fastapi.responses import JSONResponse

from main import app
from services.kyc_service import KycService, get_kyc_service
from security.helpers import get_current_active_user
from schema.kyc import CreateKYCSessionResponse


# Test data
VALID_SESSION_ID = "kyc_session_123456789"


class TestCreateKYCVerificationSession:
    """Tests for POST /api/v1/kyc/session endpoint."""

    @pytest.mark.asyncio
    async def test_create_session_success(self, async_client, override_auth_landlord):
        """Test successful KYC session creation returns CreateKYCSessionResponse."""
        # Arrange
        override_auth_landlord()
        
        # Create a mock response with all required fields
        mock_response = MagicMock()
        mock_response.session_id = VALID_SESSION_ID
        mock_response.workflow_id = "workflow123"
        mock_response.vendor_data = "507f1f77bcf86cd799439011"
        mock_response.status = "pending"
        mock_response.session_number = 1
        mock_response.session_token = "token123"
        mock_response.callback = None
        mock_response.url = "https://kyc.provider.com/verify/session123"
        mock_response.metadata = None  # Explicitly set to avoid MagicMock auto-attribute
        
        mock_kyc_service = MagicMock(spec=KycService)
        mock_kyc_service.create_kyc_verification_session = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_kyc_service] = lambda: mock_kyc_service
        
        # Act
        response = await async_client.post("/api/v1/kyc/session")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_session_failure(self, async_client, override_auth_landlord):
        """Test KYC session creation failure returns 500 with detail."""
        # Arrange
        override_auth_landlord()
        
        mock_kyc_service = MagicMock(spec=KycService)
        mock_kyc_service.create_kyc_verification_session = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to create KYC session"}
        ))
        
        app.dependency_overrides[get_kyc_service] = lambda: mock_kyc_service
        
        # Act
        response = await async_client.post("/api/v1/kyc/session")
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json()["detail"] == "Failed to create KYC session"
        
        # Cleanup
        app.dependency_overrides.clear()


class TestHandleKYCWebhook:
    """Tests for POST /api/v1/kyc/webhook endpoint."""

    @pytest.mark.asyncio
    async def test_webhook_approved_success(self, async_client):
        """Test successful KYC webhook processing with approved decision."""
        # Arrange
        mock_kyc_service = MagicMock(spec=KycService)
        mock_kyc_service.handle_kyc_webhook = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "KYC data appended without decision"}
        ))
        
        app.dependency_overrides[get_kyc_service] = lambda: mock_kyc_service
        
        # Act
        response = await async_client.post(
            "/api/v1/kyc/webhook",
            json={
                "session_id": VALID_SESSION_ID,
                "status": "completed",
                "vendor_data": "507f1f77bcf86cd799439011",
                "workflow_id": "workflow123",
                "webhook_type": "session.completed",
                "created_at": 1234567890,
                "timestamp": 1234567890
            },
            headers={
                "X-Signature": "valid_signature",
                "X-Timestamp": "1234567890"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_webhook_user_not_found(self, async_client):
        """Test webhook when user is not found returns 404."""
        # Arrange
        mock_kyc_service = MagicMock(spec=KycService)
        mock_kyc_service.handle_kyc_webhook = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "User not found for KYC webhook"}
        ))
        
        app.dependency_overrides[get_kyc_service] = lambda: mock_kyc_service
        
        # Act
        response = await async_client.post(
            "/api/v1/kyc/webhook",
            json={"session_id": "unknown_session", "vendor_data": "invalid_user_id"},
            headers={
                "X-Signature": "signature",
                "X-Timestamp": "1234567890"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found for KYC webhook"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_webhook_without_decision(self, async_client):
        """Test webhook when decision is not present (session in progress)."""
        # Arrange
        mock_kyc_service = MagicMock(spec=KycService)
        mock_kyc_service.handle_kyc_webhook = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "KYC data appended without decision"}
        ))
        
        app.dependency_overrides[get_kyc_service] = lambda: mock_kyc_service
        
        # Act
        response = await async_client.post(
            "/api/v1/kyc/webhook",
            json={
                "session_id": VALID_SESSION_ID,
                "status": "in_progress",
                "vendor_data": "507f1f77bcf86cd799439011"
                # No decision field
            },
            headers={
                "X-Signature": "valid_signature",
                "X-Timestamp": "1234567890"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["detail"] == "KYC data appended without decision"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_webhook_missing_signature_headers(self, async_client):
        """Test webhook with missing signature headers returns 401."""
        # Arrange
        mock_kyc_service = MagicMock(spec=KycService)
        
        # The service raises HTTPException when signature is missing
        from fastapi import HTTPException
        mock_kyc_service.handle_kyc_webhook = AsyncMock(
            side_effect=HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized"
            )
        )
        
        app.dependency_overrides[get_kyc_service] = lambda: mock_kyc_service
        
        # Act - No signature headers
        response = await async_client.post(
            "/api/v1/kyc/webhook",
            json={"session_id": VALID_SESSION_ID}
            # Missing X-Signature and X-Timestamp headers
        )
        
        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        
        # Cleanup
        app.dependency_overrides.clear()
