"""
Auth service for handling user authentication and authorization business logic.
"""

import os
import secrets
import logfire

from functools import lru_cache
from datetime import timedelta

from fastapi import HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from redis import Redis

from services.verification import get_email_verification_service, get_password_reset_service
from security.refresh_token import SecureRefreshTokenService

from repositories.landlord_repository import get_landlord_repository, LandLordRepository
from repositories.permissions_repository import get_permissions_repository, PermissionsRepository

from security.helpers import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_user_by_id,
)

from schema.users import UserInDB
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


# Redis configuration
redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)

# Verification code settings
CODE_LENGTH = 6
CODE_EXPIRY = timedelta(minutes=10)


class AuthService:
    """Service class for handling authentication and authorization operations.
    
    This service encapsulates the business logic for user authentication,
    email verification, token management, and session handling.
    """

    def __init__(self):
        self.verification_service = get_email_verification_service()
        self.password_reset_service = get_password_reset_service()
        self.landlord_repo = get_landlord_repository()
        self.permissions_repo = get_permissions_repository()

    async def resend_verification_code(
        self, payload: EmailVerificationRequest, background_tasks: BackgroundTasks
    ):
        """Sends a verification code to the user's email address.

        If an existing code is found in Redis for the email, it will be replaced
        with the new code.

        Args:
            payload (EmailVerificationRequest): The email verification request containing the user's email.
            background_tasks (BackgroundTasks): FastAPI background tasks for async email sending.

        Returns:
            EmailVerificationResponse: Response containing success message and expiration time.
            JSONResponse: Error response if the service is unavailable or an error occurs.
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
                self.verification_service.send_verification_code, payload.email
            )

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

    async def verify_email_code(self, payload: EmailVerificationCodeValidationRequest):
        """Verifies the email verification code sent to the user's email address.

        Once the code is verified, the user's account is activated and marked as verified.

        Args:
            payload (EmailVerificationCodeValidationRequest): The request containing email and verification code.

        Returns:
            VerifiedEmailResponse: Response containing verified user details on success.
            JSONResponse: Error response with appropriate status code on failure.

        Raises:
            HTTPException: If an unexpected error occurs during verification.
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

            # Verify code
            success, status_code, message = self.verification_service.verify_code(
                payload.email, submitted_code
            )

            if not success:
                logfire.warning(
                    f"Email verification failed for {payload.email}: {message}: with status code: {status_code}"
                )
                return JSONResponse(
                    status_code=status_code,
                    content={"detail": message},
                )

            # Verify user account
            user = await self.landlord_repo.find_unverified_by_email(payload.email)

            if not user:
                logfire.warning("User not in DB tried email OTP verification")
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
            await self.landlord_repo.save(user)

            return VerifiedEmailResponse(
                user=UserInDB(
                    **user.model_dump(exclude=["is_active", "password"], mode="json")
                ),
            )
        except Exception as e:
            logfire.error(f"Unexpected error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Sorry we can't verify your email at the moment. Please try again later.",
            )

    async def login_for_access_token(self, form_data: OAuth2PasswordRequestForm):
        """Authenticates a user and returns access and refresh tokens.

        Validates the user's credentials and generates a JWT access token
        along with a refresh token for session management.

        Args:
            form_data (OAuth2PasswordRequestForm): The login form containing username (email) and password.

        Returns:
            TokenPair: Response containing access_token, refresh_token, token_type, and expires_in.
            JSONResponse: Error response if authentication fails or an error occurs.
        """
        user = await authenticate_user(form_data.username, form_data.password)

        if not user:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Incorrect username or password"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            user_type_in_db = await self.permissions_repo.get_by_user_type(user.user_type.value)

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

    async def refresh_access_token(
        self, payload: RefreshTokenRequest, secure_service: SecureRefreshTokenService
    ):
        """Refreshes an access token using a valid refresh token.

        Implements token rotation with replay attack detection. If a token
        has been used before, the entire token family is invalidated.

        Args:
            payload (RefreshTokenRequest): The request containing the refresh token.
            secure_service (SecureRefreshTokenService): Service for secure token management.

        Returns:
            TokenPair: New access and refresh token pair.

        Raises:
            HTTPException: If the token is invalid, expired, or a replay attack is detected.
        """
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
                    "message": "Your session has been invalidated. Please log in again."
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
        user_type_in_db = await self.permissions_repo.get_by_user_type(user.user_type.value)
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

    async def logout(
        self, payload: RefreshTokenRequest, secure_service: SecureRefreshTokenService
    ):
        """Logs out the user by revoking the refresh token.

        Marks the provided refresh token as used to prevent further use.

        Args:
            payload (RefreshTokenRequest): The request containing the refresh token to revoke.
            secure_service (SecureRefreshTokenService): Service for secure token management.

        Returns:
            dict: Success message indicating the user has been logged out.
        """
        # Decode refresh token to get user info
        refresh_token_data = decode_refresh_token(payload.refresh_token)

        if refresh_token_data:
            # Mark token as used to prevent further use
            secure_service.mark_token_as_used(refresh_token_data.jti)
            logfire.info(f"User {refresh_token_data.user_id} logged out")

        return {"message": "Successfully logged out"}

    async def logout_all_devices(
        self, payload: RefreshTokenRequest, secure_service: SecureRefreshTokenService
    ):
        """Logs out the user from all devices by revoking all refresh tokens.

        Invalidates all refresh tokens associated with the user, forcing
        re-authentication on all devices.

        Args:
            payload (RefreshTokenRequest): The request containing a valid refresh token.
            secure_service (SecureRefreshTokenService): Service for secure token management.

        Returns:
            dict: Success message indicating the user has been logged out from all devices.

        Raises:
            HTTPException: If the provided refresh token is invalid.
        """
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

    # =========================================================================
    # Password Reset Methods
    # =========================================================================

    async def forgot_password(
        self, payload: ForgotPasswordRequest, background_tasks: BackgroundTasks
    ):
        """Initiates a password reset request.
        
        This method sends a password reset email to the user if the email exists
        in the system. For security reasons, the response is always the same
        whether the email exists or not (to prevent user enumeration).
        
        Args:
            payload (ForgotPasswordRequest): Request containing the user's email.
            background_tasks (BackgroundTasks): FastAPI background tasks for async email.
        
        Returns:
            ForgotPasswordResponse: Success response (always, to prevent enumeration).
            JSONResponse: Error response if rate limited or service unavailable.
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
            # Check if user exists (silently - don't reveal result)
            user = await self.landlord_repo.find_by_email(payload.email)
            
            if user:
                # Only send email if user exists, but don't reveal this
                background_tasks.add_task(
                    self.password_reset_service.request_password_reset,
                    payload.email
                )
                logfire.info(f"Password reset initiated for existing user: {payload.email}")
            else:
                # Log but don't reveal to user
                logfire.info(f"Password reset requested for non-existent email: {payload.email}")
            
            # Always return the same response to prevent enumeration
            return ForgotPasswordResponse(
                message="If an account with this email exists, a password reset link has been sent.",
                email=payload.email
            )
            
        except Exception as e:
            logfire.error(f"Error in forgot_password: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An error occurred. Please try again later."},
            )

    async def reset_password(self, payload: ResetPasswordRequest):
        """Resets the user's password using a valid reset token.
        
        This method validates the password reset token and updates the user's
        password if valid. The token is invalidated after successful use.
        
        Args:
            payload (ResetPasswordRequest): Request containing token and new password.
        
        Returns:
            ResetPasswordResponse: Success response if password was reset.
            JSONResponse: Error response if token is invalid or expired.
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
            # Validate token and get email
            email = self.password_reset_service.validate_reset_token(payload.token)
            
            if not email:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid or expired password reset token"},
                )
            
            # Find user by email
            user = await self.landlord_repo.find_by_email(email)
            
            if not user:
                logfire.error(f"User not found for valid reset token: {email}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid or expired password reset token"},
                )
            
            # Hash the new password
            from security.helpers import get_password_hash
            hashed_password = get_password_hash(payload.password)
            
            # Update user's password
            user.password = hashed_password
            await self.landlord_repo.save(user)
            
            # Invalidate the token (one-time use)
            self.password_reset_service.complete_password_reset(payload.token)
            
            logfire.info(f"Password successfully reset for user: {email}")
            
            return ResetPasswordResponse(
                message="Password has been reset successfully. You can now log in with your new password."
            )
            
        except Exception as e:
            logfire.error(f"Error in reset_password: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An error occurred. Please try again later."},
            )


@lru_cache()
def get_auth_service():
    """Returns a cached instance of AuthService.

    Uses lru_cache to ensure only one instance of AuthService is created
    and reused across the application.

    Returns:
        AuthService: The singleton AuthService instance.
    """
    return AuthService()
