"""Integration tests for User endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from fastapi.responses import JSONResponse

from main import app
from services.user_service import UserService, get_user_service
from services.verification import EmailVerificationService, get_email_verification_service
from security.helpers import get_current_active_user
from schema.users import CreateUserResponse, GetUserResponse, UpdateUserResponse, UserAnalyticsResponse
from models.users import User, LandLord, Admin
from models.helpers import UserType
from beanie import PydanticObjectId


# Test data
VALID_USER_ID = "507f1f77bcf86cd799439011"


class TestCreateUser:
    """Tests for POST /api/v1/users endpoint."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, async_client):
        """Test successful user creation returns CreateUserResponse."""
        # Arrange - create_user returns CreateUserResponse on success
        mock_response = CreateUserResponse(
            message="User created successfully",
            email="newuser@example.com",
            expires_in_minutes=10,
            user_id=VALID_USER_ID
        )
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.create_user = AsyncMock(return_value=mock_response)
        
        mock_verification_service = MagicMock(spec=EmailVerificationService)
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        app.dependency_overrides[get_email_verification_service] = lambda: mock_verification_service
        
        # Act
        response = await async_client.post(
            "/api/v1/users",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "newuser@example.com",
                "phone_number": "+1234567890",
                "password": "SecurePass123!",
                "verify_password": "SecurePass123!",
                "date_of_birth": {"day": 15, "month": 6, "year": 1990},
                "gender": "male"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["message"] == "User created successfully"
        assert data["email"] == "newuser@example.com"
        assert "userId" in data or "user_id" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, async_client):
        """Test user creation with duplicate email returns 409 Conflict."""
        # Arrange - service returns JSONResponse for duplicate
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.create_user = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A user with this email already exists"}
        ))
        
        mock_verification_service = MagicMock(spec=EmailVerificationService)
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        app.dependency_overrides[get_email_verification_service] = lambda: mock_verification_service
        
        # Act
        response = await async_client.post(
            "/api/v1/users",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "existing@example.com",
                "phone_number": "+1234567890",
                "password": "SecurePass123!",
                "verify_password": "SecurePass123!",
                "date_of_birth": {"day": 15, "month": 6, "year": 1990},
                "gender": "male"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["detail"] == "A user with this email already exists"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_user_invalid_email_format(self, async_client):
        """Test user creation with invalid email format returns 422."""
        # Act
        response = await async_client.post(
            "/api/v1/users",
            json={
                "first_name": "John",
                "last_name": "Doe",
                "email": "invalid-email",
                "phone_number": "+1234567890",
                "password": "SecurePass123!",
                "verify_password": "SecurePass123!",
                "date_of_birth": {"day": 15, "month": 6, "year": 1990},
                "gender": "male"
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_create_user_missing_required_field(self, async_client):
        """Test user creation with missing required field returns 422."""
        # Act
        response = await async_client.post(
            "/api/v1/users",
            json={
                "first_name": "John",
                # Missing other required fields
            }
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestGetUser:
    """Tests for GET /api/v1/users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_user_success(self, async_client, override_auth_landlord):
        """Test successful user retrieval returns GetUserResponse."""
        # Arrange
        mock_user = override_auth_landlord()
        
        mock_response = MagicMock(spec=GetUserResponse)
        mock_response.model_dump.return_value = {
            "firstName": "John",
            "lastName": "Doe",
            "email": "john@example.com"
        }
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_user = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.get(f"/api/v1/users/{VALID_USER_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, async_client, override_auth_admin):
        """Test user retrieval when user doesn't exist returns 404."""
        # Arrange
        mock_user = override_auth_admin()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_user = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"User with ID {VALID_USER_ID} not found"}
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.get(f"/api/v1/users/{VALID_USER_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_user_invalid_id_format(self, async_client, override_auth_landlord):
        """Test user retrieval with invalid ID format (not 24 chars) returns 422."""
        # Arrange
        override_auth_landlord()
        
        mock_user_service = MagicMock(spec=UserService)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act - ID must be 24 characters
        response = await async_client.get("/api/v1/users/invalid_short_id")
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        
        # Cleanup
        app.dependency_overrides.clear()


class TestGetUsers:
    """Tests for GET /api/v1/users endpoint."""

    @pytest.mark.asyncio
    async def test_get_users_success(self, async_client, override_auth_admin):
        """Test successful users list retrieval returns JSONResponse with message and users."""
        # Arrange
        override_auth_admin()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_users = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Users retrieved successfully",
                "users": []
            }
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.get("/api/v1/users")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Users retrieved successfully"
        assert "users" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_users_with_pagination(self, async_client, override_auth_admin):
        """Test users retrieval accepts pagination parameters."""
        # Arrange
        override_auth_admin()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_users = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Users retrieved successfully", "users": []}
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.get("/api/v1/users?offset=10&limit=20")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_users_invalid_pagination_negative_offset(self, async_client, override_auth_admin):
        """Test users retrieval with invalid pagination (negative offset) returns 422."""
        # Arrange
        override_auth_admin()
        
        mock_user_service = MagicMock(spec=UserService)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.get("/api/v1/users?offset=-1")
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        
        # Cleanup
        app.dependency_overrides.clear()


class TestDeleteUser:
    """Tests for DELETE /api/v1/users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, async_client, override_auth_admin):
        """Test successful user deletion returns 200 with message."""
        # Arrange
        override_auth_admin()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.delete_user = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": f"User with ID {VALID_USER_ID} deleted successfully"}
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.delete(f"/api/v1/users/{VALID_USER_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.json()["message"]
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, async_client, override_auth_admin):
        """Test deletion of non-existent user returns 404."""
        # Arrange
        override_auth_admin()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.delete_user = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"User with ID {VALID_USER_ID} not found"}
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.delete(f"/api/v1/users/{VALID_USER_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_user_forbidden(self, async_client, override_auth_landlord):
        """Test that non-admin users cannot delete other users returns 403."""
        # Arrange
        override_auth_landlord()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.delete_user = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Cannot delete user account"}
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.delete(f"/api/v1/users/{VALID_USER_ID}")
        
        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Cleanup
        app.dependency_overrides.clear()


class TestUpdateUser:
    """Tests for PUT /api/v1/users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_user_success(self, async_client, override_auth_landlord):
        """Test successful user update returns UpdateUserResponse."""
        # Arrange
        override_auth_landlord()
        
        mock_response = UpdateUserResponse(
            message="User updated successfully",
            user={"id": VALID_USER_ID, "first_name": "Jane"}
        )
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.update_user = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.put(
            f"/api/v1/users/{VALID_USER_ID}",
            json={"first_name": "Jane"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "User updated successfully"
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_user_no_fields_provided(self, async_client, override_auth_landlord):
        """Test update with no fields provided returns 400."""
        # Arrange
        override_auth_landlord()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.update_user = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "No fields provided to update"}
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.put(
            f"/api/v1/users/{VALID_USER_ID}",
            json={}
        )
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_user_invalid_gender(self, async_client, override_auth_landlord):
        """Test user update with invalid gender returns 422."""
        # Arrange
        override_auth_landlord()
        
        mock_user_service = MagicMock(spec=UserService)
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.put(
            f"/api/v1/users/{VALID_USER_ID}",
            json={"gender": "invalid"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        
        # Cleanup
        app.dependency_overrides.clear()


class TestGetAnalytics:
    """Tests for GET /api/v1/users/analytics endpoint."""

    @pytest.mark.asyncio
    async def test_get_analytics_success(self, async_client, override_auth_admin):
        """Test successful analytics retrieval returns UserAnalyticsResponse."""
        # Arrange
        override_auth_admin()
        
        # Create mock that can be serialized
        mock_analytics = {
            "total_users": 100,
            "verified_kyc_users": 75,
            "unverified_kyc_users": 25,
            "kyc_completion_rate": 0.75,
            "landlords_with_properties": 50,
            "landlords_without_properties": 50,
            "top_landlord_id": None,
            "average_age": 35.5,
            "age_18_25": 20,
            "age_26_35": 30,
            "age_36_45": 25,
            "age_46_60": 15,
            "age_60_plus": 10,
            "users_today": 5,
            "users_this_month": 20,
            "male_users": 60,
            "female_users": 40,
            "male_landlords": 55,
            "female_landlords": 45
        }
        
        mock_response = UserAnalyticsResponse(**mock_analytics)
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_analytics_for_users = AsyncMock(return_value=mock_response)
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.get("/api/v1/users/stats/analytics")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "totalUsers" in data or "total_users" in data
        
        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_analytics_no_data(self, async_client, override_auth_admin):
        """Test analytics when no data available returns 404."""
        # Arrange
        override_auth_admin()
        
        mock_user_service = MagicMock(spec=UserService)
        mock_user_service.get_analytics_for_users = AsyncMock(return_value=JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "No analytics data available"}
        ))
        
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        
        # Act
        response = await async_client.get("/api/v1/users/stats/analytics")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Cleanup
        app.dependency_overrides.clear()
