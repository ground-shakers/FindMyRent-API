"""Repository for Admin entity database operations."""

from functools import lru_cache
from typing import Optional, List

from beanie import PydanticObjectId

from models.users import Admin


class AdminRepository:
    """Repository class for Admin database operations.

    This class encapsulates all database operations for the Admin entity,
    providing a clean separation between business logic and data access.
    """

    async def get_by_id(self, user_id: str) -> Optional[Admin]:
        """Retrieves an admin by their unique identifier.

        Args:
            user_id (str): The unique identifier of the admin.

        Returns:
            Optional[Admin]: The admin if found, None otherwise.
        """
        return await Admin.get(PydanticObjectId(user_id))

    async def get_by_email(self, email: str) -> Optional[Admin]:
        """Retrieves an admin by their email address.

        Args:
            email (str): The email address to search for.

        Returns:
            Optional[Admin]: The admin if found, None otherwise.
        """
        return await Admin.find_one(Admin.email == email)

    async def find_all(self, offset: int = 0, limit: int = 100) -> List[Admin]:
        """Retrieves a paginated list of all admins.

        Args:
            offset (int): Number of records to skip. Defaults to 0.
            limit (int): Maximum number of records to return. Defaults to 100.

        Returns:
            List[Admin]: List of admin documents.
        """
        return await Admin.find().skip(offset).limit(limit).to_list()

    async def insert(self, admin: Admin) -> Admin:
        """Inserts a new admin into the database.

        Args:
            admin (Admin): The admin document to insert.

        Returns:
            Admin: The inserted admin with generated ID.
        """
        return await admin.insert()

    async def delete(self, admin: Admin) -> None:
        """Deletes an admin from the database.

        Args:
            admin (Admin): The admin document to delete.
        """
        await admin.delete()


@lru_cache()
def get_admin_repository() -> AdminRepository:
    """Returns a cached instance of AdminRepository.

    Returns:
        AdminRepository: The singleton repository instance.
    """
    return AdminRepository()
