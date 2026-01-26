""" User router for handling all user-related endpoints.
"""

import logfire
import re

from fastapi import APIRouter, status, Depends, HTTPException, Form, UploadFile, BackgroundTasks, Security, Path, Query
from fastapi.responses import JSONResponse
from schema.users import CreateUserRequest, CreateUserResponse, GetUserResponse, CreateAdminUserResponse, UserInDB, UserAnalyticsResponse


from models.users import LandLord, Admin, User
from models.helpers import UserType

from services.verification import get_email_verification_service, EmailVerificationService

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
EMAIL_REGEX = "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

@router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(payload: CreateUserRequest, verification_service: Annotated[EmailVerificationService, Depends(get_email_verification_service)], background_tasks: BackgroundTasks):
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

    try:
        with logfire.span(f"Creating new user: {payload.email}"):
            new_user = LandLord(
                **payload.model_dump(exclude=["verify_password"]), user_type="landlord"
            )

            # Hash the user's password before saving
            new_user.password = get_password_hash(payload.password)

            logfire.info(f"Hashed password for new user: {new_user.email}")

            # Insert the new user to the database
            await new_user.insert()
            logfire.info(f"Saved new inactive user to database: {new_user.email}")

            background_tasks.add_task(verification_service.send_verification_code, new_user.email) # Send verification code in background

            logfire.info(f"Email verification code sent to email: {new_user.email} with user ID: {str(new_user.id) if new_user.id else ''}")
            return CreateUserResponse(
                email=new_user.email,
                expires_in_minutes=10,
                user_id=str(new_user.id),
            )
    except DuplicateKeyError:
        logfire.warning(f"Attempt to create duplicate user: {payload.email}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A user with this email already exists"},
        )
    except RevisionIdWasChanged:
        logfire.error(f"Revision ID conflict when creating user: {payload.email}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "User creation conflict. Please try again."},
        )
    except WriteError:
        logfire.error(f"Write error when creating user: {payload.email}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to create user account"},
        )
    except ConnectionFailure:
        logfire.error(f"Connection error when creating user: {payload.email}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "An unexpected error occurred"},
        )
    except ValidationError as e:
        # We reach this block if CreateUserResponse validation fails
        logfire.error(f"Validation error for new user with:\nemail {payload.email}:\nerror {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )
    except Exception as e:
        logfire.error(f"Unexpected error for new user with:\nemail {payload.email}:\nerror {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )


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

    try:
        with logfire.span(f"Creating new admin user: {payload.email}"):
            new_user = Admin(
                **payload.model_dump(exclude=["verify_password"]),
                user_type="admin",
                is_active=True,
            )

            # Hash the user's password before saving
            new_user.password = get_password_hash(payload.password)

            logfire.info(f"Hashed password for new admin user: {new_user.email}")

            # Insert the new user to the database
            await new_user.insert()
            logfire.info(f"Saved new admin user to database: {new_user.email}")

            return CreateAdminUserResponse(
                message="Admin user created successfully",
                user=new_user.model_dump(exclude=["password"], mode="json"),
            )
    except DuplicateKeyError as e:
        logfire.warning(
            f"Attempt to create duplicate admin user: {payload.email} Error: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A user with this email already exists"},
        )
    except RevisionIdWasChanged:
        logfire.error(f"Revision ID conflict when creating admin user: {payload.email}")
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "User creation conflict. Please try again."},
        )
    except WriteError:
        logfire.error(f"Write error when creating admin user: {payload.email}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred"},
        )


@router.get("/{user_id}", response_model=GetUserResponse)
async def get_user(
    user_id: Annotated[str, Path(description="The unique identifier of the user to retrieve", min_length=24, max_length=24)],
    current_user: Annotated[User, Security(get_current_active_user, scopes=["me"])],
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
    try:
        
        is_admin_user = current_user.user_type == UserType.ADMIN or current_user.user_type == UserType.SUPER_USER

        # Only allow admin users to fetch other users' details
        if is_admin_user:
            user_in_db = await LandLord.get(PydanticObjectId(user_id))
            
            if not user_in_db:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": f"User with ID {user_id} not found"},
                )
        else:
            user_in_db = current_user
        return GetUserResponse(**user_in_db.model_dump(exclude=["password"], mode="json"))
    except ValidationError as e:
        logfire.error(
            f"Validation error retrieving user details for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve user details"},
        )
    except Exception as e:
        logfire.error(
            f"Error retrieving user details for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve user details"},
        )


@router.get("")
async def get_users(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["adm:read:users"])],
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
    try:
        users = await LandLord.find().skip(offset).limit(limit).to_list()
        
        logfire.info(f"Retrieved {len(users)} users for admin user {str(current_user.email)}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Users retrieved successfully",
                "users": [user.model_dump(exclude=["password"], mode="json") for user in users],
            },
        )
    except ValidationError as e:
        logfire.error(
            f"Validation error retrieving users for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve users"},
        )
    except Exception as e:
        logfire.error(
            f"Error retrieving users for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve users"},
        )


