"""Contains all models commonly used across different modules."""
from enum import Enum

from datetime import date


class UserType(str, Enum):
    """Enumeration of user types."""
    LANDLORD = "landlord"
    ADMIN = "admin"
    SUPER_USER = "superuser"


class EmailType(str, Enum):
    """Enum for different email types."""

    VERIFICATION = "verification"
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    NOTIFICATION = "notification"


class ContentType(str, Enum):
    """Enum for email content types."""

    PLAIN = "plain"
    HTML = "html"
    MULTIPART = "multipart"
