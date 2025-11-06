"""Contains all the logic for controllers relating to validation of details"""

import logfire

from dotenv import load_dotenv

from schema.abstract import (
    PhoneNumberFormat,
    ValidateEmailResponse,
    EmailValidationNested,
    PhoneIntelligenceResponse,
    PhoneBreachesDetails,
    PhoneCarrierDetails,
    PhoneLocationDetails,
    PhoneMessagingDetails,
    PhoneRegistrationDetails,
    PhoneRiskDetails,
    PhoneValidityDetails,
)
from pydantic import ValidationError

from fastapi import HTTPException
from fastapi import status

from controllers.abstract_controller import (
    send_validate_email_request,
    send_phone_verification_request,
)

load_dotenv()


def is_phone_number_valid(phone_number: str) -> tuple[bool, str]:
    """Validate `phone_number` with `AbstractAPIController` and return
    whether it is valid or not along with a description of the validity

    Args:
        phone_number (str): Phone Number to validate against the `AbstractAPIController`

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating validity and a description
    """

    response = send_phone_verification_request(phone_number=phone_number)

    try:

        validated_response = PhoneIntelligenceResponse(
            phone_number=response.get("phone_number"),
            phone_format=PhoneNumberFormat(**response.get("phone_format")),
            phone_carrier=PhoneCarrierDetails(**response.get("phone_carrier")),
            phone_location=PhoneLocationDetails(**response.get("phone_location")),
            phone_messaging=PhoneMessagingDetails(**response.get("phone_messaging")),
            phone_validation=PhoneValidityDetails(**response.get("phone_validation")),
            phone_registration=PhoneRegistrationDetails(
                **response.get("phone_registration")
            ),
            phone_risk=PhoneRiskDetails(**response.get("phone_risk")),
            phone_breaches=PhoneBreachesDetails(**response.get("phone_breaches")),
        )

        # A phone number is considered valid it has the following attributes
        # - valid format
        # - not a voip number
        # - line type is "mobile"
        # - line status is "active"
        # - is not disposable
        # - no abuse detected
        # - risk level is "low"

        is_valid_phone_number = (
            validated_response.phone_validation.is_valid
            and not validated_response.phone_validation.is_voip
            and validated_response.phone_validation.line_status == "active"
        )

        is_verified_phone_number = (
            validated_response.phone_carrier.line_type == "mobile"
            and not validated_response.phone_risk.is_disposable
            and not validated_response.phone_risk.is_abuse_detected
            and validated_response.phone_risk.risk_level == "low"
        )

        if not is_valid_phone_number:
            return False, "Invalid phone number format or inactive line"

        if not is_verified_phone_number:
            return False, "Phone number could not be verified"

        return True, "Valid phone number"
    except ValidationError as e:
        logfire.error(
            f"Got a validation error for phone number validation response: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"We could not validate your phone number. Make sure the number is correct and try again.",
        )
    except Exception as e:
        logfire.error(f"Unexpected error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sorry we can't validate your phone number right now. Try again later.",
        )


def is_email_valid(email: str) -> bool:
    """Validate `email` with `AbstractAPIController` and return
    whether it is valid or not. An email is considered valid if it is deliverable
    and has a valid format

    Args:
        email (str): Email to validate against the `Abstract API`

    Returns:
        bool: `True` if email is valid and deliverable, else `False`
    """

    response = send_validate_email_request(email=email)

    try:
        validated_response = ValidateEmailResponse(
            email=response.get("email"),
            is_valid_format=EmailValidationNested(**response.get("is_valid_format")),
            deliverability=response.get("deliverability"),
            quality_score=response.get("quality_score"),
            is_free_email=EmailValidationNested(**response.get("is_free_email")),
            is_disposable_email=EmailValidationNested(
                **response.get("is_disposable_email")
            ),
            is_role_email=EmailValidationNested(**response.get("is_role_email")),
            is_catch_all_email=EmailValidationNested(
                **response.get("is_catchall_email")
            ),
            is_mx_found=EmailValidationNested(**response.get("is_mx_found")),
            is_smtp_valid=EmailValidationNested(**response.get("is_smtp_valid")),
        )

        # An email is considered valid if it is deliverable and has a valid format

        is_valid = (
            validated_response.deliverability == "DELIVERABLE"
            and validated_response.is_valid_format.value
        )
        return is_valid
    except ValidationError as e:
        print("Got a validation error for email validation response")
        return False
    except Exception as e:
        print(f"Something went wrong with email validation service {e}")
        return False
