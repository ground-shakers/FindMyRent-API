"""Shared pytest fixtures and configuration for all tests."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Generator, AsyncGenerator

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from main import app
from models.users import LandLord, Admin, User
from models.listings import Listing, ListingLocation, LandLordDetailsSummary, PropertyType
from models.security import Permissions
from models.helpers import UserType
from schema.users import UserDateOfBirth

from repositories.landlord_repository import LandLordRepository
from repositories.admin_repository import AdminRepository
from repositories.listing_repository import ListingRepository
from repositories.permissions_repository import PermissionsRepository

from beanie import PydanticObjectId


# ============================================================================
# Test Data Constants
# ============================================================================

VALID_OBJECT_ID = "507f1f77bcf86cd799439011"

VALID_LANDLORD_DATA = {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone_number": "+1234567890",
    "password": "SecurePass123!",
    "verify_password": "SecurePass123!",
    "date_of_birth": {"day": 15, "month": 6, "year": 1990},
    "gender": "male"
}

VALID_ADMIN_DATA = {
    "first_name": "Admin",
    "last_name": "User",
    "email": "admin@example.com",
    "phone_number": "+0987654321",
    "password": "AdminPass456!",
    "verify_password": "AdminPass456!",
    "date_of_birth": {"day": 1, "month": 1, "year": 1985},
    "gender": "female"
}

VALID_LISTING_DATA = {
    "description": "Spacious 2-bedroom apartment with great views",
    "price": 1500.00,
    "address": "123 Main Street",
    "city": "New York",
    "state": "NY",
    "bedrooms": 2,
    "amenities": ["pool", "gym", "parking"],
    "property_type": "flat"
}


# ============================================================================
# Mock Model Factories
# ============================================================================

def create_mock_landlord(
    id: str = VALID_OBJECT_ID,
    verified: bool = True,
    kyc_verified: bool = True,
    is_active: bool = True,
    **overrides
) -> MagicMock:
    """Create a mock LandLord object for testing."""
    mock = MagicMock(spec=LandLord)
    mock.id = PydanticObjectId(id)
    mock.first_name = overrides.get("first_name", VALID_LANDLORD_DATA["first_name"])
    mock.last_name = overrides.get("last_name", VALID_LANDLORD_DATA["last_name"])
    mock.email = overrides.get("email", VALID_LANDLORD_DATA["email"])
    mock.phone_number = overrides.get("phone_number", VALID_LANDLORD_DATA["phone_number"])
    mock.password = overrides.get("password", "hashed_password")
    mock.user_type = UserType.LANDLORD
    mock.verified = verified
    mock.kyc_verified = kyc_verified
    mock.is_active = is_active
    mock.listings = overrides.get("listings", [])
    mock.kyc_verification_trail = []
    mock.date_of_birth = UserDateOfBirth(**VALID_LANDLORD_DATA["date_of_birth"])
    mock.gender = VALID_LANDLORD_DATA["gender"]
    mock.model_dump = MagicMock(return_value={
        "id": str(mock.id),
        "first_name": mock.first_name,
        "last_name": mock.last_name,
        "email": mock.email,
        "phone_number": mock.phone_number,
        "user_type": mock.user_type.value,
        "verified": mock.verified,
        "kyc_verified": mock.kyc_verified,
        "is_active": mock.is_active,
        "listings": mock.listings,
    })
    return mock


def create_mock_admin(
    id: str = VALID_OBJECT_ID,
    is_active: bool = True,
    user_type: UserType = UserType.ADMIN,
    **overrides
) -> MagicMock:
    """Create a mock Admin object for testing."""
    mock = MagicMock(spec=Admin)
    mock.id = PydanticObjectId(id)
    mock.first_name = overrides.get("first_name", VALID_ADMIN_DATA["first_name"])
    mock.last_name = overrides.get("last_name", VALID_ADMIN_DATA["last_name"])
    mock.email = overrides.get("email", VALID_ADMIN_DATA["email"])
    mock.phone_number = overrides.get("phone_number", VALID_ADMIN_DATA["phone_number"])
    mock.password = overrides.get("password", "hashed_password")
    mock.user_type = user_type
    mock.is_active = is_active
    mock.model_dump = MagicMock(return_value={
        "id": str(mock.id),
        "first_name": mock.first_name,
        "last_name": mock.last_name,
        "email": mock.email,
        "user_type": mock.user_type.value,
        "is_active": mock.is_active,
    })
    return mock


def create_mock_listing(
    id: str = VALID_OBJECT_ID,
    verified: bool = True,
    landlord_id: str = VALID_OBJECT_ID,
    **overrides
) -> MagicMock:
    """Create a mock Listing object for testing."""
    mock = MagicMock(spec=Listing)
    mock.id = PydanticObjectId(id)
    mock.description = overrides.get("description", VALID_LISTING_DATA["description"])
    mock.price = overrides.get("price", VALID_LISTING_DATA["price"])
    mock.bedrooms = overrides.get("bedrooms", VALID_LISTING_DATA["bedrooms"])
    mock.verified = verified
    mock.images = overrides.get("images", ["https://example.com/img1.jpg"])
    mock.proof_of_ownership = overrides.get("proof_of_ownership", ["https://example.com/proof.pdf"])
    mock.amenities = overrides.get("amenities", VALID_LISTING_DATA["amenities"])
    mock.property_type = PropertyType.FLAT
    mock.location = MagicMock()
    mock.location.address = VALID_LISTING_DATA["address"]
    mock.location.city = VALID_LISTING_DATA["city"]
    mock.location.state = VALID_LISTING_DATA["state"]
    mock.landlord = MagicMock()
    mock.landlord.landlord_id = landlord_id
    mock.landlord.first_name = "John"
    mock.landlord.last_name = "Doe"
    mock.landlord.email = "john.doe@example.com"
    mock.model_dump = MagicMock(return_value={
        "id": str(mock.id),
        "description": mock.description,
        "price": mock.price,
        "verified": mock.verified,
        "bedrooms": mock.bedrooms,
    })
    return mock


def create_mock_permissions(user_type: str = "landlord") -> MagicMock:
    """Create a mock Permissions object for testing."""
    mock = MagicMock(spec=Permissions)
    mock.user_type = user_type
    mock.permissions = ["me", "read:listing", "cre:listing", "del:listing", "upd:user"]
    return mock


# ============================================================================
# Repository Fixtures
# ============================================================================

@pytest.fixture
def mock_landlord_repo() -> MagicMock:
    """Create a mock LandLordRepository."""
    repo = MagicMock(spec=LandLordRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.find_unverified_by_email = AsyncMock(return_value=None)
    repo.find_all = AsyncMock(return_value=[])
    repo.insert = AsyncMock()
    repo.save = AsyncMock()
    repo.delete = AsyncMock()
    repo.get_analytics = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_admin_repo() -> MagicMock:
    """Create a mock AdminRepository."""
    repo = MagicMock(spec=AdminRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=None)
    repo.find_all = AsyncMock(return_value=[])
    repo.insert = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_listing_repo() -> MagicMock:
    """Create a mock ListingRepository."""
    repo = MagicMock(spec=ListingRepository)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.find_by_landlord_and_id = AsyncMock(return_value=None)
    repo.find_verified_by_id = AsyncMock(return_value=None)
    repo.find_by_landlord = AsyncMock(return_value=[])
    repo.find_verified = AsyncMock(return_value=[])
    repo.save = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_permissions_repo() -> MagicMock:
    """Create a mock PermissionsRepository."""
    repo = MagicMock(spec=PermissionsRepository)
    repo.get_by_user_type = AsyncMock(return_value=None)
    return repo


# ============================================================================
# HTTP Client Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing endpoints."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        follow_redirects=True
    ) as client:
        yield client


# ============================================================================
# Auth Override Fixtures
# ============================================================================

@pytest.fixture
def override_auth_landlord():
    """Override authentication to return a mock landlord user."""
    from security.helpers import get_current_active_user
    
    mock_user = create_mock_landlord()
    
    def _override():
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        return mock_user
    
    yield _override
    app.dependency_overrides.clear()


@pytest.fixture
def override_auth_admin():
    """Override authentication to return a mock admin user."""
    from security.helpers import get_current_active_user
    
    mock_user = create_mock_admin()
    
    def _override():
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        return mock_user
    
    yield _override
    app.dependency_overrides.clear()


@pytest.fixture
def override_auth_super_user():
    """Override authentication to return a mock super user."""
    from security.helpers import get_current_active_user
    
    mock_user = create_mock_admin(user_type=UserType.SUPER_USER)
    
    def _override():
        app.dependency_overrides[get_current_active_user] = lambda: mock_user
        return mock_user
    
    yield _override
    app.dependency_overrides.clear()
