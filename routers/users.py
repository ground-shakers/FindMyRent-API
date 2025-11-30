""" User router for handling all user-related endpoints.
"""

import logfire

from fastapi import APIRouter, status, Depends, HTTPException, Form, UploadFile, BackgroundTasks, Security
from fastapi.responses import JSONResponse
from schema.users import CreateUserRequest, CreateUserResponse, GetUserResponse

from models.users import LandLord

from services.verification import get_email_verification_service, EmailVerificationService

from pymongo.errors import DuplicateKeyError, WriteError, ConnectionFailure, ServerSelectionTimeoutError
from beanie.exceptions import RevisionIdWasChanged
from beanie.operators import And


from security.helpers import get_current_active_user

from typing import Annotated
from pydantic import ValidationError

from security.helpers import get_password_hash

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)

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
    except ServerSelectionTimeoutError:
        logfire.error(f"Database server selection timeout when creating user: {payload.email}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "An unexpected error occurred"},
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


@router.get("", response_model=GetUserResponse)
async def get_user_details(
    current_user: Annotated[LandLord, Security(get_current_active_user, scopes=["me"])],
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

        return GetUserResponse(**current_user.model_dump(exclude=["password"], mode="json"))
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
