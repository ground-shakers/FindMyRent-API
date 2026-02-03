"""
Favorites router for handling user favorites endpoints.
"""

import logfire

from fastapi import APIRouter, status, Depends, Security, Query, Path

from models.users import LandLord

from security.helpers import get_current_active_user
from services.favorites_service import get_favorites_service, FavoritesService

from typing import Annotated


router = APIRouter(
    prefix="/api/v1/favorites",
    tags=["Favorites"],
)


@router.post("/{listing_id}", status_code=status.HTTP_201_CREATED)
async def add_to_favorites(
    listing_id: Annotated[
        str,
        Path(
            description="The unique identifier of the listing to favorite",
            min_length=24,
            max_length=24,
        ),
    ],
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    favorites_service: Annotated[FavoritesService, Depends(get_favorites_service)],
):
    """Add a property listing to favorites.
    
    Saves a verified listing to the user's favorites list for quick access later.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | listing_id | string (24 chars) | MongoDB ObjectId of the listing |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (201 Created)
    ```json
    {
        "message": "Listing added to favorites",
        "listing_id": "507f1f77bcf86cd799439011",
        "total_favorites": 5
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 404 | Listing not found | `{"detail": "Listing not found"}` |
    | 409 | Already favorited | `{"detail": "Listing already in favorites"}` |
    | 500 | Internal error | `{"detail": "An unexpected error occurred"}` |
    """
    return await favorites_service.add_favorite(listing_id, current_user)


@router.delete("/{listing_id}")
async def remove_from_favorites(
    listing_id: Annotated[
        str,
        Path(
            description="The unique identifier of the listing to remove",
            min_length=24,
            max_length=24,
        ),
    ],
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    favorites_service: Annotated[FavoritesService, Depends(get_favorites_service)],
):
    """Remove a property listing from favorites.
    
    Removes a saved listing from the user's favorites list.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | listing_id | string (24 chars) | MongoDB ObjectId of the listing |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "Listing removed from favorites",
        "listing_id": "507f1f77bcf86cd799439011",
        "total_favorites": 4
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 404 | Not in favorites | `{"detail": "Listing not in favorites"}` |
    | 500 | Internal error | `{"detail": "An unexpected error occurred"}` |
    """
    return await favorites_service.remove_favorite(listing_id, current_user)


@router.get("")
async def get_favorites(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    favorites_service: Annotated[FavoritesService, Depends(get_favorites_service)],
    offset: Annotated[
        int,
        Query(description="Number of items to skip for pagination", ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(description="Maximum items to return (1-100)", ge=1, le=100),
    ] = 20,
):
    """Get user's favorited listings.
    
    Retrieves a paginated list of the user's saved/favorited property listings.
    
    ## Query Parameters
    | Parameter | Default | Description |
    |-----------|---------|-------------|
    | offset | 0 | Skip N favorites |
    | limit | 20 | Return max N favorites (1-100) |
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "favorites": [
            {
                "id": "507f1f77bcf86cd799439011",
                "description": "Beautiful apartment...",
                "price": 2500.00,
                "location": {...},
                "images": [...]
            }
        ],
        "total": 10,
        "offset": 0,
        "limit": 20,
        "has_more": false
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 500 | Internal error | `{"detail": "An unexpected error occurred"}` |
    
    ## Notes
    - Returns empty array if no favorites, not 404
    - Listings that become unavailable are excluded from results
    """
    return await favorites_service.get_favorites(current_user, offset, limit)


@router.get("/{listing_id}/check")
async def check_is_favorite(
    listing_id: Annotated[
        str,
        Path(
            description="The unique identifier of the listing to check",
            min_length=24,
            max_length=24,
        ),
    ],
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    favorites_service: Annotated[FavoritesService, Depends(get_favorites_service)],
):
    """Check if a listing is in user's favorites.
    
    Quick check to determine if a specific listing is saved in the user's favorites.
    Useful for UI state (showing filled/unfilled heart icon).
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | listing_id | string (24 chars) | MongoDB ObjectId of the listing |
    
    ## Success Response (200 OK)
    ```json
    {
        "listing_id": "507f1f77bcf86cd799439011",
        "is_favorite": true
    }
    ```
    """
    return await favorites_service.check_is_favorite(listing_id, current_user)
