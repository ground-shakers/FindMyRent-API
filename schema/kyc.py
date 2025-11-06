"""Schema for KYC verification.
"""

from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl, EmailStr

from typing import Annotated, List, Optional


class KYCResponseBase(BaseModel):
    session_id: Annotated[str, Field(description="Unique identifier for the KYC session")]
    workflow_id: Annotated[str, Field(description="ID of the workflow associated with the KYC session")]
    vendor_data: Annotated[str, Field(description="ID of the user in the FindMyRent system")]
    metadata: Annotated[dict | None, Field(description="Additional metadata for the KYC session")]
    status: Annotated[str, Field(description="Current status of the KYC session")]

class CreateKYCSessionResponse(KYCResponseBase):
    """Model representing the response from Didit for creating a KYC session."""
    
    session_number: Annotated[int, Field(description="Numeric identifier for the KYC session")]
    session_token: Annotated[str, Field(description="Token associated with the KYC session")]
    callback: Annotated[HttpUrl | None, Field(description="Redirect URL once verification is complete")]
    url: Annotated[HttpUrl, Field(description="URL for the KYC session")]


class AddressCoordinates(BaseModel):
    latitude: Annotated[Optional[float], Field(description="Latitude of the address", default=None)]
    longitude: Annotated[Optional[float], Field(description="Longitude of the address", default=None)]


class AddressViewPortCoordinateDetails(BaseModel):
    northeast: Annotated[
        Optional[AddressCoordinates],
        Field(description="Northeast coordinates of the viewport", default=None),
    ]
    southwest: Annotated[
        Optional[AddressCoordinates],
        Field(description="Southwest coordinates of the viewport", default=None),
    ]


class AddressGeometry(BaseModel):
    location: Annotated[
        Optional[AddressCoordinates],
        Field(description="Coordinates of the address location", default=None),
    ]
    location_type: Annotated[
        Optional[str],
        Field(description="Type of location (e.g., ROOFTOP, RANGE_INTERPOLATED)", default=None),
    ]
    viewport: Annotated[
        Optional[AddressViewPortCoordinateDetails],
        Field(description="Viewport coordinates for the address", default=None),
    ]


class AddressRawResults(BaseModel):
    geometry: Annotated[
        Optional[AddressGeometry], Field(description="Geometry details of the address", default=None)
    ]


class ParsedAddressDetails(BaseModel):
    id: Annotated[Optional[str], Field(description="Unique identifier for the address", default=None)]
    address_type: Annotated[
        Optional[str],
        Field(description="Type of address (e.g., residential, business)", default=None),
    ]
    city: Annotated[Optional[str], Field(description="City of the address", default=None)]
    label: Annotated[Optional[str], Field(description="Label for the address", default=None)]
    region: Annotated[Optional[str], Field(description="Region of the address", default=None)]
    street_1: Annotated[
        Optional[str], Field(description="First line of the street address", default=None)
    ]
    street_2: Annotated[
        Optional[str], Field(description="Second line of the street address", default=None)
    ]
    postal_code: Annotated[
        Optional[str], Field(description="Postal code of the address", default=None)
    ]
    raw_results: Annotated[
        Optional[AddressRawResults], Field(description="Raw results of the address parsing", default=None)
    ]


class IDVerificationWarnings(BaseModel):
    risk: Annotated[str, Field(description="Risk level associated with the verification")]
    additional_data: Annotated[Optional[str | int | float | HttpUrl], Field(description="Additional data related to the verification warnings")]
    log_type: Annotated[str, Field(description="Type of log associated with the warnings")]
    short_description: Annotated[str, Field(description="Short description of the warning")]
    long_description: Annotated[str, Field(description="Longer description of the warning")]


class KYCSessionReviewDetails(BaseModel):
    user: Annotated[
        EmailStr,
        Field(description="Email of the user who performed the review"),
    ]
    new_status: Annotated[
        str, Field(description="New status assigned in the review")
    ]
    comment: Annotated[
        Optional[str], Field(description="Comment provided in the review", default=None)
    ]
    created_at: Annotated[
        Optional[str], Field(description="Timestamp when the review was created", default=None)
    ]


