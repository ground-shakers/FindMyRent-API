"""Repository for Permissions entity database operations."""

from functools import lru_cache
from typing import Optional

from models.security import Permissions


class PermissionsRepository:
    """Repository class for Permissions database operations.

    This class encapsulates all database operations for the Permissions entity,
    providing a clean separation between business logic and data access.
    """

    async def get_by_user_type(self, user_type: str) -> Optional[Permissions]:
        """Retrieves permissions for a specific user type.

        Args:
            user_type (str): The user type to get permissions for.

        Returns:
            Optional[Permissions]: The permissions if found, None otherwise.
        """
        return await Permissions.find_one(Permissions.user_type == user_type)


@lru_cache()
def get_permissions_repository() -> PermissionsRepository:
    """Returns a cached instance of PermissionsRepository.

    Returns:
        PermissionsRepository: The singleton repository instance.
    """
    return PermissionsRepository()
