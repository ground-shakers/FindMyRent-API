"""
Auth router for handling user authentication and authorization related endpoints.
"""

import logfire

from fastapi import HTTPException, status, APIRouter, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from security.refresh_token import (
    get_secure_refresh_token_service,
    SecureRefreshTokenService,
)

from services.auth_service import get_auth_service, AuthService

from schema.verification import (
    EmailVerificationCodeValidationRequest,
    VerifiedEmailResponse,
    EmailVerificationResponse,
    EmailVerificationRequest,
)
from schema.security import TokenPair, RefreshTokenRequest

from typing import Annotated


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Auth"],
)


@router.post(
    "/verification/email/send",
    status_code=status.HTTP_200_OK,
    response_model=EmailVerificationResponse,
)
async def resend_verification_code(
    payload: EmailVerificationRequest,
    background_tasks: BackgroundTasks,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """This endpoint sends a verification code to the user's email address.
    If an existing code is found in Redis for the email, it will be replaced with the new code.

    ### Possible use cases
        - Send verification code when initial code expires
        - Send new verification code on user request
    """
    return await auth_service.resend_verification_code(payload, background_tasks)


@router.post(
    "/verification/email",
    status_code=status.HTTP_200_OK,
    response_model=VerifiedEmailResponse,
)
async def verify_email_code(
    payload: EmailVerificationCodeValidationRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
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
    return await auth_service.verify_email_code(payload)


@router.post("/login", response_model=TokenPair)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Login endpoint that returns both access and refresh tokens."""
    return await auth_service.login_for_access_token(form_data)


@router.post("/refresh", response_model=TokenPair)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Refresh endpoint to get a new access token using a refresh token."""
    return await auth_service.refresh_access_token(payload, secure_service)


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Logout endpoint that revokes the refresh token."""
    return await auth_service.logout(payload, secure_service)


@router.post("/logout-all")
async def logout_all_devices(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Logout from all devices by revoking all refresh tokens for the user."""
    return await auth_service.logout_all_devices(payload, secure_service)
