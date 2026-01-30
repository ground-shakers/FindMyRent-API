"""Unit tests for user schema validation."""

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from schema.users import (
    CreateUserRequest,
    UserDateOfBirth,
    UpdateUserRequest,
    CreateUserResponse,
)


class TestUserDateOfBirth:
    """Test cases for UserDateOfBirth schema validation."""

    def test_valid_date_of_birth(self):
        """Test that valid date of birth passes validation."""
        dob = UserDateOfBirth(day=15, month=6, year=1990)
        
        assert dob.day == 15
        assert dob.month == 6
        assert dob.year == 1990

    def test_underage_user_raises_403_error(self):
        """Test that users under 18 are rejected with 403 status."""
        with pytest.raises(HTTPException) as exc_info:
            UserDateOfBirth(day=1, month=1, year=2020)
        
        assert exc_info.value.status_code == 403
        assert "at least 18 years old" in exc_info.value.detail

    def test_invalid_day_raises_validation_error(self):
        """Test that invalid day value is rejected."""
        with pytest.raises(ValidationError):
            UserDateOfBirth(day=32, month=6, year=1990)

    def test_invalid_month_raises_validation_error(self):
        """Test that invalid month value is rejected."""
        with pytest.raises(ValidationError):
            UserDateOfBirth(day=15, month=13, year=1990)

    def test_day_zero_raises_validation_error(self):
        """Test that day=0 is rejected."""
        with pytest.raises(ValidationError):
            UserDateOfBirth(day=0, month=6, year=1990)

    def test_month_zero_raises_validation_error(self):
        """Test that month=0 is rejected."""
        with pytest.raises(ValidationError):
            UserDateOfBirth(day=15, month=0, year=1990)

    def test_year_before_1900_raises_validation_error(self):
        """Test that year before 1900 is rejected."""
        with pytest.raises(ValidationError):
            UserDateOfBirth(day=15, month=6, year=1899)

    def test_barely_18_years_old_passes(self):
        """Test that a user who is exactly 18 passes validation."""
        from datetime import date
        today = date.today()
        # Calculate date 18 years ago
        dob = UserDateOfBirth(day=today.day, month=today.month, year=today.year - 18)
        assert dob is not None


class TestCreateUserRequest:
    """Test cases for CreateUserRequest schema validation."""

    @pytest.fixture
    def valid_user_data(self):
        """Return valid user creation data."""
        return {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone_number": "+1234567890",
            "password": "SecurePass123!",
            "verify_password": "SecurePass123!",
            "date_of_birth": {"day": 15, "month": 6, "year": 1990},
            "gender": "male"
        }

    def test_valid_user_data_passes_validation(self, valid_user_data):
        """Test that valid user data passes validation."""
        user = CreateUserRequest(**valid_user_data)
        
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.email == "john.doe@example.com"

    def test_password_mismatch_raises_422_error(self, valid_user_data):
        """Test that mismatched passwords are rejected with 422 status."""
        valid_user_data["verify_password"] = "DifferentPass123!"
        
        with pytest.raises(HTTPException) as exc_info:
            CreateUserRequest(**valid_user_data)
        
        assert exc_info.value.status_code == 422
        # The detail is a dict with "message" key
        assert exc_info.value.detail["message"] == "Passwords do not match"

    def test_weak_password_no_uppercase_raises_422_error(self, valid_user_data):
        """Test that password without uppercase is rejected with 422 status."""
        valid_user_data["password"] = "securepass123!"
        valid_user_data["verify_password"] = "securepass123!"
        
        with pytest.raises(HTTPException) as exc_info:
            CreateUserRequest(**valid_user_data)
        
        assert exc_info.value.status_code == 422
        assert "uppercase letter" in exc_info.value.detail

    def test_weak_password_no_lowercase_raises_422_error(self, valid_user_data):
        """Test that password without lowercase is rejected with 422 status."""
        valid_user_data["password"] = "SECUREPASS123!"
        valid_user_data["verify_password"] = "SECUREPASS123!"
        
        with pytest.raises(HTTPException) as exc_info:
            CreateUserRequest(**valid_user_data)
        
        assert exc_info.value.status_code == 422
        assert "lowercase letter" in exc_info.value.detail

    def test_weak_password_no_digit_raises_422_error(self, valid_user_data):
        """Test that password without digit is rejected with 422 status."""
        valid_user_data["password"] = "SecurePassword!"
        valid_user_data["verify_password"] = "SecurePassword!"
        
        with pytest.raises(HTTPException) as exc_info:
            CreateUserRequest(**valid_user_data)
        
        assert exc_info.value.status_code == 422
        assert "number" in exc_info.value.detail

    def test_weak_password_no_special_char_raises_422_error(self, valid_user_data):
        """Test that password without special character is rejected with 422 status."""
        valid_user_data["password"] = "SecurePass123"
        valid_user_data["verify_password"] = "SecurePass123"
        
        with pytest.raises(HTTPException) as exc_info:
            CreateUserRequest(**valid_user_data)
        
        assert exc_info.value.status_code == 422
        assert "special character" in exc_info.value.detail

    def test_short_password_raises_validation_error(self, valid_user_data):
        """Test that password shorter than 8 characters is rejected."""
        valid_user_data["password"] = "Pass1!"
        valid_user_data["verify_password"] = "Pass1!"
        
        with pytest.raises(ValidationError):
            CreateUserRequest(**valid_user_data)

    def test_invalid_email_format_raises_validation_error(self, valid_user_data):
        """Test that invalid email format is rejected."""
        valid_user_data["email"] = "invalid-email"
        
        with pytest.raises(ValidationError):
            CreateUserRequest(**valid_user_data)

    def test_first_name_too_short_raises_validation_error(self, valid_user_data):
        """Test that first_name shorter than 2 chars is rejected."""
        valid_user_data["first_name"] = "J"
        
        with pytest.raises(ValidationError):
            CreateUserRequest(**valid_user_data)

    def test_first_name_too_long_raises_validation_error(self, valid_user_data):
        """Test that first_name longer than 50 chars is rejected."""
        valid_user_data["first_name"] = "J" * 51
        
        with pytest.raises(ValidationError):
            CreateUserRequest(**valid_user_data)

    def test_missing_required_field_raises_validation_error(self):
        """Test that missing required fields are rejected."""
        with pytest.raises(ValidationError):
            CreateUserRequest(first_name="John")

    def test_invalid_gender_raises_validation_error(self, valid_user_data):
        """Test that invalid gender value is rejected."""
        valid_user_data["gender"] = "invalid"
        
        with pytest.raises(ValidationError):
            CreateUserRequest(**valid_user_data)

    def test_all_valid_genders(self, valid_user_data):
        """Test that all valid gender values are accepted."""
        for gender in ["male", "female", "other"]:
            valid_user_data["gender"] = gender
            user = CreateUserRequest(**valid_user_data)
            assert user.gender == gender


