"""
Auth router for handling user authentication and authorization related endpoints.
"""

import logging
import os

from dotenv import load_dotenv

from fastapi import HTTPException, status, APIRouter
from fastapi.responses import JSONResponse
from fastapi.requests import Request

from redis import Redis
from datetime import timedelta

from pathlib import Path

from services.verification import EmailVerificationService
from services.template import TemplateService
from services.email import EmailService

from models.users import User
from schema.users import UserInDB

from beanie.operators import And

from schema.verification import EmailVerificationCodeValidationRequest, VerifiedEmailResponse

from middleware.rate_limiting import limiter

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

verification_service = EmailVerificationService(
    redis_client=redis_client,
    email_service=email_service,
    template_service=template_service,
    code_length=CODE_LENGTH,
    code_expiry=CODE_EXPIRY,
)


@router.post("/verification/email", status_code=status.HTTP_200_OK, response_model=VerifiedEmailResponse)
@limiter.limit("5/minute")
async def verify_email_code(payload: EmailVerificationCodeValidationRequest, request: Request):
    """This endpoint verifies the email verification code sent to the user's email address.
    Once the code is verified, the user's account is activated.
    """
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
        submitted_code = payload.code.strip()
        if not submitted_code.isdigit() or len(submitted_code) != CODE_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid code format. Code must be {CODE_LENGTH} digits.",
            )

        # Verify code
        success = verification_service.verify_code(payload.email, submitted_code)

        if not success:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid verification code"},
            )
            
        # Activate user account
        user = await User.find_one(And(User.email == payload.email, User.is_active == False), with_children=True)

        if not user:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "User not found or already verified"},
            )
            
        user.is_active = True
        await user.save()

        return VerifiedEmailResponse(
            user=UserInDB(**user.model_dump(exclude=["is_active", "password"])),  # Convert to UserInDB schema
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sorry we can't verify your email at the moment. Please try again later.",
        )