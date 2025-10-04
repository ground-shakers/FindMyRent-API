"""Contains all security related helper functions
"""

import secrets
import string

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from redis import Redis
from typing import Optional

# Verification code settings
CODE_LENGTH = 6


def generate_verification_code() -> str:
    """Generate a secure random verification code."""
    return "".join(secrets.choice(string.digits) for _ in range(CODE_LENGTH))
