""" User router for handling all user-related endpoints.
"""

import logfire
import re

from fastapi import APIRouter, status, Depends, HTTPException, Form, UploadFile, BackgroundTasks, Security, Path, Query
from fastapi.responses import JSONResponse
from schema.users import CreateUserRequest, CreateUserResponse, GetUserResponse, CreateAdminUserResponse, UserInDB, UserAnalyticsResponse, UpdateUserRequest, UpdateUserResponse


from models.users import LandLord, Admin, User
from models.helpers import UserType

from services.verification import get_email_verification_service, EmailVerificationService
from services.user_service import get_user_service
from services.user_service import UserService

from pymongo.errors import DuplicateKeyError, WriteError, ConnectionFailure
from beanie.exceptions import RevisionIdWasChanged
from beanie import PydanticObjectId


from security.helpers import get_current_active_user

from typing import Annotated, Optional
from pydantic import ValidationError

from security.helpers import get_password_hash

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)

@router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: CreateUserRequest, verification_service: Annotated[EmailVerificationService, Depends(get_email_verification_service)], background_tasks: BackgroundTasks, user_service: Annotated[UserService, Depends(get_user_service)]):
    """Register a new user account.
    
    Creates a new landlord user account and sends a verification email with a 6-digit
    code. The account remains inactive until the email is verified via the
    `/api/v1/auth/verification/email` endpoint.
    
    ## Account Types
    - Only `landlord` accounts can be created via this public endpoint
    - Admin accounts require the `/users/admin` endpoint with proper authorization
    
    ## Request Body
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | email | string (email) | Yes | Unique email address |
    | password | string | Yes | Min 8 chars, must include uppercase, lowercase, number, special char |
    | firstName | string | Yes | User's first name (2-50 chars) |
    | lastName | string | Yes | User's last name (2-50 chars) |
    | phoneNumber | string | Yes | Valid phone number |
    | userType | string | Yes | Must be "landlord" |
    
    ## Example Request
    ```json
    {
        "email": "landlord@example.com",
        "password": "SecureP@ss123",
        "firstName": "John",
        "lastName": "Doe",
        "phoneNumber": "+27821234567",
        "userType": "landlord"
    }
    ```
    
    ## Success Response (201 Created)
    ```json
    {
        "message": "User created successfully. Please check your email for verification.",
        "user": {
            "id": "507f1f77bcf86cd799439011",
            "email": "landlord@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "verified": false
        }
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 409 | Email already registered | `{"detail": "User with this email already exists"}` |
    | 422 | Validation error | `{"detail": "Password must contain at least one uppercase letter"}` |
    | 500 | Internal error | `{"detail": "An error occurred during registration"}` |
    | 503 | Database unavailable | `{"detail": "Service temporarily unavailable"}` |
    
    ## Notes
    - A verification code is automatically sent to the provided email
    - The verification code expires after 10 minutes
    - Unverified accounts cannot log in
    """
    return await user_service.create_user(payload, verification_service, background_tasks)


@router.post(
    "/admin",
    response_model=CreateAdminUserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_user(
    payload: CreateUserRequest,
    current_user: Annotated[
        Admin, Security(get_current_active_user, scopes=["cre:admin:user"])
    ],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    """Create a new admin user account.
    
    Creates a new administrator account with elevated privileges. Admin accounts
    are created in an active state (pre-verified) and can immediately access
    admin-only features.
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Request Body
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | email | string (email) | Yes | Unique email address |
    | password | string | Yes | Strong password |
    | firstName | string | Yes | Admin's first name |
    | lastName | string | Yes | Admin's last name |
    | phoneNumber | string | Yes | Valid phone number |
    | userType | string | Yes | Must be "admin" |
    
    ## Example Request
    ```json
    {
        "email": "admin@example.com",
        "password": "SecureAdm!n123",
        "firstName": "Jane",
        "lastName": "Admin",
        "phoneNumber": "+27821234567",
        "userType": "admin"
    }
    ```
    
    ## Success Response (201 Created)
    ```json
    {
        "message": "Admin user created successfully",
        "user": {
            "id": "507f1f77bcf86cd799439011",
            "email": "admin@example.com",
            "firstName": "Jane",
            "lastName": "Admin",
            "userType": "admin",
            "verified": true
        }
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Insufficient permissions | `{"detail": "Not enough permissions"}` |
    | 409 | Email already exists | `{"detail": "User with this email already exists"}` |
    | 422 | Validation error | `{"detail": [...]}` |
    | 500 | Internal error | `{"detail": "An error occurred"}` |
    """
    return await user_service.create_admin_user(payload, current_user)


@router.get("/me", response_model=GetUserResponse)
async def get_current_user_profile(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["me"])],
):
    """Get the currently authenticated user's profile.
    
    Returns the profile information for the authenticated user making the request.
    No user ID is required - the identity is determined from the access token.
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "id": "507f1f77bcf86cd799439011",
        "email": "user@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "phoneNumber": "+27821234567",
        "userType": "landlord",
        "verified": true,
        "kycVerified": false,
        "premium": false
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 401 | Invalid token | `{"detail": "Could not validate credentials"}` |
    
    ## Use Cases
    - Displaying user profile page
    - Pre-filling profile edit forms
    - Checking premium/verification status
    - Showing user info in navigation/header
    """
    # Serialize user data - exclude sensitive fields
    user_data = current_user.model_dump(
        mode="json",
        by_alias=True,
        exclude=["password", "kyc_verification_trail"]
    )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=user_data
    )


