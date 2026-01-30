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

from typing import Annotated
from pydantic import ValidationError

from security.helpers import get_password_hash

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)

@router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: CreateUserRequest, verification_service: Annotated[EmailVerificationService, Depends(get_email_verification_service)], background_tasks: BackgroundTasks, user_service: Annotated[UserService, Depends(get_user_service)]):
    """This endpoint creates a new user in the system and sends a verification code to their email.
    User accounts are created in an inactive state and must be verified via the code sent to their email address.
    Only 'landlord' user types can be created via this endpoint.
    
    ## Possible Errors
    - 409 Conflict: If a user with the provided email already exists.
    - 500 Internal Server Error: If there is an unexpected error during user creation.
    - 503 Service Unavailable: If there is a database connection issue.
    
    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
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
    """This endpoint creates a new admin user in the system and sends a verification code to their email.
    Admin accounts are created in an active state.

    ## Possible Errors
    - 500 Internal Server Error: If there is an unexpected error during user creation.
    - 503 Service Unavailable: If there is a database connection issue.

    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
    """
    return await user_service.create_admin_user(payload, current_user)


@router.get("/{user_id}", response_model=GetUserResponse)
async def get_user(
    user_id: Annotated[str, Path(description="The unique identifier of the user to retrieve", min_length=24, max_length=24)],
    current_user: Annotated[User, Security(get_current_active_user, scopes=["me"])],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    """Get details of an authenticated user.

    The details returned by this endpoint can be displayed on the profile page in the app or anywhere else to provide a personalized experience for the user
    
    ## Possible Errors
    - 404 Not Found: If the user does not exist or is inactive.
    - 500 Internal Server Error: If there is an unexpected error.
    - 503 Service Unavailable: If there is a database connection issue.
    
    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
    """
    return await user_service.get_user(user_id, current_user)


@router.get("")
async def get_users(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["adm:read:users"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
    offset: Annotated[int, Query(description="Number of users to skip for pagination", ge=0)] = 0,
    limit: Annotated[int, Query(description="Maximum number of users to return", ge=1, le=100)] = 10,
):
    """Get a list of users.

    The details returned by this endpoint can be displayed on the admin management page in the app or anywhere else to provide a personalized experience for the admin user
    
    ## Possible Errors
    - 500 Internal Server Error: If there is an unexpected error.
    - 503 Service Unavailable: If there is a database connection issue.
    
    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
    """
    return await user_service.get_users(offset, limit)


@router.get("/admin/{user_id}", response_model=GetUserResponse)
async def get_admin_user_details(
    user_id: Annotated[str, Path(description="The unique ID or email of the admin user to retrieve", min_length=24, max_length=24)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    current_user: Annotated[Admin, Security(get_current_active_user, scopes=["me", "adm:read:user"])],
):
    """Get details of an admin user.

    The details returned by this endpoint can be displayed on the profile page in the app or anywhere else to provide a personalized experience for the admin user
    
    ## Possible Errors
    - 404 Not Found: If the admin user does not exist.
    - 500 Internal Server Error: If there is an unexpected error.
    - 503 Service Unavailable: If there is a database connection issue.
    
    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
    """
    return await user_service.get_admin_user_details(user_id, current_user)


@router.get("/admin")
async def get_admin_users(
    current_user: Annotated[Admin, Security(get_current_active_user, scopes=["adm:read:users"])],
    user_service: Annotated[UserService, Depends(get_user_service)],
    offset: Annotated[int, Query(description="Number of admin users to skip for pagination", ge=0)] = 0,
    limit: Annotated[int, Query(description="Maximum number of admin users to return", ge=1, le=100)] = 10,
):
    """Get a list of admin users.

    The details returned by this endpoint can be displayed on the admin management page in the app or anywhere else to provide a personalized experience for the admin user
    
    ## Possible Errors
    - 500 Internal Server Error: If there is an unexpected error.
    - 503 Service Unavailable: If there is a database connection issue.
    
    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
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

    This endpoint allows an admin user to delete a user account from the system.

    ## Possible Errors
    - 404 Not Found: If the user does not exist.
    - 500 Internal Server Error: If there is an unexpected error.
    - 503 Service Unavailable: If there is a database connection issue.

    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
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