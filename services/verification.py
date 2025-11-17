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
