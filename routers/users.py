import logging

from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.responses import JSONResponse

from schema.users import CreateUserRequest, CreateUserResponse

from models.users import Tenant, LandLord

from fastapi.requests import Request

from middleware.rate_limiting import limiter

from services.verification import get_email_verification_service, EmailVerificationService

from pymongo.errors import DuplicateKeyError

from typing import Annotated

from security.helpers import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/users",
    tags=["Users"],
)

@router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_user(payload: CreateUserRequest, request: Request, verification_service: Annotated[EmailVerificationService, Depends(get_email_verification_service)]):
    """This endpoint creates a new user in the system and sends a verification code to their email.
    User accounts are created in an inactive state and must be verified via the code sent to their email address.
    Only 'tenant' and 'landlord' user types can be created via this endpoint.
    """

    logger.info(f"Creating user: {payload.email}")

    try:

        # Check user type from payload and add to respective collection
        if payload.user_type == "tenant":
            # Add tenant to the database
            new_user = Tenant(**payload.model_dump(exclude=["verify_password"]))
        elif payload.user_type == "landlord":
            # Add landlord to the database
            new_user = LandLord(**payload.model_dump(exclude=["verify_password"]))
        else:
            # Raise error for unsupported user types or user type of 'admin'
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid user type"},
            )
            
        # Hash the user's password before saving
        new_user.password = get_password_hash(payload.password)

        # Save the new user to the database
        await new_user.save()
        logger.info(f"Created new inactive user to database: {new_user.email}")

        success = verification_service.send_verification_code(new_user.email)

        if not success:
            logger.error(f"Failed to send verification email to: {new_user.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email",
            )

        logger.info(f"Verification code sent to email: {new_user.email} with user ID: {str(new_user.id) if new_user.id else ''}")
        return CreateUserResponse(
            email=new_user.email,
            expires_in_minutes=10,
            user_id=str(new_user.id) if new_user.id else "",
        )
    except DuplicateKeyError:
        logger.warning(f"Attempt to create duplicate user: {payload.email}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )