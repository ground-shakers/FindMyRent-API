"""Integration tests for Auth endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status

from main import app
from services.auth_service import AuthService, get_auth_service
from services.verification import EmailVerificationService, get_email_verification_service
from security.refresh_token import SecureRefreshTokenService, get_secure_refresh_token_service
from schema.verification import EmailVerificationResponse, VerifiedEmailResponse
from schema.security import TokenPair
from schema.users import UserInDB


class TestResendVerificationCode:
    """Tests for POST /api/v1/auth/verification/email/send endpoint."""

    @pytest.mark.asyncio
    async def test_send_verification_code_success(self, async_client):
        """Test successful verification code sending returns EmailVerificationResponse."""
        # Arrange
        mock_response = EmailVerificationResponse(
            message="Verification code sent successfully",
            email="test@example.com",
            expires_in_minutes=10
        )
        
        mock_service = MagicMock(spec=AuthService)
        mock_service.resend_verification_code = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/verification/email/send",
            json={"email": "test@example.com"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Verification code sent successfully"
        assert data["email"] == "test@example.com"
        assert data["expires_in_minutes"] == 10
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_send_verification_code_invalid_email_format(self, async_client):
        """Test verification code sending with invalid email format."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/verification/email/send",
            json={"email": "invalid-email"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_send_verification_code_empty_email(self, async_client):
        """Test verification code sending with empty email."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/verification/email/send",
            json={}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestVerifyEmailCode:
    """Tests for POST /api/v1/auth/verification/email endpoint."""

    @pytest.mark.asyncio
    async def test_verify_email_success(self, async_client):
        """Test successful email verification returns VerifiedEmailResponse."""
        # Arrange
        mock_user_in_db = UserInDB(
            id="507f1f77bcf86cd799439011",
            first_name="John",
            last_name="Doe",
            email="test@example.com",
            phone_number="+1234567890",
            user_type="landlord"
        )
        mock_response = VerifiedEmailResponse(
            message="Email verified successfully",
            user=mock_user_in_db
        )
        
        mock_service = MagicMock(spec=AuthService)
        mock_service.verify_email_code = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/verification/email",
            json={"email": "test@example.com", "code": "123456"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Email verified successfully"
        assert "user" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_verify_email_missing_code(self, async_client):
        """Test email verification with missing code."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/verification/email",
            json={"email": "test@example.com"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_verify_email_non_numeric_code(self, async_client):
        """Test email verification with non-numeric code (schema validation)."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/verification/email",
            json={"email": "test@example.com", "code": "abcdef"}
        )
        
        # Assert - Should fail schema validation (400 for HTTPException in validator)
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_CONTENT]

    @pytest.mark.asyncio
    async def test_verify_email_code_wrong_length(self, async_client):
        """Test email verification with code that's not 6 characters."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/verification/email",
            json={"email": "test@example.com", "code": "123"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestLogin:
    """Tests for POST /api/v1/auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, async_client):
        """Test successful login returns TokenPair with access and refresh tokens."""
        # Arrange
        mock_token_pair = TokenPair(
            access_token="mock_access_token",
            refresh_token="mock_refresh_token",
            token_type="Bearer",
            expires_in=1800
        )
        
        mock_service = MagicMock(spec=AuthService)
        mock_service.login_for_access_token = AsyncMock(return_value=mock_token_pair)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "test@example.com", "password": "SecurePass123!"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["access_token"] == "mock_access_token"
        assert data["refresh_token"] == "mock_refresh_token"
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 1800
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_missing_username(self, async_client):
        """Test login with missing username returns validation error."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/login",
            data={"password": "password123"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_login_missing_password(self, async_client):
        """Test login with missing password returns validation error."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/login",
            data={"username": "test@example.com"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, async_client):
        """Test successful token refresh returns new TokenPair."""
        # Arrange
        mock_token_pair = TokenPair(
            access_token="new_access_token",
            refresh_token="new_refresh_token",
            token_type="Bearer",
            expires_in=1800
        )
        
        mock_auth_service = MagicMock(spec=AuthService)
        mock_auth_service.refresh_access_token = AsyncMock(return_value=mock_token_pair)
        
        mock_secure_service = MagicMock(spec=SecureRefreshTokenService)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_secure_refresh_token_service] = lambda: mock_secure_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid_refresh_token"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["access_token"] == "new_access_token"
        assert data["refresh_token"] == "new_refresh_token"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_refresh_token_missing_token(self, async_client):
        """Test refresh with missing token returns validation error."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestLogout:
    """Tests for POST /api/v1/auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, async_client):
        """Test successful logout returns success message dict."""
        # Arrange - logout returns plain dict, not JSONResponse
        mock_auth_service = MagicMock(spec=AuthService)
        mock_auth_service.logout = AsyncMock(return_value={"message": "Successfully logged out"})
        
        mock_secure_service = MagicMock(spec=SecureRefreshTokenService)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_secure_refresh_token_service] = lambda: mock_secure_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "valid_refresh_token"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Successfully logged out"
        
        # Cleanup
        app.dependency_overrides.clear()


class TestLogoutAllDevices:
    """Tests for POST /api/v1/auth/logout-all endpoint."""

    @pytest.mark.asyncio
    async def test_logout_all_success(self, async_client):
        """Test successful logout from all devices returns success message dict."""
        # Arrange - logout_all_devices returns plain dict
        mock_auth_service = MagicMock(spec=AuthService)
        mock_auth_service.logout_all_devices = AsyncMock(
            return_value={"message": "Successfully logged out from all devices"}
        )
        
        mock_secure_service = MagicMock(spec=SecureRefreshTokenService)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_secure_refresh_token_service] = lambda: mock_secure_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/logout-all",
            json={"refresh_token": "valid_refresh_token"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Successfully logged out from all devices"
        
        # Cleanup
        app.dependency_overrides.clear()
