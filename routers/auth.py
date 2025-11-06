"""
Auth router for handling user authentication and authorization related endpoints.
"""

import os
import secrets
import logfire

from dotenv import load_dotenv

from fastapi import HTTPException, status, APIRouter, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from redis import Redis
from datetime import timedelta

from pathlib import Path as TemplatePath

from services.verification import EmailVerificationService
from services.template import TemplateService
from services.email import EmailService
from security.refresh_token import (
    get_secure_refresh_token_service,
    SecureRefreshTokenService,
)

from models.users import LandLord
from models.security import Permissions

from security.helpers import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_user_by_id,
)

from schema.users import UserInDB

from beanie.operators import And

from schema.verification import (
    EmailVerificationCodeValidationRequest,
    VerifiedEmailResponse,
    EmailVerificationResponse,
    EmailVerificationRequest,
)
from schema.security import TokenPair, RefreshTokenRequest

from typing import Annotated

load_dotenv()

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Auth"],
)

# Redis configuration
redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)

SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")

# Verification code settings
CODE_LENGTH = 6
CODE_EXPIRY = timedelta(minutes=10)

# Template directory
TEMPLATES_DIR = TemplatePath("templates")


email_service = EmailService(
    smtp_server=SMTP_SERVER,
    smtp_port=SMTP_PORT,
    username=SMTP_USERNAME,
    password=SMTP_PASSWORD,
    from_email=FROM_EMAIL,
)

template_service = TemplateService(templates_dir=TEMPLATES_DIR)

verification_service = EmailVerificationService(
    redis_client=redis_client,
    email_service=email_service,
    template_service=template_service,
    code_length=CODE_LENGTH,
    code_expiry=CODE_EXPIRY,
)


@router.post(
    "/verification/email/send",
    status_code=status.HTTP_200_OK,
    response_model=EmailVerificationResponse,
)
async def resend_verification_code(
    payload: EmailVerificationRequest, background_tasks: BackgroundTasks
):
    """This endpoint sends a verification code to the user's email address.
    If an existing code is found in Redis for the email, it will be replaced with the new code.

    ### Possible use cases
        - Send verification code when initial code expires
        - Send new verification code on user request
    """
    try:
        redis_client.ping()
    except Exception as e:
        logfire.error(f"Redis connection failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service temporarily unavailable"},
        )

    try:
        # Send verification code (this will replace any existing code in Redis)
        background_tasks.add_task(
            verification_service.send_verification_code, payload.email
        )  # Send verification code in background

        logfire.info(
            f"Verification code sent successfully to user with email: {payload.email}"
        )

        return EmailVerificationResponse(
            message="Verification code sent successfully",
            email=payload.email,
            expires_in_minutes=int(CODE_EXPIRY.total_seconds() / 60),
        )
    except Exception as e:
        logfire.error(
            f"Unexpected error sending email verification code to {payload.email}: {str(e)}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Sorry, we can't send the verification code at the moment. Please try again later."
            },
        )


@router.post(
    "/verification/email",
    status_code=status.HTTP_200_OK,
    response_model=VerifiedEmailResponse,
)
async def verify_email_code(payload: EmailVerificationCodeValidationRequest):
    """This endpoint verifies the email verification code sent to the user's email address.
    Once the code is verified, the user's account is activated.

    ## Responses
    ### User already verified
    - status code: 400
    - body: ```{'detail': 'User already verified'}```

    ### User not found
    - status code: 404
    - body: ```{'detail': 'User not found'}```

    ### Invalid verification code format
    - status code: 400
    - body: ```{'detail': 'Invalid code format. Code must be 6 digits.'}```

    ### Code verification process failed
    - status code: 400
    - body: ```{'detail': 'Invalid verification code'}```

    ### Code verification service unavailable
    - status code: 503
    - body: ```{'detail': 'Service temporarily unavailable'}```

    ### Internal Server Error
    - status code: 500
    - body: ```{"detail": "Sorry we can't verify your email at the moment. Please try again later."}```
    """
    try:
        redis_client.ping()
    except Exception as e:
        logfire.error(f"Redis connection failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service temporarily unavailable"},
        )

    try:
        # Validate code format
        submitted_code = payload.code.strip()
        if not submitted_code.isdigit() or len(submitted_code) != CODE_LENGTH:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": f"Invalid code format. Code must be {CODE_LENGTH} digits."
                },
            )

        # Verify code
        success = verification_service.verify_code(payload.email, submitted_code)

        if not success:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid verification code"},
            )

        # Verify user account
        user = await LandLord.find_one(
            And(LandLord.email == payload.email, LandLord.verified == False)
        )

        if not user:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "User not found"},
            )

        if user.verified:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "User already verified"},
            )

        user.verified = True  # Mark user as verified
        await user.save()

        return VerifiedEmailResponse(
            user=UserInDB(
                **user.model_dump(exclude=["is_active", "password"])
            ),  # Convert to UserInDB schema
        )
    except Exception as e:
        logfire.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sorry we can't verify your email at the moment. Please try again later.",
        )


