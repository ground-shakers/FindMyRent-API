""" User router for handling all user-related endpoints.
"""

import logfire

from fastapi import APIRouter, status, Depends, HTTPException, Form, UploadFile, BackgroundTasks

from schema.users import CreateUserRequest, CreateUserResponse

from models.users import LandLord

from services.verification import get_email_verification_service, EmailVerificationService

from pymongo.errors import DuplicateKeyError
from beanie.exceptions import RevisionIdWasChanged

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
    Only 'tenant' and 'landlord' user types can be created via this endpoint.
    """

    logfire.info(f"Starting user creation: {payload.email}")

    try:
        new_user = LandLord(
            **payload.model_dump(exclude=["verify_password"]), user_type="landlord"
        )
        
        # Hash the user's password before saving
        new_user.password = get_password_hash(payload.password)

        # Insert the new user to the database
        await new_user.insert()
        logfire.info(f"Saved new inactive user to database: {new_user.email}")

        logfire.info(f"Sending verification code to email: {new_user.email} with user ID: {str(new_user.id)}")

        background_tasks.add_task(verification_service.send_verification_code, new_user.email) # Send verification code in background

        logfire.info(f"Verification code sent to email: {new_user.email} with user ID: {str(new_user.id) if new_user.id else ''}")
        return CreateUserResponse(
            email=new_user.email,
            expires_in_minutes=10,
            user_id=str(new_user.id),
        )
    except DuplicateKeyError:
        logfire.warning(f"Attempt to create duplicate user: {payload.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    except RevisionIdWasChanged:
        logfire.error(f"Revision ID conflict when creating user: {payload.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User creation conflict. Please try again.",
        )
    except ValidationError as e:
        # We reach this block if CreateUserResponse validation fails
        logfire.error(f"Validation error for new user with:\nemail {payload.email}:\nerror {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )
    except Exception as e:
        logfire.error(f"Unexpected error for new user with:\nemail {payload.email}:\nerror {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )