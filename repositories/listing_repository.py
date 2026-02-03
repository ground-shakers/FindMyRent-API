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

    async def search_listings(
        self,
        filters: dict,
        offset: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Listing], int]:
        """Searches listings with dynamic filters.

        Builds a MongoDB query from the provided filters and returns matching
        verified listings with pagination and sorting.

        Args:
            filters (dict): Dictionary of filter criteria.
            offset (int): Number of records to skip. Defaults to 0.
            limit (int): Maximum number of records to return. Defaults to 20.
            sort_by (str): Field to sort by. Defaults to "created_at".
            sort_order (str): Sort direction ("asc" or "desc"). Defaults to "desc".

        Returns:
            tuple[list[Listing], int]: List of matching listings and total count.
        """
        # Build query conditions - always filter verified listings only
        query_conditions = [Listing.verified == True]

        # Text search on description
        if filters.get("query"):
            query_conditions.append(
                {"$expr": {"$regexMatch": {
                    "input": "$description",
                    "regex": filters["query"],
                    "options": "i"
                }}}
            )

        # Price range filters
        if filters.get("min_price") is not None:
            query_conditions.append(Listing.price >= float(filters["min_price"]))
        if filters.get("max_price") is not None:
            query_conditions.append(Listing.price <= float(filters["max_price"]))

        # Location filters (case-insensitive)
        if filters.get("city"):
            query_conditions.append(
                {"location.city": {"$regex": f"^{filters['city']}$", "$options": "i"}}
            )
        if filters.get("state"):
            query_conditions.append(
                {"location.state": {"$regex": f"^{filters['state']}$", "$options": "i"}}
            )

        # Property type filter
        if filters.get("property_type"):
            query_conditions.append(Listing.property_type == filters["property_type"])

        # Bedroom range filters
        if filters.get("min_bedrooms") is not None:
            query_conditions.append(Listing.bedrooms >= filters["min_bedrooms"])
        if filters.get("max_bedrooms") is not None:
            query_conditions.append(Listing.bedrooms <= filters["max_bedrooms"])

        # Amenities filter - listing must have ALL specified amenities
        if filters.get("amenities"):
            query_conditions.append({"amenities": {"$all": filters["amenities"]}})

        # Availability filter
        if filters.get("available_only", True):
            query_conditions.append(Listing.available == True)

        # Build sort direction
        sort_direction = -1 if sort_order == "desc" else 1
        
        # Map sort field names
        sort_field_map = {
            "price": "price",
            "created_at": "created_at",
            "bedrooms": "bedrooms",
        }
        sort_field = sort_field_map.get(sort_by, "created_at")

        # Execute query with count
        query = Listing.find(*query_conditions)
        total = await query.count()
        
        listings = (
            await query
            .sort([(sort_field, sort_direction)])
            .skip(offset)
            .limit(limit)
            .to_list()
        )

        return listings, total


@lru_cache()
def get_listing_repository() -> ListingRepository:
    """Returns a cached instance of ListingRepository.

    Returns:
        ListingRepository: The singleton repository instance.
    """
    return ListingRepository()
