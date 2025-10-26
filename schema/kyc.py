from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ParsedAddress(BaseModel):
    """Parsed address information from ID verification."""
    id: str
    address_type: Optional[str] = None
    city: Optional[str] = None
    label: Optional[str] = None
    region: Optional[str] = None
    street_1: Optional[str] = None
    street_2: Optional[str] = None
    postal_code: Optional[str] = None
    raw_results: Optional[Dict[str, Any]] = None


class Warning(BaseModel):
    """Warning information from verification."""
    risk: str
    additional_data: Optional[Any] = None
    log_type: str
    short_description: str
    long_description: str


class IDVerification(BaseModel):
    """ID verification details."""
    status: str
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    personal_number: Optional[str] = None
    portrait_image: Optional[str] = None
    front_image: Optional[str] = None
    front_video: Optional[str] = None
    back_image: Optional[str] = None
    back_video: Optional[str] = None
    full_front_image: Optional[str] = None
    full_back_image: Optional[str] = None
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    expiration_date: Optional[str] = None
    date_of_issue: Optional[str] = None
    issuing_state: Optional[str] = None
    issuing_state_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    formatted_address: Optional[str] = None
    place_of_birth: Optional[str] = None
    marital_status: Optional[str] = None
    nationality: Optional[str] = None
    parsed_address: Optional[ParsedAddress] = None
    extra_files: Optional[List[str]] = None
    warnings: Optional[List[Warning]] = None


class ExpectedDetails(BaseModel):
    """Expected user details."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ContactDetails(BaseModel):
    """Contact details."""
    email: Optional[str] = None
    email_lang: Optional[str] = None


class Review(BaseModel):
    """Review information."""
    user: str
    new_status: str
    comment: str
    created_at: datetime


class Decision(BaseModel):
    """Decision information for verification session."""
    session_id: str
    session_number: Optional[int] = None
    session_url: Optional[str] = None
    status: str
    workflow_id: str
    features: Optional[List[str]] = None
    vendor_data: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    expected_details: Optional[ExpectedDetails] = None
    contact_details: Optional[ContactDetails] = None
    callback: Optional[str] = None
    id_verification: Optional[IDVerification] = None
    reviews: Optional[List[Review]] = None
    created_at: datetime


class DiditWebhookPayload(BaseModel):
    """Didit webhook payload model."""
    session_id: str
    status: str  # "Approved", "Declined", "In Progress", etc.
    webhook_type: str
    created_at: int
    timestamp: int
    workflow_id: str
    vendor_data: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    decision: Optional[Decision] = None


class DiditWebhookResponse(BaseModel):
    """Didit webhook response model."""
    success: bool
    message: str
    session_id: str
