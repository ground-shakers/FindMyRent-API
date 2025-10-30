"""Schema for KYC verification.
"""

from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl
from typing import Annotated

from pydantic import BaseModel


class CreateSesssionResponse(BaseModel):
    """Model representing the response from Didit for creating a KYC session."""
    
    session_id: Annotated[str, Field()]
    session_number: Annotated[int, Field()]
    session_token: Annotated[str, Field()]
    vendor_data: Annotated[str, Field()]
    metadata: Annotated[dict | None, Field()]
    status: Annotated[str, Field()]
    workflow_id: Annotated[str, Field()]
    callback: Annotated[str | None, Field()]
    url: Annotated[str, HttpUrl()]