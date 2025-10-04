"""
Auth router for handling user authentication and authorization related endpoints.
"""

import logging
import os

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, status, APIRouter
from fastapi.responses import JSONResponse

from redis import Redis
from datetime import timedelta

from pathlib import Path

from services.verification import VerificationService
from services.template import TemplateService
from services.email import EmailService


from schema.verification import (
    EmailVerificationRequest,
    EmailVerificationCodeValidationRequest,
)

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
TEMPLATES_DIR = Path("templates")


email_service = EmailService(
    smtp_server=SMTP_SERVER,
    smtp_port=SMTP_PORT,
    username=SMTP_USERNAME,
    password=SMTP_PASSWORD,
    from_email=FROM_EMAIL,
)

template_service = TemplateService(templates_dir=TEMPLATES_DIR)

verification_service = VerificationService(
    redis_client=redis_client,
    email_service=email_service,
    template_service=template_service,
    code_length=CODE_LENGTH,
    code_expiry=CODE_EXPIRY,
)


@router.post("/verification/email", status_code=status.HTTP_200_OK)
async def send_verification_code(request: EmailVerificationRequest):
    """Send a verification code to the user's email."""
    try:
        redis_client.ping()
    except Exception as e:
        logger.error(f"Redis connection failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        )

    try:
        success = verification_service.send_verification_code(request.email)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification email",
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Verification code sent successfully",
                "email": request.email,
                "expires_in_minutes": CODE_EXPIRY.seconds // 60,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post("/api/verification/email/verify-code", status_code=status.HTTP_200_OK)
async def verify_code(request: EmailVerificationCodeValidationRequest):
    """Verify the code entered by the user."""
    try:
        redis_client.ping()
    except Exception as e:
        logger.error(f"Redis connection failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        )

    try:
        # Validate code format
        submitted_code = request.code.strip()
        if not submitted_code.isdigit() or len(submitted_code) != CODE_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid code format. Code must be {CODE_LENGTH} digits.",
            )

        # Verify code
        verification_service.verify_code(request.email, submitted_code)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Email verified successfully",
                "email": request.email,
                "verified": True,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )