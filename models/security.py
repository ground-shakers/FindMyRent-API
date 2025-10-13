"""
Security models for user authentication and authorization.
"""
from typing import Annotated, List
from pydantic import Field, field_serializer

from beanie import Document, PydanticObjectId


class Permissions(Document):
    """Model representing user permissions."""

    user_type: Annotated[str, Field(unique=True)]  # Unique name of the permission
    permissions: Annotated[
        List[str], Field(default=[])
    ]  # List of permissions for the user type

    @field_serializer("id")
    def convert_pydantic_object_id_to_string(self, id: PydanticObjectId):
        return str(id)
