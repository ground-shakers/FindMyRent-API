"""Service for handling email verification."""

import os

from fastapi import status
from fastapi.exceptions import HTTPException

from models.helpers import ContentType

from datetime import timedelta

from .template import TemplateService
from .email import EmailService

from typing import Optional

from redis import Redis

from dotenv import load_dotenv

from fastapi import HTTPException, status

from pathlib import Path

from security.helpers import generate_verification_code

load_dotenv()

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
TEMPLATES_DIR = Path("templates")


email_service = EmailService(
    smtp_server=SMTP_SERVER,
    smtp_port=SMTP_PORT,
    username=SMTP_USERNAME,
    password=SMTP_PASSWORD,
    from_email=FROM_EMAIL,
)

template_service = TemplateService(templates_dir=TEMPLATES_DIR)

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
        """Generate and send verification code to email."""
        # Note: Rate limiting is now handled by slowapi decorator at the route level

        # Generate and store code
        code = generate_verification_code()
        self._store_code(email, code)

        # Send email
        html_content = self.template_service.render_verification_email(code, email)
        return self.email_service.send_email(
            to=email,
            subject="Your Verification Code",
            content=html_content,
            content_type=ContentType.HTML,
        )

    def verify_code(self, email: str, code: str) -> bool:
        """Verify the code against stored value."""
        # Check failed attempts
        if not self._check_attempts(email):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Too many failed attempts. Please request a new verification code.",
            )

        # Get stored code
        stored_code = self._get_stored_code(email)

        if not stored_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Verification code not found or expired. Please request a new code.",
            )

        # Verify code
        if code != stored_code:
            self._increment_attempts(email)
            remaining = 5 - self._get_attempts(email)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid verification code. {remaining} attempts remaining.",
            )

        # Success - cleanup
        self._cleanup_verification(email)
        return True

    def _store_code(self, email: str, code: str):
        """Store verification code in Redis."""
        key = f"verification:{email}"
        self.redis.setex(key, self.code_expiry, code)

    def _get_stored_code(self, email: str) -> Optional[str]:
        """Get stored verification code."""
        key = f"verification:{email}"
        code = self.redis.get(key)
        return code if code else None

    def _check_attempts(self, email: str) -> bool:
        """Check if attempts limit exceeded."""
        attempts = self._get_attempts(email)
        if attempts >= 5:
            self._cleanup_verification(email)
            return False
        return True

    def _get_attempts(self, email: str) -> int:
        """Get number of failed attempts."""
        key = f"attempts:{email}"
        attempts = self.redis.get(key)
        return int(attempts) if attempts else 0

    def _increment_attempts(self, email: str):
        """Increment failed attempts counter."""
        key = f"attempts:{email}"
        if self.redis.exists(key):
            self.redis.incr(key)
        else:
            self.redis.setex(key, self.code_expiry, 1)

    def _cleanup_verification(self, email: str):
        """Clean up all verification-related keys."""
        self.redis.delete(f"verification:{email}")
        self.redis.delete(f"attempts:{email}")

def get_email_verification_service() -> EmailVerificationService:
    """Factory function to create EmailVerificationService instance."""
    return EmailVerificationService(
        redis_client=redis_client,
        email_service=email_service,
        template_service=template_service,
    )
