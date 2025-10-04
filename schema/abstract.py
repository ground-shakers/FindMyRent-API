"""Contains models that describe the responses from the Abstract API
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Annotated, Literal


class PhoneNumberCountryDetails(BaseModel):
    code: Annotated[str, Field(max_length=2)] # Country code that follows ISO 3166-1 Alpha-2 standard
    name: Annotated[str, Field(max_length=56)]
    prefix: Annotated[str, Field(max_length=4)] # Phone number prefixes inclusive of the + at the front e.g. +264

class PhoneNumberFormat(BaseModel):
    international: Annotated[str, Field(max_length=17)] # North Korea reported with longest number of 17 characters
    local: Annotated[str, Field(max_length=20)]

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