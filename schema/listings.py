"""Pydantic schemas for property listing search and filter functionality."""

from pydantic import BaseModel, Field
from typing import Annotated, Optional, List, Literal
from decimal import Decimal

from models.listings import PropertyType


class ListingSearchRequest(BaseModel):
    """Request schema for searching property listings.
    
    All fields are optional - omitting a field means no filter is applied for that criteria.
    """
    
    # Text search
    query: Annotated[
        Optional[str], 
        Field(default=None, max_length=200, description="Text search on property description")
    ]
    
    # Price range
    min_price: Annotated[
        Optional[Decimal], 
        Field(default=None, gt=0, description="Minimum rental price")
    ]
    max_price: Annotated[
        Optional[Decimal], 
        Field(default=None, gt=0, description="Maximum rental price")
    ]
    
    # Location filters
    city: Annotated[
        Optional[str], 
        Field(default=None, max_length=100, description="Filter by city")
    ]
    state: Annotated[
        Optional[str], 
        Field(default=None, max_length=100, description="Filter by state")
    ]
    
    # Property attributes
    property_type: Annotated[
        Optional[PropertyType], 
        Field(default=None, description="Filter by property type")
    ]
    min_bedrooms: Annotated[
        Optional[int], 
        Field(default=None, ge=0, description="Minimum number of bedrooms")
    ]
    max_bedrooms: Annotated[
        Optional[int], 
        Field(default=None, ge=0, description="Maximum number of bedrooms")
    ]
    
    # Amenities filter - listings must have ALL specified amenities
    amenities: Annotated[
        Optional[List[str]], 
        Field(default=None, description="Required amenities (listing must have all)")
    ]
    
    # Availability filter
    available_only: Annotated[
        bool, 
        Field(default=True, description="Only return available listings")
    ]
    
    # Pagination
    offset: Annotated[
        int, 
        Field(default=0, ge=0, description="Number of listings to skip")
    ]
    limit: Annotated[
        int, 
        Field(default=20, ge=1, le=100, description="Maximum listings to return")
    ]
    
    # Sorting
    sort_by: Annotated[
        Literal["price", "created_at", "bedrooms"], 
        Field(default="created_at", description="Field to sort by")
    ]
    sort_order: Annotated[
        Literal["asc", "desc"], 
        Field(default="desc", description="Sort order (ascending or descending)")
    ]


class ListingSearchResult(BaseModel):
    """Individual listing result in search response."""
    
    id: str
    description: str
    price: float
    location: dict
    bedrooms: int
    property_type: str = Field(alias="propertyType")
    amenities: List[str]
    images: List[str]
    available: bool
    created_at: str = Field(alias="createdAt")
    
    class Config:
        populate_by_name = True


class ListingSearchResponse(BaseModel):
    """Response schema for listing search results."""
    
    listings: List[dict]  # Serialized listings
    total: Annotated[int, Field(description="Total number of matching listings")]
    offset: Annotated[int, Field(description="Current offset")]
    limit: Annotated[int, Field(description="Current limit")]
    has_more: Annotated[bool, Field(description="Whether more results exist")]
