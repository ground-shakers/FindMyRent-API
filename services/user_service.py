""" User service for handling all user-related business logic.
"""

import logfire
import re

from functools import lru_cache

from fastapi import APIRouter, status, Depends, HTTPException, Form, UploadFile, BackgroundTasks, Security, Path, Query
from fastapi.responses import JSONResponse
from schema.users import CreateUserRequest, CreateUserResponse, GetUserResponse, CreateAdminUserResponse, UserInDB, UserAnalyticsResponse, UpdateUserRequest, UpdateUserResponse

from models.users import LandLord, Admin, User
from models.helpers import UserType

from services.verification import get_email_verification_service, EmailVerificationService

from repositories.landlord_repository import get_landlord_repository, LandLordRepository
from repositories.admin_repository import get_admin_repository, AdminRepository

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

class UserService:
    """Service class for handling user-related business logic.

    This service encapsulates the business logic for user operations,
    delegating database operations to the appropriate repositories.
    """

    def __init__(self):
        self.EMAIL_REGEX = "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        self.landlord_repo = get_landlord_repository()
        self.admin_repo = get_admin_repository()

    async def create_user(self, payload: CreateUserRequest, verification_service: Annotated[EmailVerificationService, Depends(get_email_verification_service)], background_tasks: BackgroundTasks):
        """
        This method creates a new user in the system and sends a verification code to their email.
        User accounts are created in an inactive state and must be verified via the code sent to their email address.


        Args:
            payload (CreateUserRequest): The user creation request containing user details.
            verification_service (EmailVerificationService): The email verification service instance.
            background_tasks (BackgroundTasks): The background tasks instance.

        Returns:
            CreateUserResponse: The response containing the user ID and expiration time.
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
                await self.landlord_repo.insert(new_user)
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


    async def get_user(self, user_id: str, current_user: User):
        """This method fetches the details of the user with the given user ID

        Args:
            user_id (str): The unique identifier of the user to retrieve

        Returns:
            GetUserResponse: The user details
        """

        try:
            
            is_admin_user = current_user.user_type == UserType.ADMIN or current_user.user_type == UserType.SUPER_USER

            # Only allow admin users to fetch other users' details
            if is_admin_user:
                user_in_db = await self.landlord_repo.get_by_id(user_id)
                
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

    
    async def get_users(self, offset: int, limit: int):
        """This method fetches a list of users with pagination support

        Args:
            offset (int): The number of users to skip for pagination
            limit (int): The maximum number of users to return

        Returns:
            List[User]: A list of users
        """

        try:
            users = await self.landlord_repo.find_all(offset, limit)
            
            logfire.info(f"Retrieved {len(users)} users")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Users retrieved successfully",
                    "users": [user.model_dump(exclude=["password"], mode="json") for user in users],
                },
            )
        except ValidationError as e:
            logfire.error(
                f"Validation error retrieving users: {str(e)}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to retrieve users"},
            )
        except Exception as e:
            logfire.error(
                f"Error retrieving users: {str(e)}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to retrieve users"},
            )


    async def delete_user(self, user_id: str, current_user: User):
        """This method deletes a user from the system

        Args:
            user_id (str): User ID of the user to delete
            current_user (User): User making the deletion request
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

                user_in_db = await self.landlord_repo.get_by_id(user_id)

                if not user_in_db:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": f"User with ID {user_id} not found"},
                    )

                await self.landlord_repo.delete(user_in_db)

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


    async def create_admin_user(self, payload: CreateUserRequest, current_user: User):
        """
        This method creates a new admin user in the system.

        Args:
            payload (CreateUserRequest): The user creation request containing user details.
            current_user (Admin): The current active super user.

        Returns:
            CreateAdminUserResponse: The response containing the details of the new admin user
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
                await self.admin_repo.insert(new_user)
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


    async def get_admin_user_details(self, user_id: str, current_user: User):
        """This method retrieves the details of an admin use with the user ID provided

        Args:
            user_id (str): ID of the admin user to retrieve
            current_user (User): The current user

        Returns:
            GetUserResponse: Details of the admin user
        """

        try:
            
            with logfire.info("Fetching an admin user"):
                # Check if user ID or email was provided and fetch document using either
                if not re.match(self.EMAIL_REGEX, user_id):
                    logfire.info(f"Fetching admin user by ID: {user_id}")
                    user_in_db = await self.admin_repo.get_by_id(user_id)
                else:
                    logfire.info(f"Fetching admin user by email: {user_id}")
                    user_in_db = await self.admin_repo.get_by_email(user_id)

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


    async def get_admin_users(self, offset: int, limit: int):
        """This method retrieves a list of admin users with pagination

        Args:
            offset (int): Number of admin users to skip for pagination
            limit (int): Maximum number of admin users to return

        Returns:
            JSONResponse: List of admin users retrieved, if successful, else, error message
        """

        try:
            admin_users = await self.admin_repo.find_all(offset, limit)

            logfire.info(f"Retrieved {len(admin_users)} admin users")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Admin users retrieved successfully",
                    "users": [user.model_dump(exclude=["password"], mode="json") for user in admin_users],
                },
            )
        except ValidationError as e:
            logfire.error(
                f"Validation error retrieving admin users: {str(e)}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to retrieve admin users"},
            )
        except Exception as e:
            logfire.error(
                f"Error retrieving admin users: {str(e)}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to retrieve admin users"},
            )


    async def delete_admin_user(self, user_id: str):
        """This method deletes admin users from the system

        Args:
            user_id (int): User ID of admin user to be deleted

        Returns:
            JSONResponse: JSON response with message of the status of the deletion
        """
        with logfire.info("Deleting admin user account"):
            try:
                user_in_db = await self.admin_repo.get_by_id(user_id)
                
                if not user_in_db:
                    logfire.warning(f"Admin user {user_id} not found")
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "Admin user not found"},
                    )
                    
                await self.admin_repo.delete(user_in_db)
                
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


    async def get_analytics_for_users(self):
        """This method retrieves analytics data for all users

        Returns:
            JSONResponse: JSON response with analytics data for all users
        """

        try:
            
            with logfire.span("Fetching user analytics"):
                # Fetch the aggregated analytics data
                analytics_results = await self.landlord_repo.get_analytics()
                
                if not analytics_results or len(analytics_results) == 0:
                    logfire.warning("No user analytics data available")
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "No analytics data available"},
                    )
                # Get the first (and should be only) result
                analytics_data = analytics_results[0]
                
                logfire.info("User analytics retrieved successfully")
                
                return UserAnalyticsResponse(
                    **analytics_data.model_dump(mode="json")
                )
                
        except ValidationError as e:
            logfire.error(
                f"Validation error retrieving user analytics: {str(e)}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to retrieve user analytics"},
            )
        except ConnectionFailure:
            logfire.error(
                "Database connection error while retrieving user analytics"
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service temporarily unavailable"},
            )


    async def update_user(self, user_id: str, payload: UpdateUserRequest, current_user: User):
        """This method updates the details of a user

        Args:
            user_id (str): The unique identifier of the user to update
            payload (UpdateUserRequest): The update request containing fields to update
            current_user (User): The current authenticated user

        Returns:
            UpdateUserResponse: The response containing the updated user details
        """

        try:
            with logfire.span(f"Updating user: {user_id}"):
                is_admin_user = current_user.user_type == UserType.ADMIN or current_user.user_type == UserType.SUPER_USER

                # Only allow users to update their own details, unless they are admin/super users
                if not is_admin_user and str(current_user.id) != user_id:
                    logfire.warning(f"User {str(current_user.id)} attempted to update another user's details")
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "You can only update your own account details"},
                    )

                # Fetch the user to update
                user_in_db = await self.landlord_repo.get_by_id(user_id)

                if not user_in_db:
                    logfire.warning(f"User with ID {user_id} not found for update")
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": f"User with ID {user_id} not found"},
                    )

                # Apply only non-null fields from the payload
                update_data = payload.model_dump(exclude_none=True)

                if not update_data:
                    logfire.info(f"No fields to update for user {user_id}")
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"detail": "No fields provided to update"},
                    )

                # Update the user fields
                for field, value in update_data.items():
                    setattr(user_in_db, field, value)

                # Save the updated user
                await self.landlord_repo.save(user_in_db)

                logfire.info(f"User {user_id} updated successfully by {str(current_user.id)}")

                return UpdateUserResponse(
                    message="User updated successfully",
                    user=user_in_db.model_dump(exclude=["password"], mode="json"),
                )

        except ValidationError as e:
            logfire.error(f"Validation error updating user {user_id}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"detail": "Invalid data provided for update"},
            )
        except ConnectionFailure:
            logfire.error(f"Database connection error while updating user {user_id}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service temporarily unavailable"},
            )
        except Exception as e:
            logfire.error(f"Error updating user {user_id}: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to update user details"},
            )


@lru_cache()
def get_user_service():
    """This function returns a UserService instance

    Returns:
        UserService: UserService instance
    """


    return UserService()