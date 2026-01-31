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
from schema.security import (
    TokenPair,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)

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


# =============================================================================
# Password Reset Endpoints
# =============================================================================


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    response_model=ForgotPasswordResponse,
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Request a password reset link.
    
    This endpoint initiates the password reset flow by sending a reset link
    to the provided email address if an account exists.
    
    ## Security Notes
    - For security, this endpoint always returns a success response to prevent
      user enumeration attacks (revealing which emails are registered).
    - Reset links expire after 1 hour.
    - Maximum 3 reset requests per hour per email address.
    
    ## Request Body
    - **email**: The email address associated with the account.
    
    ## Responses
    ### Success (always returned for valid email format)
    - status code: 200
    - body: `{"message": "If an account with this email exists, a password reset link has been sent.", "email": "..."}`
    
    ### Service Unavailable
    - status code: 503
    - body: `{"detail": "Service temporarily unavailable"}`
    """
    return await auth_service.forgot_password(payload, background_tasks)


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    response_model=ResetPasswordResponse,
)
async def reset_password(
    payload: ResetPasswordRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Reset password using a valid reset token.
    
    This endpoint completes the password reset flow by validating the token
    and updating the user's password.
    
    ## Security Notes
    - Tokens are single-use and expire after 1 hour.
    - Maximum 5 failed token validation attempts before lockout.
    - Password must meet strength requirements (uppercase, lowercase, number, special char).
    
    ## Request Body
    - **token**: The password reset token from the email link (64 characters).
    - **password**: The new password (min 8 characters).
    - **confirm_password**: Confirmation of the new password.
    
    ## Responses
    ### Success
    - status code: 200
    - body: `{"message": "Password has been reset successfully. You can now log in with your new password."}`
    
    ### Invalid Token
    - status code: 400
    - body: `{"detail": "Invalid or expired password reset token"}`
    
    ### Password Validation Failed
    - status code: 422
    - body: `{"detail": "Password must contain at least one uppercase letter"}`
    
    ### Service Unavailable
    - status code: 503
    - body: `{"detail": "Service temporarily unavailable"}`
    """
    return await auth_service.reset_password(payload)

