"""Repository for Listing entity database operations."""

from functools import lru_cache
from typing import Optional, List

from beanie import PydanticObjectId

from models.listings import Listing


class ListingRepository:
    """Repository class for Listing database operations.

    This class encapsulates all database operations for the Listing entity,
    providing a clean separation between business logic and data access.
    """

    async def get_by_id(self, listing_id: str) -> Optional[Listing]:
        """Retrieves a listing by its unique identifier.

        Args:
            listing_id (str): The unique identifier of the listing.

        Returns:
            Optional[Listing]: The listing if found, None otherwise.
        """
        return await Listing.get(PydanticObjectId(listing_id))

    async def find_by_landlord_and_id(
        self, landlord_id: str, listing_id: str
    ) -> Optional[Listing]:
        """Finds a listing belonging to a specific landlord.

        Args:
            landlord_id (str): The landlord's unique identifier.
            listing_id (str): The listing's unique identifier.

        Returns:
            Optional[Listing]: The listing if found and owned by landlord, None otherwise.
        """
        return await Listing.find_one(
            Listing.landlord.landlord_id == landlord_id,
            Listing.id == PydanticObjectId(listing_id),
        )

    async def find_verified_by_id(self, listing_id: str) -> Optional[Listing]:
        """Finds a verified listing by its ID.

        Args:
            listing_id (str): The listing's unique identifier.

        Returns:
            Optional[Listing]: The verified listing if found, None otherwise.
        """
        return await Listing.find_one(
            Listing.id == PydanticObjectId(listing_id),
            Listing.verified == True,
        )

    async def find_by_landlord(
        self, landlord_id: str, offset: int = 0, limit: int = 100
    ) -> List[Listing]:
        """Retrieves all listings belonging to a specific landlord.

        Args:
            landlord_id (str): The landlord's unique identifier.
            offset (int): Number of records to skip. Defaults to 0.
            limit (int): Maximum number of records to return. Defaults to 100.

        Returns:
            List[Listing]: List of listings owned by the landlord.
        """
        return (
            await Listing.find(Listing.landlord.landlord_id == landlord_id)
            .skip(offset)
            .limit(limit)
            .to_list()
        )

    async def find_verified(self, offset: int = 0, limit: int = 100) -> List[Listing]:
        """Retrieves all verified listings with pagination.

        Args:
            offset (int): Number of records to skip. Defaults to 0.
            limit (int): Maximum number of records to return. Defaults to 100.

        Returns:
            List[Listing]: List of verified listings.
        """
        return (
            await Listing.find_many(Listing.verified == True)
            .skip(offset)
            .limit(limit)
            .to_list()
        )

    async def save(self, listing: Listing) -> Listing:
        """Saves/updates a listing in the database.

        Args:
            listing (Listing): The listing document to save.

        Returns:
            Listing: The saved listing document.
        """
        return await listing.save()

    async def delete(self, listing: Listing) -> None:
        """Deletes a listing from the database.

        Args:
            listing (Listing): The listing document to delete.
        """
        await listing.delete()


@lru_cache()
def get_listing_repository() -> ListingRepository:
    """Returns a cached instance of ListingRepository.

    Returns:
        ListingRepository: The singleton repository instance.
    """
    return ListingRepository()
