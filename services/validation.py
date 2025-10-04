"""Contains all the logic for controllers relating to validation of details
"""

from dotenv import load_dotenv

from schema.abstract import (
    ValidatePhoneNumberResponse,
    PhoneNumberCountryDetails,
    PhoneNumberFormat,
    ValidateEmailResponse,
    EmailValidationNested
)
from pydantic import ValidationError

from controllers.abstract_controller import send_validate_phone_number_request, send_validate_email_request

load_dotenv()
    
def is_phone_number_valid(phone_number: str) -> bool:
    """Validate `phone_number` with `Abstract API` and return
    whether it is valid or not

    Args:
        phone_number (str): Phone Number to validate against the `Abstract API`
        
    Returns:
        bool: `True` if phone number is valid else `False`
    """
    
    response =  send_validate_phone_number_request(phone_number=phone_number)

    try:
        
        country_details: dict = response.get("country")
        format_details: dict = response.get("format")

        validated_response = ValidatePhoneNumberResponse(
            carrier=response.get("carrier"),
            country=PhoneNumberCountryDetails(**country_details),
            phone_number_format=PhoneNumberFormat(**format_details),
            location=response.get("location"),
            phone=response.get("phone"),
            number_type=response.get("type"),
            valid=response.get("valid")
        )
        
        return validated_response.valid    
    except ValidationError as e:
        print(e.json())
    except Exception as e:
        print(e.__traceback__)
        

def is_email_valid(email: str) -> bool:
    """Validate `email` with `AbstractAPIController` and return
    whether it is valid or not. An email is considered valid if it is deliverable
    and has a valid format

    Args:
        email (str): Email to validate against the `Abstract API`
        
    Returns:
        bool: `True` if email is valid and deliverable, else `False`
    """
    
    response =  send_validate_email_request(email=email)

    try:
        validated_response = ValidateEmailResponse(
            email=response.get("email"),
            is_valid_format=EmailValidationNested(**response.get("is_valid_format")),
            deliverability=response.get("deliverability"),
            quality_score=response.get("quality_score"),
            is_free_email=EmailValidationNested(**response.get("is_free_email")),
            is_disposable_email=EmailValidationNested(**response.get("is_disposable_email")),
            is_role_email=EmailValidationNested(**response.get("is_role_email")),
            is_catch_all_email=EmailValidationNested(**response.get("is_catch_all_email")),
            is_mx_found=EmailValidationNested(**response.get("is_mx_found")),
            is_smtp_valid=EmailValidationNested(**response.get("is_smtp_valid"))
        )
        
        # An email is considered valid if it is deliverable and has a valid format
        return validated_response.deliverability == "DELIVERABLE" and validated_response.is_valid_format.value
    except ValidationError as e:
        print(e.json())
    except Exception as e:
        print(e.__traceback__)