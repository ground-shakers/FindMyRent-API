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
    """Send or resend a verification code to the user's email address.
    
    This endpoint sends a 6-digit verification code to the specified email address.
    If an existing code is found in Redis, it will be replaced with a new code.
    The code expires after 10 minutes.
    
    ## Use Cases
    - Initial email verification after user registration
    - Resending verification code when the initial code expires
    - User requests a new code because they didn't receive the first one
    
    ## Request Body
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | email | string (email) | Yes | Email address to send the code to |
    
    ## Example Request
    ```json
    {
        "email": "user@example.com"
    }
    ```
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "Verification code sent successfully",
        "email": "user@example.com",
        "expires_in_minutes": 10
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 422 | Invalid email format | `{"detail": "value is not a valid email address"}` |
    | 503 | Redis unavailable | `{"detail": "Service temporarily unavailable"}` |
    | 500 | Internal error | `{"detail": "Sorry, we can't send the verification code at the moment."}` |
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
    """Authenticate a user and obtain access and refresh tokens.
    
    This endpoint validates user credentials and returns a JWT access token
    along with a refresh token for session management. The access token is used
    for API authentication, while the refresh token is used to obtain new access
    tokens without re-authenticating.
    
    ## Authentication
    - Uses OAuth2 password flow (form data, not JSON)
    - Access tokens expire after 30 minutes
    - Refresh tokens are valid until explicitly revoked
    
    ## Request Body (Form Data)
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | username | string | Yes | User's email address |
    | password | string | Yes | User's password |
    
    ## Example Request (cURL)
    ```bash
    curl -X POST "/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=user@example.com&password=SecureP@ss123"
    ```
    
    ## Success Response (200 OK)
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIs...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
        "token_type": "Bearer",
        "expires_in": 1800
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Invalid credentials | `{"detail": "Incorrect username or password"}` |
    | 401 | Unverified account | `{"detail": "User account is not verified"}` |
    | 422 | Missing fields | `{"detail": [{"loc": ["body", "username"], ...}]}` |
    | 500 | Internal error | `{"detail": "An error occurred during login"}` |
    
    ## Usage Notes
    - Include the access token in the `Authorization` header: `Bearer <access_token>`
    - Store the refresh token securely to obtain new access tokens
    - Use the `/refresh` endpoint when the access token expires
    """
    return await auth_service.login_for_access_token(form_data)


@router.post("/refresh", response_model=TokenPair)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Obtain a new access token using a valid refresh token.
    
    This endpoint implements token rotation for enhanced security. When a refresh
    token is used, both the access token and refresh token are rotated. The old
    refresh token is invalidated to prevent replay attacks.
    
    ## Request Body
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | refresh_token | string | Yes | Valid refresh token from login or previous refresh |
    
    ## Example Request
    ```json
    {
        "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
    }
    ```
    
    ## Success Response (200 OK)
    ```json
    {
        "access_token": "eyJhbGciOiJIUzI1NiIs...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
        "token_type": "Bearer",
        "expires_in": 1800
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Invalid/expired token | `{"detail": "Invalid refresh token"}` |
    | 401 | Token reuse detected | `{"detail": "Token reuse detected. All sessions invalidated."}` |
    | 422 | Missing token | `{"detail": [{"loc": ["body", "refresh_token"], ...}]}` |
    
    ## Important Notes
    - Always use the NEW refresh token from the response for subsequent requests
    - The old refresh token is immediately invalidated after use
    - If token reuse is detected, all user sessions are terminated for security
    """
    return await auth_service.refresh_access_token(payload, secure_service)


@router.post("/logout")
async def logout(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Log out the current session by revoking the refresh token.
    
    This endpoint invalidates the provided refresh token, effectively logging out
    the user from the current device/session. Other active sessions remain valid.
    
    ## Use Cases
    - User manually logs out from a single device
    - Session cleanup when switching users
    - Security measure after sensitive operations
    
    ## Request Body
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | refresh_token | string | Yes | The refresh token to revoke |
    
    ## Example Request
    ```json
    {
        "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
    }
    ```
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "Successfully logged out"
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Invalid token | `{"detail": "Invalid refresh token"}` |
    | 422 | Missing token | `{"detail": [{"loc": ["body", "refresh_token"], ...}]}` |
    
    ## Notes
    - The access token remains valid until expiration (30 min max)
    - For immediate access revocation, implement token blacklisting
    - To log out from all devices, use `/logout-all` instead
    """
    return await auth_service.logout(payload, secure_service)


@router.post("/logout-all")
async def logout_all_devices(
    payload: RefreshTokenRequest,
    secure_service: Annotated[
        SecureRefreshTokenService, Depends(get_secure_refresh_token_service)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Log out from all devices by revoking all refresh tokens.
    
    This endpoint invalidates ALL refresh tokens associated with the user,
    forcing re-authentication on all devices. Use this for security-sensitive
    situations like password changes or suspected account compromise.
    
    ## Use Cases
    - User suspects account compromise
    - After password change
    - Security audit cleanup
    - User wants to sign out everywhere
    
    ## Request Body
    | Field | Type | Required | Description |
    |-------|------|----------|-------------|
    | refresh_token | string | Yes | Any valid refresh token for the user |
    
    ## Example Request
    ```json
    {
        "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
    }
    ```
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "Successfully logged out from all devices"
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Invalid token | `{"detail": "Invalid refresh token"}` |
    | 422 | Missing token | `{"detail": [{"loc": ["body", "refresh_token"], ...}]}` |
    
    ## Security Notes
    - All active sessions across all devices will be terminated
    - Users will need to log in again on each device
    - Access tokens remain valid until expiration but cannot be refreshed
    """
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

