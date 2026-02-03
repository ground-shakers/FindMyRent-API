"""
Favorites service for handling user favorites business logic.
"""

import logfire

from functools import lru_cache
from typing import List, Optional

from fastapi import status
from fastapi.responses import JSONResponse

from beanie import PydanticObjectId

from pymongo.errors import ConnectionFailure, PyMongoError

from models.users import LandLord
from models.listings import Listing

from repositories.landlord_repository import get_landlord_repository, LandLordRepository
from repositories.listing_repository import get_listing_repository, ListingRepository

from utils.masking import mask_landlord_details


class FavoritesService:
    """Service class for handling user favorites operations.

    This service encapsulates the business logic for adding, removing,
    and retrieving favorited property listings.
    """

    def __init__(self):
        self.landlord_repo = get_landlord_repository()
        self.listing_repo = get_listing_repository()

    async def add_favorite(
        self,
        listing_id: str,
        current_user: LandLord,
    ):
        """Add a listing to user's favorites.

        Args:
            listing_id (str): The ID of the listing to favorite.
            current_user (LandLord): The authenticated user.

        Returns:
            JSONResponse: Success or error response.
        """
        try:
            with logfire.span(f"Adding listing {listing_id} to favorites for user {current_user.id}"):
                # Check if listing exists and is verified
                listing = await self.listing_repo.find_verified_by_id(listing_id)
                if not listing:
                    logfire.info(f"Listing {listing_id} not found or not verified")
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "Listing not found"},
                    )

                # Check if already favorited
                if listing_id in current_user.favorites:
                    logfire.info(f"Listing {listing_id} already in favorites for user {current_user.id}")
                    return JSONResponse(
                        status_code=status.HTTP_409_CONFLICT,
                        content={"detail": "Listing already in favorites"},
                    )

                # Add to favorites
                current_user.favorites.append(listing_id)
                await self.landlord_repo.save(current_user)

                logfire.info(f"Added listing {listing_id} to favorites for user {current_user.id}")

                return JSONResponse(
                    status_code=status.HTTP_201_CREATED,
                    content={
                        "message": "Listing added to favorites",
                        "listing_id": listing_id,
                        "total_favorites": len(current_user.favorites),
                    },
                )

        except ConnectionFailure:
            logfire.error("Database connection failure when adding favorite")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(f"Database error when adding favorite: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred."},
            )

    async def remove_favorite(
        self,
        listing_id: str,
        current_user: LandLord,
    ):
        """Remove a listing from user's favorites.

        Args:
            listing_id (str): The ID of the listing to remove.
            current_user (LandLord): The authenticated user.

        Returns:
            JSONResponse: Success or error response.
        """
        try:
            with logfire.span(f"Removing listing {listing_id} from favorites for user {current_user.id}"):
                # Check if in favorites
                if listing_id not in current_user.favorites:
                    logfire.info(f"Listing {listing_id} not in favorites for user {current_user.id}")
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"detail": "Listing not in favorites"},
                    )

                # Remove from favorites
                current_user.favorites.remove(listing_id)
                await self.landlord_repo.save(current_user)

                logfire.info(f"Removed listing {listing_id} from favorites for user {current_user.id}")

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "message": "Listing removed from favorites",
                        "listing_id": listing_id,
                        "total_favorites": len(current_user.favorites),
                    },
                )

        except ConnectionFailure:
            logfire.error("Database connection failure when removing favorite")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(f"Database error when removing favorite: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred."},
            )

    async def get_favorites(
        self,
        current_user: LandLord,
        offset: int = 0,
        limit: int = 20,
    ):
        """Get user's favorited listings with pagination.

        Args:
            current_user (LandLord): The authenticated user.
            offset (int): Number of items to skip. Defaults to 0.
            limit (int): Maximum items to return. Defaults to 20.

        Returns:
            JSONResponse: List of favorited listings.
        """
        try:
            with logfire.span(f"Getting favorites for user {current_user.id}"):
                favorite_ids = current_user.favorites

                if not favorite_ids:
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content={
                            "favorites": [],
                            "total": 0,
                            "offset": offset,
                            "limit": limit,
                        },
                    )

                # Paginate the favorites list
                total = len(favorite_ids)
                paginated_ids = favorite_ids[offset:offset + limit]

                # Fetch the actual listings
                listings = []
                for listing_id in paginated_ids:
                    listing = await self.listing_repo.find_verified_by_id(listing_id)
                    if listing:
                        # Serialize and apply masking based on premium status
                        listing_data = listing.model_dump(
                            mode="json",
                            by_alias=True,
                            exclude=["proof_of_ownership"]
                        )
                        # Apply masking for non-premium users
                        listing_data = mask_landlord_details(listing_data, current_user.premium)
                        listings.append(listing_data)

                logfire.info(f"Retrieved {len(listings)} favorites for user {current_user.id}")

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "favorites": listings,
                        "total": total,
                        "offset": offset,
                        "limit": limit,
                        "has_more": (offset + len(listings)) < total,
                    },
                )

        except ConnectionFailure:
            logfire.error("Database connection failure when getting favorites")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(f"Database error when getting favorites: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred."},
            )

    async def check_is_favorite(
        self,
        listing_id: str,
        current_user: LandLord,
    ):
        """Check if a listing is in user's favorites.

        Args:
            listing_id (str): The ID of the listing to check.
            current_user (LandLord): The authenticated user.

        Returns:
            JSONResponse: Boolean result.
        """
        is_favorite = listing_id in current_user.favorites
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "listing_id": listing_id,
                "is_favorite": is_favorite,
            },
        )


@lru_cache()
def get_favorites_service():
    """Returns a cached instance of FavoritesService.

    Returns:
        FavoritesService: The singleton FavoritesService instance.
    """
    return FavoritesService()
