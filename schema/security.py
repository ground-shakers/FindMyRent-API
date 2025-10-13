"""Defines schema of requests and responses related to security"""

from pydantic import BaseModel, Field
from typing import Annotated, List

from models.helpers import UserType

from pydantic import BaseModel


class Token(BaseModel):
    """Model representing an authentication token."""
    
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Model representing data contained in an authentication token."""
    
    username: str | None = None
    scopes: list[str] = []