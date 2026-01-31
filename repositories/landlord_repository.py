"""Repository for LandLord entity database operations."""

from functools import lru_cache
from typing import Optional, List

from beanie import PydanticObjectId
from beanie.operators import And

from models.users import LandLord
from models.aggregations.users import UserAnalyticsView


class LandLordRepository:
    """Repository class for LandLord database operations.

    This class encapsulates all database operations for the LandLord entity,
    providing a clean separation between business logic and data access.
    """

    async def get_by_id(self, user_id: str) -> Optional[LandLord]:
        """Retrieves a landlord by their unique identifier.

        Args:
            user_id (str): The unique identifier of the landlord.

        Returns:
            Optional[LandLord]: The landlord if found, None otherwise.
        """
        return await LandLord.get(PydanticObjectId(user_id))

    async def find_unverified_by_email(self, email: str) -> Optional[LandLord]:
        """Finds an unverified landlord by email address.

        Args:
            email (str): The email address to search for.

        Returns:
            Optional[LandLord]: The unverified landlord if found, None otherwise.
        """
        return await LandLord.find_one(
            And(LandLord.email == email, LandLord.verified == False)
        )

    async def find_by_email(self, email: str) -> Optional[LandLord]:
        """Finds a landlord by email address.

        Args:
            email (str): The email address to search for.

        Returns:
            Optional[LandLord]: The landlord if found, None otherwise.
        """
        return await LandLord.find_one(LandLord.email == email)

    async def find_all(self, offset: int = 0, limit: int = 100) -> List[LandLord]:
        """Retrieves a paginated list of all landlords.

        Args:
            offset (int): Number of records to skip. Defaults to 0.
            limit (int): Maximum number of records to return. Defaults to 100.

        Returns:
            List[LandLord]: List of landlord documents.
        """
        return await LandLord.find().skip(offset).limit(limit).to_list()

    async def insert(self, landlord: LandLord) -> LandLord:
        """Inserts a new landlord into the database.

        Args:
            landlord (LandLord): The landlord document to insert.

        Returns:
            LandLord: The inserted landlord with generated ID.
        """
        return await landlord.insert()

    async def save(self, landlord: LandLord) -> LandLord:
        """Saves/updates an existing landlord in the database.

        Args:
            landlord (LandLord): The landlord document to save.

        Returns:
            LandLord: The saved landlord document.
        """
        return await landlord.save()

    async def delete(self, landlord: LandLord) -> None:
        """Deletes a landlord from the database.

        Args:
            landlord (LandLord): The landlord document to delete.
        """
        await landlord.delete()

    async def get_analytics(self) -> List[UserAnalyticsView]:
        """Retrieves user analytics data from the UserAnalyticsView.

        Returns:
            List[UserAnalyticsView]: List of analytics records.
        """
        return await UserAnalyticsView.find_all().to_list()


@lru_cache()
def get_landlord_repository() -> LandLordRepository:
    """Returns a cached instance of LandLordRepository.

    Returns:
        LandLordRepository: The singleton repository instance.
    """
    return LandLordRepository()