@router.get("/{user_id}", response_model=GetUserResponse)
async def get_user(
    user_id: Annotated[str, Path(description="The unique identifier of the user to retrieve", min_length=24, max_length=24)],
    current_user: Annotated[User, Security(get_current_active_user, scopes=["me"])],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    """Get details of an authenticated user.
    
    Retrieves the profile information for a specific user. Users can only
    access their own profile unless they have admin privileges.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | user_id | string (24 chars) | MongoDB ObjectId of the user |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "id": "507f1f77bcf86cd799439011",
        "email": "user@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "phoneNumber": "+27821234567",
        "userType": "landlord",
        "verified": true,
        "kycVerified": false,
        "createdAt": "2024-01-15T10:30:00Z"
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Access denied | `{"detail": "Cannot access other user's profile"}` |
    | 404 | User not found | `{"detail": "User not found"}` |
    | 422 | Invalid user_id | `{"detail": "Invalid user ID format"}` |
    
    ## Use Cases
    - Displaying user profile page
    - Pre-filling profile edit forms
    - Showing user info in navigation/header
    """
    return await user_service.get_user(user_id, current_user)


@router.get("")
async def get_users(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["adm:read:users"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
    offset: Annotated[int, Query(description="Number of users to skip for pagination", ge=0)] = 0,
    limit: Annotated[int, Query(description="Maximum number of users to return", ge=1, le=100)] = 10,
):
    """Get a paginated list of all users.
    
    Retrieves a list of all landlord users in the system with pagination support.
    This endpoint is designed for admin dashboards and user management interfaces.
    
    ## Query Parameters
    | Parameter | Type | Default | Description |
    |-----------|------|---------|-------------|
    | offset | int | 0 | Number of users to skip (for pagination) |
    | limit | int | 10 | Maximum users to return (1-100) |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Example Request
    ```
    GET /api/v1/users?offset=0&limit=20
    ```
    
    ## Success Response (200 OK)
    ```json
    {
        "users": [
            {
                "id": "507f1f77bcf86cd799439011",
                "email": "user1@example.com",
                "firstName": "John",
                "lastName": "Doe",
                "verified": true
            },
            {
                "id": "507f1f77bcf86cd799439012",
                "email": "user2@example.com",
                "firstName": "Jane",
                "lastName": "Smith",
                "verified": false
            }
        ],
        "total": 150,
        "offset": 0,
        "limit": 20
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Insufficient permissions | `{"detail": "Not enough permissions"}` |
    | 500 | Internal error | `{"detail": "An error occurred"}` |
    """
    return await user_service.get_users(offset, limit)


@router.get("/admin/{user_id}", response_model=GetUserResponse)
async def get_admin_user_details(
    user_id: Annotated[str, Path(description="The unique ID or email of the admin user to retrieve", min_length=24, max_length=24)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[Admin, Security(get_current_active_user, scopes=["me", "adm:read:user"])],
):
    """Get details of a specific admin user.
    
    Retrieves the profile information for an administrator. Admins can view
    their own profile or other admin profiles with appropriate permissions.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | user_id | string (24 chars) | MongoDB ObjectId of the admin |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "id": "507f1f77bcf86cd799439011",
        "email": "admin@example.com",
        "firstName": "Jane",
        "lastName": "Admin",
        "phoneNumber": "+27821234567",
        "userType": "admin",
        "verified": true,
        "createdAt": "2024-01-15T10:30:00Z"
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Insufficient permissions | `{"detail": "Not enough permissions"}` |
    | 404 | Admin not found | `{"detail": "Admin user not found"}` |
    | 422 | Invalid user_id | `{"detail": "Invalid user ID format"}` |
    """
    return await user_service.get_admin_user_details(user_id, current_user)


@router.get("/admin")
async def get_admin_users(
    current_user: Annotated[Admin, Security(get_current_active_user, scopes=["adm:read:users"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
    offset: Annotated[int, Query(description="Number of admin users to skip for pagination", ge=0)] = 0,
    limit: Annotated[int, Query(description="Maximum number of admin users to return", ge=1, le=100)] = 10,
):
    """Get a paginated list of all admin users.
    
    Retrieves a list of all administrator accounts with pagination support.
    Used for admin management dashboards and access control interfaces.
    
    ## Query Parameters
    | Parameter | Type | Default | Description |
    |-----------|------|---------|-------------|
    | offset | int | 0 | Number of admins to skip (pagination) |
    | limit | int | 10 | Maximum admins to return (1-100) |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Example Request
    ```
    GET /api/v1/users/admin?offset=0&limit=10
    ```
    
    ## Success Response (200 OK)
    ```json
    {
        "users": [
            {
                "id": "507f1f77bcf86cd799439011",
                "email": "admin1@example.com",
                "firstName": "Jane",
                "lastName": "Admin"
            },
            {
                "id": "507f1f77bcf86cd799439012",
                "email": "admin2@example.com",
                "firstName": "John",
                "lastName": "Manager"
            }
        ],
        "total": 5,
        "offset": 0,
        "limit": 10
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Insufficient permissions | `{"detail": "Not enough permissions"}` |
    | 500 | Internal error | `{"detail": "An error occurred"}` |
    """
    return await user_service.get_admin_users(offset, limit)


@router.delete("/{user_id}")
async def delete_user(
    user_id: Annotated[
        str,
        Path(
            description="The unique identifier of the user to delete",
            min_length=24,
            max_length=24,
        ),
    ],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[
        User, Security(get_current_active_user, scopes=["del:user"])
    ],
):
    """Delete a user account.
    
    Permanently removes a user account and all associated data from the system.
    Users can delete their own accounts, and admins can delete any user account.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | user_id | string (24 chars) | MongoDB ObjectId of the user |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "User deleted successfully"
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Cannot delete other users | `{"detail": "Not authorized to delete this user"}` |
    | 404 | User not found | `{"detail": "User not found"}` |
    | 422 | Invalid user_id | `{"detail": "Invalid user ID format"}` |
    
    ## Caution
    - This action is **irreversible**
    - All user data, listings, and history will be permanently deleted
    - Active sessions will be invalidated
    """
    return await user_service.delete_user(user_id, current_user)


@router.delete("/admin/{user_id}")
async def delete_admin_user(
    user_id: Annotated[
        str,
        Path(
            description="The unique identifier of the user to delete",
            min_length=24,
            max_length=24,
        ),
    ],
    current_user: Annotated[Admin, Security(get_current_active_user, scopes=["del:admin:user"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
):
    """Delete an admin user account.
    
    This endpoint allows super admins to delete admin user accounts from the system.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | user_id | string (24 chars) | MongoDB ObjectId of the admin to delete |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "Admin user deleted successfully"
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Insufficient permissions | `{"detail": "Not enough permissions"}` |
    | 404 | Admin not found | `{"detail": "Admin user not found"}` |
    | 422 | Invalid user_id format | `{"detail": "Invalid user ID format"}` |
    | 500 | Internal error | `{"detail": "An error occurred while deleting admin"}` |
    
    ## Caution
    - This action is irreversible
    - All associated data and permissions will be permanently removed
    - Audit logs are maintained for compliance
    """
    return await user_service.delete_admin_user(user_id)


@router.put("/{user_id}", response_model=UpdateUserResponse)
async def update_user(
    user_id: Annotated[
        str,
        Path(
            description="The unique identifier of the user to update",
            min_length=24,
            max_length=24,
        ),
    ],
    payload: UpdateUserRequest,
    current_user: Annotated[
        User, Security(get_current_active_user, scopes=["upd:user"])
    ],
    user_service: Annotated[UserService, Depends(get_user_service)],
):
    """Update details of a user account.

    This endpoint allows users to update their own account details such as first name, 
    last name, phone number, and gender. Admin users can update any user's details.
    
    ## Request Body
    All fields are optional - only provided fields will be updated:
    - **firstName**: User's first name (2-50 characters)
    - **lastName**: User's last name (2-50 characters)
    - **phoneNumber**: User's phone number
    - **gender**: User's gender (male, female, or other)

    ## Possible Errors
    - 400 Bad Request: If no fields are provided to update.
    - 403 Forbidden: If attempting to update another user's account without admin privileges.
    - 404 Not Found: If the user does not exist.
    - 422 Unprocessable Entity: If the provided data is invalid.
    - 500 Internal Server Error: If there is an unexpected error.
    - 503 Service Unavailable: If there is a database connection issue.

    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
    """
    return await user_service.update_user(user_id, payload, current_user)


@router.get("/stats/analytics", response_model=UserAnalyticsResponse)
async def get_analytics_for_users(
    current_user: Annotated[
        Admin, Security(get_current_active_user, scopes=["read:user:analytics"])
    ],
    user_service: Annotated[UserService, Depends(get_user_service)],
):
    """Get aggregated analytics data for all users.

    This endpoint provides comprehensive analytics about user demographics, KYC verification status,
    property listings, and user growth metrics. Only accessible to admin and super users.
    
    ## Possible Errors
    - 404 Not Found: If no analytics data is available.
    - 500 Internal Server Error: If there is an unexpected error.
    - 503 Service Unavailable: If there is a database connection issue.
    
    ## Error response structure    ```json
    {
        "detail": "Sample error message"
    }
    ```
    """
    return await user_service.get_analytics_for_users()