class IDVerificationDetails(BaseModel):
    """Model representing the ID verification details from the KYC webhook."""

    status: Annotated[str, Field(description="Status of the ID verification")]
    document_type: Annotated[str, Field(description="Type of document used for verification")]
    document_number: Annotated[str, Field(description="Document number used for verification")]
    personal_number: Annotated[
        Optional[str],
        Field(description="Personal number associated with the document", default=None),
    ]
    portrait_image: Annotated[Optional[HttpUrl], Field(description="URL of the portrait image", default=None)]
    front_image: Annotated[Optional[HttpUrl], Field(description="URL of the front image", default=None)]
    front_video: Annotated[Optional[HttpUrl], Field(description="URL of the front video", default=None)]
    back_image: Annotated[Optional[HttpUrl], Field(description="URL of the back image", default=None)]
    back_video: Annotated[Optional[HttpUrl], Field(description="URL of the back video", default=None)]
    full_front_image: Annotated[Optional[HttpUrl], Field(description="URL of the full front image", default=None)]
    full_back_image: Annotated[Optional[HttpUrl], Field(description="URL of the full back image", default=None)]
    date_of_birth: Annotated[str, Field(description="Date of birth of the user")]
    age: Annotated[Optional[int], Field(description="Age of the user", default=None)]
    expiration_date: Annotated[Optional[str], Field(description="Expiration date of the document", default=None)]
    date_of_issue: Annotated[str, Field(description="Date of issue of the document")]
    issuing_state: Annotated[Optional[str], Field(description="State issuing the document", default=None)]
    issuing_state_name: Annotated[Optional[str], Field(description="Name of the state issuing the document", default=None)]
    first_name: Annotated[str, Field(description="First name of the user")]
    last_name: Annotated[str, Field(description="Last name of the user")]
    full_name: Annotated[str, Field(description="Full name of the user")]
    gender: Annotated[str, Field(description="Gender of the user")]
    address: Annotated[Optional[str], Field(description="Address of the user", default=None)]
    formatted_address: Annotated[
        Optional[str], Field(description="Formatted address of the user", default=None)
    ]
    place_of_birth: Annotated[Optional[str], Field(description="Place of birth of the user")]
    marital_status: Annotated[
        Optional[str], Field(description="Marital status of the user", default=None)
    ]
    nationality: Annotated[str, Field(description="Nationality of the user")]
    parsed_address: Annotated[
        Optional[ParsedAddressDetails],
        Field(description="Parsed address details of the user", default=None),
    ]
    extra_files: Annotated[
        List[HttpUrl],
        Field(description="List of URLs for extra files provided", default=[]),
    ]
    warnings: Annotated[
        Optional[List[IDVerificationWarnings]],
        Field(description="List of warnings associated with the KYC verification", default=None),
    ]


class KYCVerificationDecisionDetails(KYCResponseBase):
    """Model representing the decision details from the KYC webhook."""

    status: Annotated[str, Field(description="Final status of the KYC session")]
    session_number: Annotated[
        int, Field(description="Numeric identifier for the KYC session")
    ]
    session_url: Annotated[
        HttpUrl, Field(description="URL for the KYC session")
    ]
    status: Annotated[str, Field(description="Status of the ID verification")]
    features: Annotated[
        List[str], Field(description="List of features verified in the ID verification")
    ]
    expected_details: Annotated[
        dict[str, str | int],
        Field(description="User details Expected for the ID verification"),
    ]
    contact_details: Annotated[
        dict[str, str],
        Field(description="Contact details of the user who was verified"),
    ]
    callback: Annotated[
        HttpUrl | None, Field(description="Redirect URL once verification is complete", default=None)
    ]
    id_verification: Annotated[IDVerificationDetails, Field(description="ID verification details from the KYC session")]
    reviews: Annotated[List[KYCSessionReviewDetails], Field(description="Reviews associated with the KYC session", default=[])]
    created_at: Annotated[str, Field(description="Timestamp when the KYC session was created")]


class KYCWebhookResponse(KYCResponseBase):
    """Model representing the response from Didit webhook for KYC session updates."""

    webhook_type: Annotated[str, Field(description="Type of webhook event")]
    created_at: Annotated[int, Field(description="Timestamp when the KYC session was created")]
    timestamp: Annotated[int, Field(description="Timestamp of the KYC session update")]
    decision: Annotated[
        Optional[KYCVerificationDecisionDetails],
        Field(description="Details of the decision made in the KYC session", default=None),
    ]