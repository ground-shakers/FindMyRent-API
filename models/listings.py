import pytz

from enum import Enum

from datetime import datetime

from pydantic import Field

from typing import Annotated, List, Literal
from beanie import Document, Link



class PropertyType(str, Enum):
    SINGLE = "single"
    SHARED = "shared"
    STUDIO = "studio"
    FLAT = "flat"
    ROOM = "room"


class Listing(Document):
    title: Annotated[str, Field(max_length=100)]
    description: Annotated[str, Field(max_length=1000)]
    price: Annotated[float, Field(gt=0)]
    location: Annotated[str, Field(max_length=100)]
    land_lord: Annotated[str, Field()]
    bedrooms: Annotated[int, Field(ge=0, default=0)]
    created_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(pytz.utc))]
    updated_at: Annotated[datetime, Field(default_factory=lambda: datetime.now(pytz.utc))]
    currency: Annotated[str, Field(max_length=3, default="NAD")]
    listing_type: Annotated[PropertyType, Field(default=PropertyType.SINGLE)]  # e.g., rent, sale
    verified: Annotated[bool, Field(default=False)]
    images: Annotated[List[str], Field(default=[])]  # List of image URLs
    available: Annotated[bool, Field(default=True)]  # Availability status
