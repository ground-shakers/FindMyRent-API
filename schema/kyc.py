"""Schema for KYC verification.
"""

from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl
from typing import Annotated

from pydantic import BaseModel


class CreateKYCSessionResponse(BaseModel):
    """Model representing the response from Didit for creating a KYC session."""
    
    session_id: Annotated[str, Field(description="Unique identifier for the KYC session")]
    session_number: Annotated[int, Field(description="Numeric identifier for the KYC session")]
    session_token: Annotated[str, Field(description="Token associated with the KYC session")]
    vendor_data: Annotated[str, Field(description="ID of the user in the FindMyRent system")]
    metadata: Annotated[dict | None, Field(description="Additional metadata for the KYC session")]
    status: Annotated[str, Field(description="Current status of the KYC session")]
    workflow_id: Annotated[str, Field(description="ID of the workflow associated with the KYC session")]
    callback: Annotated[HttpUrl | None, Field(description="Redirect URL once verification is complete")]
    url: Annotated[HttpUrl, Field(description="URL for the KYC session")]