class TestUpdateUserRequest:
    """Test cases for UpdateUserRequest schema validation."""

    def test_partial_update_with_first_name(self):
        """Test that partial update with only first_name works."""
        update = UpdateUserRequest(first_name="Jane")
        
        assert update.first_name == "Jane"
        assert update.last_name is None

    def test_partial_update_with_phone_number(self):
        """Test that partial update with only phone_number works."""
        update = UpdateUserRequest(phone_number="+9876543210")
        
        assert update.phone_number == "+9876543210"

    def test_empty_update_is_valid(self):
        """Test that empty update request is valid (no fields)."""
        update = UpdateUserRequest()
        
        assert update.first_name is None
        assert update.last_name is None
        assert update.phone_number is None
        assert update.gender is None

    def test_invalid_gender_in_update_raises_validation_error(self):
        """Test that invalid gender in update is rejected."""
        with pytest.raises(ValidationError):
            UpdateUserRequest(gender="invalid")

    def test_all_fields_update(self):
        """Test updating all optional fields at once."""
        update = UpdateUserRequest(
            first_name="Jane",
            last_name="Smith",
            phone_number="+1112223333",
            gender="female"
        )
        
        assert update.first_name == "Jane"
        assert update.last_name == "Smith"
        assert update.phone_number == "+1112223333"
        assert update.gender == "female"


class TestCreateUserResponse:
    """Test cases for CreateUserResponse schema."""

    def test_valid_response(self):
        """Test valid response creation."""
        response = CreateUserResponse(
            email="test@example.com",
            expires_in_minutes=10,
            user_id="507f1f77bcf86cd799439011"
        )
        
        assert response.email == "test@example.com"
        assert response.expires_in_minutes == 10
        assert response.user_id == "507f1f77bcf86cd799439011"

    def test_user_id_must_be_24_chars(self):
        """Test that user_id must be exactly 24 characters."""
        with pytest.raises(ValidationError):
            CreateUserResponse(
                email="test@example.com",
                expires_in_minutes=10,
                user_id="short_id"
            )

    def test_default_message(self):
        """Test that default message is set."""
        response = CreateUserResponse(
            email="test@example.com",
            expires_in_minutes=10,
            user_id="507f1f77bcf86cd799439011"
        )
        
        assert response.message == "User created successfully"
