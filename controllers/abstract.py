"""Contains logic that communicates with the `Abstract API` for
contact details validation
"""
import os
import httpx

from pprint import pprint

from dotenv import load_dotenv

from fastapi import HTTPException
from fastapi import status

load_dotenv(override=True)

def send_validate_email_request(email: str) -> dict:
    """Validate `email` with `Abstract API`

    Args:
        email (str): Email to validate against the `Abstract API`
    """
    EMAIL_VALIDATION_API_KEY = os.getenv("ABSTRACT_EMAIL_VALIDATION_API_KEY")

    if not EMAIL_VALIDATION_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong",
        )

    parameters = {
        "api_key": EMAIL_VALIDATION_API_KEY,
        "email": email
    }

    try:

        with httpx.Client() as client:
            response = client.get(
                url="https://emailvalidation.abstractapi.com/v1/",
                params=parameters
            )

        if response.status_code == 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect email format",
            )

        if not response.status_code == 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Sorry we can't validate your email right now",
            )
        return response.json()
    except Exception as e:
        print(f"Validation request to Abstract API failed {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sorry we can't validate your email right now"
        )


def send_phone_verification_request(phone_number: str) -> dict:
    """Send a phone verification request using `Abstract API`

    Args:
        phone_number (str): Phone Number to send verification request for
    """
    PHONE_VERIFICATION_API_KEY = os.getenv("ABSTRACT_PHONE_VERIFICATION_API_KEY")

    if not PHONE_VERIFICATION_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong",
        )

    parameters = {
        "api_key": PHONE_VERIFICATION_API_KEY,
        "phone": phone_number
    }

    try:

        with httpx.Client() as client:
            response = client.get(
                url="https://phoneintelligence.abstractapi.com/v1/", params=parameters
            )

        if response.status_code == 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect phone number format",
            )

        if response.status_code == 500:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Sorry cannot verify your phone number",
            )

        return response.json()
    except Exception as e:
        print(f"Validation request to Abstract API failed with status code {response.status_code}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Sorry we can't validate your phone number right now",
        )
