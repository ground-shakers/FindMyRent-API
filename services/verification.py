"""Service for handling email verification."""

import os

import logfire

from fastapi import status

from models.helpers import ContentType

from datetime import timedelta

from .template import TemplateService, get_template_service
from .email import EmailService, get_email_service

from typing import Optional

from redis import Redis

from dotenv import load_dotenv


from security.helpers import generate_verification_code

load_dotenv()

# Redis configuration
redis_client = Redis(host="localhost", port=6379, db=0, decode_responses=True)

# Verification code settings
CODE_LENGTH = 6
CODE_EXPIRY = timedelta(minutes=10)
MAX_ATTEMPTS = 5


email_service = get_email_service() # Email service instance
template_service = get_template_service() # Template service instance

class EmailVerificationService:
    """Service for handling email verification."""

    def __init__(
        self,
        redis_client: Redis,
        email_service: EmailService,
        template_service: TemplateService,
        code_length: int = 6,
        code_expiry: timedelta = timedelta(minutes=10),
    ):
        self.redis = redis_client
        self.email_service = email_service
        self.template_service = template_service
        self.code_length = code_length
        self.code_expiry = code_expiry

    def send_verification_code(self, email: str) -> bool:
        """Send an email verification code to the specified email address.

        Args:
            email (str): The email address to send the verification code to.

        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """


        with logfire.span(f"Sending email verification code to: {email}"):
            # Generate and store code
            code = generate_verification_code()
            
            logfire.info(f"Generated verification code for email: {email}")
            
            self._store_code(email, code)
            
            logfire.info(f"Stored verification code for email: {email} in Redis")

            # Send email
            html_content = self.template_service.render_verification_email(code, email)
            
            logfire.info(f"Prepared verification email content for: {email}")
            
            return self.email_service.send_email(
                to=email,
                subject="Your FindMyRent Verification Code",
                content=html_content,
                content_type=ContentType.HTML,
            )

    def verify_code(self, email: str, code: str) -> tuple[bool, int, str]:
        """Verify the email OTP code.

        Args:
            email (str): The email address associated with the OTP code.
            code (str): The OTP code submitted by the user.

        Returns:
            tuple[bool, int, str]: A tuple containing the verification result, HTTP status code, and a message.
        """

        # Check failed attempts
        if self._is_attempt_limit_reached(email):
            return (False, status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Please request a new code.")

        # Get stored code
        stored_code = self._get_stored_code(email)

        if not stored_code:
            return (False, status.HTTP_400_BAD_REQUEST, "Verification code expired or not found. Please request a new code.")

        # Verify code
        if code != stored_code:
            self._increment_attempts(email)
            remaining = MAX_ATTEMPTS - self._get_attempts(email)
            return (False, status.HTTP_401_UNAUTHORIZED, f"Invalid verification code. {remaining} attempts remaining.")

        # Success - cleanup
        self._cleanup_verification(email)
        return (True, status.HTTP_200_OK, "Verification successful.")

    def _store_code(self, email: str, code: str):
        """Store email verification code in Redis.

        Args:
            email (str): Email address to store the verification code for.
            code (str): The verification code to store.
        """
        key = f"email:verification:{email}"
        # Redis setex expects seconds (or an int); convert timedelta to seconds
        self.redis.setex(key, int(self.code_expiry.total_seconds()), code)

    def _get_stored_code(self, email: str) -> Optional[str]:
        """Get stored email verification code.

        Args:
            email (str): Email address to retrieve the verification code for.

        Returns:
            Optional[str]: The stored verification code or None if not found.
        """
        key = f"email:verification:{email}"
        code = self.redis.get(key)
        return code if code else None

    def _is_attempt_limit_reached(self, email: str) -> bool:
        """Check if failed code attempt limit is reached.

        Args:
            email (str): Email address pegged to the verification code.

        Returns:
            bool: True if over limit, False otherwise.
        """
        attempts = self._get_attempts(email)
        if attempts >= MAX_ATTEMPTS:
            # reached or exceeded allowed attempts; cleanup stored data and report limit reached
            self._cleanup_verification(email)
            return True
        return False

    def _get_attempts(self, email: str) -> int:
        """Get number of failed email verification code submission attempts.

        Args:
            email (str): Email address pegged to the verification code.

        Returns:
            int: Number of failed attempts.
        """
        key = f"attempts:{email}"
        attempts = self.redis.get(key)
        return int(attempts) if attempts else 0

    def _increment_attempts(self, email: str):
        """Increment failed email verification code attempts counter.

        Args:
            email (str): Email address pegged to the verification code.
        """
        key = f"attempts:{email}"
        if self.redis.exists(key):
            self.redis.incr(key)
        else:
            # set attempts key with same expiry as the verification code
            self.redis.setex(key, int(self.code_expiry.total_seconds()), 1)

    def _cleanup_verification(self, email: str):
        """Delete email verification code and attempts counter from Redis

        Args:
            email (str): Email address pegged to the verification code.
        """
        # delete the exact keys used for storing the code and attempts
        self.redis.delete(f"email:verification:{email}")
        self.redis.delete(f"attempts:{email}")


def get_email_verification_service() -> EmailVerificationService:
    """Factory function to create EmailVerificationService instance.

    Returns:
        EmailVerificationService: An instance of EmailVerificationService.
    """
    return EmailVerificationService(
        redis_client=redis_client,
        email_service=email_service,
        template_service=template_service,
    )


# =============================================================================
# Password Reset Service
# =============================================================================


class PasswordResetService:
    """Service for handling secure password reset functionality.
    
    This service implements a secure password reset flow with:
    - Cryptographically secure tokens (256-bit entropy)
    - One-hour token expiry
    - One-time use tokens (invalidated after use)
    - Rate limiting to prevent abuse
    - No user enumeration (same response for existing/non-existing emails)
    
    Attributes:
        TOKEN_EXPIRY: How long reset tokens remain valid (1 hour).
        MAX_REQUESTS_PER_HOUR: Maximum reset requests allowed per email per hour.
        MAX_TOKEN_ATTEMPTS: Maximum failed token validation attempts.
    """
    
    TOKEN_EXPIRY = timedelta(hours=1)
    MAX_REQUESTS_PER_HOUR = 3
    MAX_TOKEN_ATTEMPTS = 5
    
    def __init__(
        self,
        redis_client: Redis,
        email_service: EmailService,
        template_service: TemplateService,
        frontend_base_url: str = None,
    ):
        """Initialize the PasswordResetService.
        
        Args:
            redis_client: Redis client for token storage.
            email_service: Service for sending emails.
            template_service: Service for rendering email templates.
            frontend_base_url: Base URL for password reset links.
        """
        self.redis = redis_client
        self.email_service = email_service
        self.template_service = template_service
        self.frontend_base_url = frontend_base_url or os.getenv("FRONTEND_BASE_URL")
    
    def _generate_secure_token(self) -> str:
        """Generate a cryptographically secure reset token.
        
        Uses secrets.token_urlsafe() to generate a 64-character URL-safe
        token with 256 bits of entropy.
        
        Returns:
            str: A secure random token.
        """
        import secrets
        return secrets.token_urlsafe(48)  # 64 characters, 256 bits
    
    def _get_rate_limit_key(self, email: str) -> str:
        """Get Redis key for rate limiting by email."""
        return f"password_reset:rate:{email}"
    
    def _get_token_key(self, token: str) -> str:
        """Get Redis key for storing token data."""
        return f"password_reset:token:{token}"
    
    def _get_token_attempts_key(self, token: str) -> str:
        """Get Redis key for token validation attempts."""
        return f"password_reset:attempts:{token}"
    
    def _check_rate_limit(self, email: str) -> bool:
        """Check if the email has exceeded the rate limit.
        
        Args:
            email: The email address to check.
            
        Returns:
            bool: True if rate limit is exceeded, False otherwise.
        """
        key = self._get_rate_limit_key(email)
        count = self.redis.get(key)
        
        if count and int(count) >= self.MAX_REQUESTS_PER_HOUR:
            return True
        return False
    
    def _increment_rate_limit(self, email: str):
        """Increment the rate limit counter for an email.
        
        Args:
            email: The email address to increment.
        """
        key = self._get_rate_limit_key(email)
        
        if self.redis.exists(key):
            self.redis.incr(key)
        else:
            # Set with 1-hour expiry
            self.redis.setex(key, int(self.TOKEN_EXPIRY.total_seconds()), 1)
    
    def request_password_reset(self, email: str) -> bool:
        """Request a password reset for the given email.
        
        This method:
        1. Checks rate limiting
        2. Generates a secure token
        3. Stores the token in Redis with expiry
        4. Sends a password reset email
        
        For security, this method does NOT indicate whether the email
        exists in the system. The caller should always return a success
        message to prevent user enumeration attacks.
        
        Args:
            email: The email address to send the reset link to.
            
        Returns:
            bool: True if the reset was initiated (email exists and not rate limited),
                  False if rate limited. Note: Returns True even if email doesn't exist
                  to prevent enumeration.
        """
        with logfire.span(f"Password reset requested for: {email}"):
            # Check rate limit
            if self._check_rate_limit(email):
                logfire.warn(f"Password reset rate limit exceeded for: {email}")
                return False
            
            # Increment rate limit counter
            self._increment_rate_limit(email)
            
            # Generate secure token
            token = self._generate_secure_token()
            
            # Store token -> email mapping in Redis with expiry
            token_key = self._get_token_key(token)
            self.redis.setex(
                token_key,
                int(self.TOKEN_EXPIRY.total_seconds()),
                email
            )
            
            logfire.info(f"Password reset token generated for: {email}")
            
            # Generate reset link
            reset_link = f"{self.frontend_base_url}/reset-password?token={token}"
            
            # Send email
            html_content = self.template_service.render_password_reset_email(
                reset_link=reset_link,
                email=email
            )
            
            success = self.email_service.send_email(
                to=email,
                subject="Reset Your FindMyRent Password",
                content=html_content,
                content_type=ContentType.HTML,
            )
            
            if success:
                logfire.info(f"Password reset email sent to: {email}")
            else:
                logfire.error(f"Failed to send password reset email to: {email}")
            
            return True
    
    def validate_reset_token(self, token: str) -> Optional[str]:
        """Validate a password reset token.
        
        Args:
            token: The password reset token to validate.
            
        Returns:
            Optional[str]: The email address if valid, None otherwise.
        """
        # Check failed attempts
        attempts_key = self._get_token_attempts_key(token)
        attempts = self.redis.get(attempts_key)
        
        if attempts and int(attempts) >= self.MAX_TOKEN_ATTEMPTS:
            logfire.warn(f"Password reset token exceeded max attempts")
            # Invalidate the token
            self._invalidate_token(token)
            return None
        
        # Get email from token
        token_key = self._get_token_key(token)
        email = self.redis.get(token_key)
        
        if not email:
            # Increment failed attempts
            if self.redis.exists(attempts_key):
                self.redis.incr(attempts_key)
            else:
                self.redis.setex(attempts_key, int(self.TOKEN_EXPIRY.total_seconds()), 1)
            return None
        
        return email
    
    def complete_password_reset(self, token: str) -> Optional[str]:
        """Complete the password reset by invalidating the token.
        
        This should be called AFTER the password has been successfully updated.
        
        Args:
            token: The password reset token.
            
        Returns:
            Optional[str]: The email address if successful, None otherwise.
        """
        email = self.validate_reset_token(token)
        
        if email:
            # Invalidate the token (one-time use)
            self._invalidate_token(token)
            logfire.info(f"Password reset completed for: {email}")
        
        return email
    
    def _invalidate_token(self, token: str):
        """Invalidate a password reset token.
        
        Args:
            token: The token to invalidate.
        """
        self.redis.delete(self._get_token_key(token))
        self.redis.delete(self._get_token_attempts_key(token))


def get_password_reset_service() -> PasswordResetService:
    """Factory function to create PasswordResetService instance.
    
    Returns:
        PasswordResetService: An instance of PasswordResetService.
    """
    return PasswordResetService(
        redis_client=redis_client,
        email_service=email_service,
        template_service=template_service,
    )
