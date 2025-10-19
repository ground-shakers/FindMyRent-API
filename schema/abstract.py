"""Contains models that describe the responses from the Abstract API
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Annotated, Literal, Optional


class PhoneCarrierDetails(BaseModel):
    name: Annotated[Optional[str], Field()]  # Carrier name
    line_type: Annotated[Optional[str], Field()]  # Line type (e.g., mobile, landline)
    mcc: Annotated[Optional[str], Field()]  # Mobile Country Code
    mnc: Annotated[Optional[str], Field()]  # Mobile Network Code


class PhoneLocationDetails(BaseModel):
    country_name: Annotated[Optional[str], Field(max_length=56)]
    country_code: Annotated[Optional[str], Field(max_length=4)]  # Country code that follows
    country_prefix: Annotated[
        str, Field()
    ]  # Phone number prefixes inclusive of the + at the front e.g. +264
    region: Annotated[Optional[str], Field(max_length=100)]
    city: Annotated[Optional[str], Field(max_length=100)]
    timezone: Annotated[Optional[str], Field(max_length=50)]  # Timezone in TZ database format e.g. Africa/Windhoek


class PhoneMessagingDetails(BaseModel):
    sms_domain: Annotated[Optional[str], Field()]  # SMS domain
    sms_email: Annotated[Optional[str], Field()]  # SMS email address


class PhoneValidityDetails(BaseModel):
    is_valid: Annotated[bool, Field()]  # Whether the phone number is valid
    line_status: Annotated[Optional[str], Field()]  # Line status (active, inactive, unknown)
    is_voip: Annotated[Optional[bool], Field()]  # Whether the phone number is a VoIP number
    minimum_age: Annotated[Optional[int], Field()]  # Minimum age of the phone number in years, null if not available


class PhoneRegistrationDetails(BaseModel):
    name: Annotated[Optional[str], Field()]
    type: Annotated[Optional[str], Field()]


class PhoneRiskDetails(BaseModel):
    risk_level: Annotated[
        Literal["low", "medium", "high"], Field()
    ]  # Risk level (low, medium, high)
    is_disposable: Annotated[Optional[bool], Field()]  # Whether the phone number is disposable
    is_abuse_detected: Annotated[Optional[bool], Field()]  # Whether abuse has been detected on the phone number


class PhoneBreachesDetails(BaseModel):
    total_breaches: Annotated[
        Optional[int], Field()
    ]  # Total number of breaches, null if none
    date_first_breached: Annotated[
        Optional[str], Field()
    ]  # Date of first breach in YYYY-MM-DD format, null if none
    date_last_breached: Annotated[
        Optional[str], Field()
    ]  # Date of last breach in YYYY-MM-DD format, null if none
    breached_domains: Annotated[Optional[list], Field()]  # List of breached domains


class PhoneNumberCountryDetails(BaseModel):
    code: Annotated[str, Field(max_length=2)] # Country code that follows ISO 3166-1 Alpha-2 standard
    name: Annotated[str, Field(max_length=56)]
    prefix: Annotated[str, Field(max_length=4)] # Phone number prefixes inclusive of the + at the front e.g. +264

class PhoneNumberFormat(BaseModel):
    international: Annotated[str, Field(max_length=17)] # North Korea reported with longest number of 17 characters
    national: Annotated[str, Field(max_length=20)]

class ValidatePhoneNumberResponse(BaseModel):
    """Model that describes the response from the `Abstract API` when a request to validate
    phone number is made
    """
    
    carrier: Annotated[str, Field()]
    country: Annotated[PhoneNumberCountryDetails, Field()]
    phone_number_format: Annotated[PhoneNumberFormat, Field()]
    location: Annotated[str, Field(max_length=56)]
    number_type: Annotated[str, Field()] # Phone number type
    valid: Annotated[bool, Field()]
    phone: Annotated[str, Field(max_length=17)]


class EmailValidationNested(BaseModel):
    """Describes the structure of the nested dictionaries returned by the `Abstract API`
    when a request to validate email is made
    """
    text: Annotated[str, Field()] # Textual representation of the boolean value
    value: Annotated[bool, Field()] # Boolean value

class ValidateEmailResponse(BaseModel):
    """Model that describes the response from the `Abstract API` when a request to validate
    an email is made
    """
    
    email: Annotated[EmailStr, Field()] # Maximum length of an email address is 254 characters
    is_valid_format: Annotated[EmailValidationNested, Field()] # Whether the email is valid in format
    deliverability: Annotated[Literal["DELIVERABLE", "UNDELIVERABLE", "UNKNOWN", "RISKY"], Field()] # Deliverability status of the email (DELIVERABLE, UNDELIVERABLE, RISKY, UNKNOWN)
    quality_score: Annotated[float, Field()] # Quality score of the email (0 to 1)
    is_free_email: Annotated[EmailValidationNested, Field()] # Whether the email is from a free email provider
    is_disposable_email: Annotated[EmailValidationNested, Field()] # Whether the email is from a disposable email provider
    is_role_email: Annotated[EmailValidationNested, Field()] # Whether the email is a role-based email (e.g., info@, support@)
    is_catch_all_email: Annotated[EmailValidationNested, Field()] # Whether the email domain is a catch-all domain
    is_mx_found: Annotated[EmailValidationNested, Field()] # Whether MX records were found for the email domain
    is_smtp_valid: Annotated[EmailValidationNested, Field()] # Whether the email domain has valid SMTP records

class PhoneIntelligenceResponse(BaseModel):
    """Model that describes the response from the `Abstract API` when a request to the phone intelligence API
    """
    phone_number: Annotated[str, Field(max_length=17)] # E.164 format, max length 17 characters
    phone_format: Annotated[PhoneNumberFormat, Field()]
    phone_carrier: Annotated[PhoneCarrierDetails, Field()]
    phone_location: Annotated[PhoneLocationDetails, Field()]
    phone_messaging: Annotated[PhoneMessagingDetails, Field()]
    phone_validation: Annotated[PhoneValidityDetails, Field()]
    phone_registration: Annotated[PhoneRegistrationDetails, Field()]
    phone_risk: Annotated[PhoneRiskDetails, Field()]
    phone_breaches: Annotated[PhoneBreachesDetails, Field()]