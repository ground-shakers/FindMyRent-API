import pytz

from enum import Enum

from datetime import datetime

from pydantic import Field, BaseModel, field_serializer

from typing import Annotated, List, Literal
from beanie import Document, PydanticObjectId


class PropertyType(str, Enum):
    """Types of property listings."""
    SINGLE = "single"
    SHARED = "shared"
    STUDIO = "studio"
    FLAT = "flat"
    ROOM = "room"


class ListingType(str, Enum):
    """Listing types."""
    RENT = "rent"
    SALE = "sale"


class Amenities(str, Enum):
    """All amenities available at a property"""
    POOL = "swimming pool"


class ListingLocation(BaseModel):
    """Location details for a property listing.
    """
    address: Annotated[str, Field(max_length=200)]
    city: Annotated[str, Field(max_length=100)]
    state: Annotated[str, Field(max_length=100)]
    
    
class LandLordDetailsSummary(BaseModel):
    landlord_id: Annotated[str, Field()]
    first_name: Annotated[str, Field()]
    last_name: Annotated[str, Field()]


class Listing(Document):
    description: Annotated[str, Field(max_length=1000)]
    price: Annotated[float, Field(gt=0)]
    location: Annotated[ListingLocation, Field()]
    bedrooms: Annotated[int, Field(ge=0, default=0)]
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(pytz.utc))]
    landlord: Annotated[LandLordDetailsSummary, Field()]
    amenities: Annotated[List[str], Field(default=[])]
    updated_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(pytz.utc))]
    property_type: Annotated[PropertyType, Field(default=PropertyType.SINGLE)]
    verified: Annotated[bool, Field(default=False)]
    images: Annotated[List[str], Field(default=[])]  # List of image URLs
    available: Annotated[bool, Field(default=False)]  # Availability status
    proof_of_ownership: Annotated[List[str], Field(default=[])]  # List of URLs to proof of ownership documents