@router.post("/login", response_model=TokenPair)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    """Login endpoint that returns both access and refresh tokens."""
    user = await authenticate_user(form_data.username, form_data.password)

    if not user:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Incorrect username or password"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_type_in_db = await Permissions.find_one(
            Permissions.user_type == user.user_type.value
        )

        if not user_type_in_db:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "User does not have permissions assigned."},
            )

        # Create access token
        access_token_expires = timedelta(
            minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
        )
        access_token = create_access_token(
            data={"sub": str(user.email), "scopes": user_type_in_db.permissions},
            expires_delta=access_token_expires,
        )

        # Create refresh token
        token_family = secrets.token_urlsafe(32)  # Generate unique token family
        refresh_token = create_refresh_token(str(user.email), token_family)

        logfire.info(f"User {user.email} logged in successfully")

        return TokenPair(
            access_token=access_token.decode("utf-8"),
            refresh_token=refresh_token.decode("utf-8"),
            token_type="Bearer",
            expires_in=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
            * 60,  # Convert to seconds
        )
    except Exception as e:
        logfire.error(f"Fatal error occured during login {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred during login. Please try again later."
            },
        )


@router.post("/refresh", response_model=TokenPair)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
):
    """Refresh endpoint to get a new access token using a refresh token."""

    # Decode and validate refresh token
    refresh_token_data = decode_refresh_token(payload.refresh_token)

    if not refresh_token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid or expired refresh token"},
        )

    # Check if token has been used (replay protection)
    if secure_service.is_token_used(refresh_token_data.jti):
        # Token has been used - this is a replay attack or token theft
        # Invalidate the entire token family as a security measure
        secure_service.invalidate_token_family(refresh_token_data.token_family)

        logfire.warning(
            f"Replay attack detected for user {refresh_token_data.user_id}, token family {refresh_token_data.token_family}"
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Token has already been used. All sessions invalidated for security."
            },
        )

    # Check if token family is still valid
    if not secure_service.is_token_family_valid(refresh_token_data.token_family):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Token family has been invalidated"},
        )

    # Mark this token as used (one-time use enforcement)
    secure_service.mark_token_as_used(refresh_token_data.jti)

    # Get user by ID
    user = await get_user_by_id(refresh_token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "User not found"},
        )

    # Get user permissions
    user_type_in_db = await Permissions.find_one(
        Permissions.user_type == user.user_type.value
    )
    if not user_type_in_db:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "User does not have permissions assigned."},
        )

    # Create new access token
    access_token_expires = timedelta(
        minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    )
    access_token = create_access_token(
        data={"sub": str(user.id), "scopes": user_type_in_db.permissions},
        expires_delta=access_token_expires,
    )

    # Create new refresh token with same family for rotation
    new_refresh_token = create_refresh_token(
        str(user.id), refresh_token_data.token_family
    )

    logfire.info(f"Tokens refreshed for user {user.email}")

    return TokenPair(
        access_token=access_token.decode("utf-8"),
        refresh_token=new_refresh_token.decode("utf-8"),
        token_type="Bearer",
        expires_in=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
        * 60,  # Convert to seconds
    )


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
):
    """Logout endpoint that revokes the refresh token."""

    # Decode refresh token to get user info
    refresh_token_data = decode_refresh_token(payload.refresh_token)

    if refresh_token_data:
        # Mark token as used to prevent further use
        secure_service.mark_token_as_used(refresh_token_data.jti)
        logfire.info(f"User {refresh_token_data.user_id} logged out")

    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all_devices(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
):
    """Logout from all devices by revoking all refresh tokens for the user."""

    # Decode refresh token to get user info
    refresh_token_data = decode_refresh_token(payload.refresh_token)

    if not refresh_token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Invalid refresh token"},
        )

    # Revoke all refresh tokens for the user
    secure_service.revoke_all_user_tokens(refresh_token_data.user_id)

    logfire.info(f"All devices logged out for user {refresh_token_data.user_id}")

    return {"message": "Successfully logged out from all devices"}