@router.get("/admin/{user_id}", response_model=GetUserResponse)
async def get_admin_user_details(
    user_id: Annotated[str, Path(description="The unique ID or email of the admin user to retrieve", min_length=24, max_length=24)],
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
    try:
        
        with logfire.info("Fetching an admin user"):
            # Check if user ID or email was provided and fetch document using either
            if not re.match(EMAIL_REGEX, user_id):
                logfire.info(f"Fetching admin user by ID: {user_id}")
                user_in_db = await Admin.get(PydanticObjectId(user_id))
            else:
                logfire.info(f"Fetching admin user by email: {user_id}")
                user_in_db = await Admin.find_one(Admin.email == user_id)

            if not user_in_db:
                logfire.info(f"No admin user found with identifier: {user_id}")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Admin user not found"},
                )

            # Normal admin users cannot fetch super user details
            if user_in_db.user_type.value == UserType.SUPER_USER.value and current_user.user_type.value == UserType.ADMIN.value:
                logfire.info(f"Admin user {str(current_user.email)} attempted to fetch super user details")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Cannot retrieve user details"},
                )
            
            # Normal admin users cannot fetch other admin user details    
            if (not user_in_db.id == current_user.id) and current_user.user_type.value == UserType.ADMIN.value:
                logfire.info(f"Admin user {str(current_user.email)} attempted to fetch other admin user details")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Cannot retrieve user details"},
                )

            logfire.info(f"Admin user details retrieved successfully for user ID: {str(user_in_db.id)}")        
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Admin user details retrieved successfully",
                    "user": user_in_db.model_dump(exclude=["password"], mode="json"),
                },
            )
    except ValidationError as e:
        logfire.error(
            f"Validation error retrieving admin user details for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve admin user details"},
        )
    except Exception as e:
        logfire.error(
            f"Error retrieving admin user details for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve admin user details"},
        )


@router.get("/admin")
async def get_admin_users(
    current_user: Annotated[Admin, Security(get_current_active_user, scopes=["adm:read:users"])],
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
    try:
        admin_users = await Admin.find().skip(offset).limit(limit).to_list()

        logfire.info(f"Retrieved {len(admin_users)} admin users for user {str(current_user.email)}")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Admin users retrieved successfully",
                "users": [user.model_dump(exclude=["password"], mode="json") for user in admin_users],
            },
        )
    except ValidationError as e:
        logfire.error(
            f"Validation error retrieving admin users for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve admin users"},
        )
    except Exception as e:
        logfire.error(
            f"Error retrieving admin users for user ID {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve admin users"},
        )


@router.delete("{user_id}")
async def delete_user(
    user_id: Annotated[
        str,
        Path(
            description="The unique identifier of the user to delete",
            min_length=24,
            max_length=24,
        ),
    ],
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

    try:
        admin_or_super_user = (
            current_user.type.value == UserType.ADMIN.value
            or current_user.type.value == UserType.SUPER_USER.value
        )

        with logfire.info("Deleting a user account"):
            if (not user_id == str(current_user.id)) and not admin_or_super_user:
                logfire.info(
                    f"User with ID: {current_user.id} attempted to delete another user's account"
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Cannot delete user account"},
                )

            user_in_db = await LandLord.get(PydanticObjectId(user_id))

            if not user_in_db:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": f"User with ID {user_id} not found"},
                )

            await user_in_db.delete()

            logfire.info(
                f"User with ID {user_id} deleted by admin user {str(current_user.email)}"
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": f"User with ID {user_id} deleted successfully"},
            )
    except Exception as e:
        logfire.error(
            f"Error deleting user with ID {user_id} by admin user {str(current_user.email)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to delete user"},
        )


@router.delete("/admin/{user_id}")
async def delete_admin_user(
    user_id: Annotated[int, Path(description="Unique of ID of the user to delete")],
    current_user: Annotated[Admin, Security(get_current_active_user, scopes=["del:admin:user"])],
):
    
    with logfire.info("Deleting admin user account"):
        try:
            user_in_db = await Admin.get(PydanticObjectId(user_id))
            
            if not user_in_db:
                logfire.warning(f"Admin user {user_id} not found")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Admin user not found"},
                )
                
            results = await user_in_db.delete()
            
            if not results:
                logfire.info(f"Failed to delete admin user {user_id}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Failed to delete admin user"}
                )
            
            logfire.info(f"Admin user {user_id} deleted successfully")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"detail": "Admin user deleted successfully"},
            )
        except ConnectionError:
            logfire.error(f"Database connection error occurred while deleting admin user {user_id}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,                content={"detail": "Failed to delete admin user"}
            )
        except Exception as e:
            logfire.error(f"Error deleting admin user {user_id}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to delete admin user"},
            )


@router.get("/stats/analytics", response_model=UserAnalyticsResponse)
async def get_analytics_for_users(
    current_user: Annotated[
        Admin, Security(get_current_active_user, scopes=["read:user:analytics"])
    ],
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
    try:
        from models.aggregations.users import UserAnalyticsView
        
        with logfire.span("Fetching user analytics"):
            # Fetch the aggregated analytics data
            # For Views, we need to use find_all() and get the first result
            analytics_results = await UserAnalyticsView.find_all().to_list()
            
            if not analytics_results or len(analytics_results) == 0:
                logfire.warning("No user analytics data available")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "No analytics data available"},
                )
              # Get the first (and should be only) result
            analytics_data = analytics_results[0]
            
            logfire.info(f"User analytics retrieved successfully by admin user {str(current_user.email)}")
            
            return UserAnalyticsResponse(
                **analytics_data.model_dump(mode="json")
            )
            
    except ValidationError as e:
        logfire.error(
            f"Validation error retrieving user analytics for admin user {str(current_user.id)}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Failed to retrieve user analytics"},
        )
    except ConnectionFailure:
        logfire.error(
            f"Database connection error while retrieving user analytics for admin user {str(current_user.id)}"
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service temporarily unavailable"},
        )