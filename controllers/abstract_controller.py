"""Contains logic that communicates with the `Abstract API` for
contact details validation
"""
import os
import httpx

from pprint import pprint

from dotenv import load_dotenv

load_dotenv(override=True)

def send_validate_phone_number_request(phone_number: str) -> dict:
    """Validate `phone_number` with `Abstract API`

    Args:
        phone_number (str): Phone Number to validate against the `Abstract API`
    """
    PHONE_NUMBER_VALIDATION_API_KEY = os.getenv("ABSTRACT_PHONE_VALIDATION_API_KEY")

    if not PHONE_NUMBER_VALIDATION_API_KEY:
        raise Exception("Failed to retrieve Abstract API Key")

    parameters = {"api_key": PHONE_NUMBER_VALIDATION_API_KEY, "phone": phone_number}

    with httpx.Client() as client:
        response = client.get(
            url="https://phonevalidation.abstractapi.com/v1/",
            params=parameters
        )

    try:
        if not response.status_code == 200:
            raise Exception

        return response.json()
    except Exception as e:
        print(f"Validation request to Abstract API failed with status code {response.status_code}")
        print(e.__dict__)

def send_validate_email_request(email: str) -> dict:
    """Validate `email` with `Abstract API`

    Args:
        email (str): Email to validate against the `Abstract API`
    """
    EMAIL_VALIDATION_API_KEY = os.getenv("ABSTRACT_EMAIL_VALIDATION_API_KEY")

    if not EMAIL_VALIDATION_API_KEY:
        raise Exception("Failed to retrieve Abstract API Key")

    parameters = {
        "api_key": EMAIL_VALIDATION_API_KEY,
        "email": email
    }

    with httpx.Client() as client:
        response = client.get(
            url="https://emailvalidation.abstractapi.com/v1/",
            params=parameters
        )

    try:
        if not response.status_code == 200:
            raise Exception
        
        return response.json()
    except Exception as e:
        print(f"Validation request to Abstract API failed with status code {response.status_code}")
        print(e.__dict__)


pprint(send_validate_email_request("noblemateus@gmail.com"))
