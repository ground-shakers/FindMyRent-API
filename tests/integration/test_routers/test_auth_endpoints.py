"""Integration tests for Auth endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from fastapi.responses import JSONResponse

from main import app
from services.auth_service import AuthService, get_auth_service
from services.verification import EmailVerificationService, get_email_verification_service
from security.refresh_token import SecureRefreshTokenService, get_secure_refresh_token_service
from schema.verification import EmailVerificationResponse, VerifiedEmailResponse
from schema.security import TokenPair, ForgotPasswordResponse, ResetPasswordResponse
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


# =============================================================================
# Password Reset Tests
# =============================================================================


class TestForgotPassword:
    """Tests for POST /api/v1/auth/forgot-password endpoint."""

    @pytest.mark.asyncio
    async def test_forgot_password_success(self, async_client):
        """Test successful forgot password request returns ForgotPasswordResponse."""
        # Arrange
        mock_response = ForgotPasswordResponse(
            message="If an account with this email exists, a password reset link has been sent.",
            email="test@example.com"
        )
        
        mock_service = MagicMock(spec=AuthService)
        mock_service.forgot_password = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "password reset link" in data["message"].lower()
        assert data["email"] == "test@example.com"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_forgot_password_invalid_email_format(self, async_client):
        """Test forgot password with invalid email format returns validation error."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "not-an-email"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_forgot_password_missing_email(self, async_client):
        """Test forgot password with missing email returns validation error."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_forgot_password_empty_email(self, async_client):
        """Test forgot password with empty email returns validation error."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": ""}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_forgot_password_service_unavailable(self, async_client):
        """Test forgot password when service is unavailable returns 503."""
        # Arrange
        mock_service = MagicMock(spec=AuthService)
        mock_service.forgot_password = AsyncMock(
            return_value=JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service temporarily unavailable"}
            )
        )
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        
        # Cleanup
        app.dependency_overrides.clear()


class TestResetPassword:
    """Tests for POST /api/v1/auth/reset-password endpoint."""

    @pytest.mark.asyncio
    async def test_reset_password_success(self, async_client):
        """Test successful password reset returns ResetPasswordResponse."""
        # Arrange
        mock_response = ResetPasswordResponse(
            message="Password has been reset successfully. You can now log in with your new password."
        )
        
        mock_service = MagicMock(spec=AuthService)
        mock_service.reset_password = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        # Valid 64-character token
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "NewSecureP@ss123",
                "confirm_password": "NewSecureP@ss123"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "reset successfully" in data["message"].lower()
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_reset_password_token_too_short(self, async_client):
        """Test reset password with token shorter than 64 characters."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "short_token",
                "password": "NewSecureP@ss123",
                "confirm_password": "NewSecureP@ss123"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_missing_token(self, async_client):
        """Test reset password with missing token returns validation error."""
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "password": "NewSecureP@ss123",
                "confirm_password": "NewSecureP@ss123"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_passwords_dont_match(self, async_client):
        """Test reset password with mismatched passwords returns validation error."""
        # Valid 64-character token
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "NewSecureP@ss123",
                "confirm_password": "DifferentP@ss456"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_weak_password_no_uppercase(self, async_client):
        """Test reset password with password missing uppercase letter."""
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "weakpassword123!",
                "confirm_password": "weakpassword123!"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_weak_password_no_lowercase(self, async_client):
        """Test reset password with password missing lowercase letter."""
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "WEAKPASSWORD123!",
                "confirm_password": "WEAKPASSWORD123!"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_weak_password_no_number(self, async_client):
        """Test reset password with password missing number."""
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "WeakPassword!",
                "confirm_password": "WeakPassword!"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_weak_password_no_special_char(self, async_client):
        """Test reset password with password missing special character."""
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "WeakPassword123",
                "confirm_password": "WeakPassword123"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_password_too_short(self, async_client):
        """Test reset password with password shorter than 8 characters."""
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "Sh0rt!",
                "confirm_password": "Sh0rt!"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, async_client):
        """Test reset password with invalid/expired token returns error."""
        # Arrange
        mock_service = MagicMock(spec=AuthService)
        mock_service.reset_password = AsyncMock(
            return_value=JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid or expired password reset token"}
            )
        )
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "NewSecureP@ss123",
                "confirm_password": "NewSecureP@ss123"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in response.json()["detail"].lower()
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_reset_password_service_unavailable(self, async_client):
        """Test reset password when service is unavailable returns 503."""
        # Arrange
        mock_service = MagicMock(spec=AuthService)
        mock_service.reset_password = AsyncMock(
            return_value=JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service temporarily unavailable"}
            )
        )
        
        app.dependency_overrides[get_auth_service] = lambda: mock_service
        
        valid_token = "a" * 64
        
        # Act
        response = await async_client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": valid_token,
                "password": "NewSecureP@ss123",
                "confirm_password": "NewSecureP@ss123"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        
        # Cleanup
        app.dependency_overrides.clear()

