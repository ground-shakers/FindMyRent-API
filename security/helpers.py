"""Contains all security related helper functions
"""
import os
import json
import secrets
import string

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status, Security, Depends
from fastapi.security import (
    OAuth2PasswordBearer,
    SecurityScopes
)

from passlib.context import CryptContext
from jose import JWTError, jwt, jwe
from jose.exceptions import ExpiredSignatureError

from pydantic import ValidationError
from typing import Annotated

from schema.security import TokenData, RefreshTokenData

from models.users import User

# Verification code settings
CODE_LENGTH = 6


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth/login",
    scopes={
        "me": "Read information about the current user."
    },
)


def generate_verification_code() -> str:
    """Generate a secure random verification code.

    Returns:
        str: The generated verification code.
    """
    return "".join(secrets.choice(string.digits) for _ in range(CODE_LENGTH))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies that `plain_password` and `hashed_password` are equal.

    Args:
        plain_password (str): The plain text password to verify.
        hashed_password (str): The hashed password to compare against.

    Returns:
        bool: True if the passwords match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generates a hash for the given password.

    Args:
        password (str): The plain text password to hash.

    Returns:
        str: The hashed password.
    """
    return pwd_context.hash(password)


async def get_user(username: str) -> User | None:
    """
    Fetches a user from the database by their username (email).

    Args:
        username (str): The email of the user to fetch.

    Returns:
        User | None: The user object if found, None otherwise.
    """

    user_in_db = await User.find_one(User.email == username, with_children=True)

    return user_in_db


async def get_user_by_id(user_id: str) -> User | None:
    """
    Fetches a user from the database by their ID.

    Args:
        user_id (str): The ID of the user to fetch.

    Returns:
        User | None: The user object if found, None otherwise.
    """
    try:
        user_in_db = await User.get(user_id, with_children=True)
        return user_in_db
    except Exception:
        return None


async def authenticate_user(username: str, password: str) -> User | bool:
    """Authenticates a user by their username and password.

    Args:
        username (str): The email of the user.
        password (str): The password of the user.

    Returns:
        User | bool: The user object if authentication is successful, False otherwise.
    """
    user = await get_user(username)

    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> bytes:
    """Creates a new access token.

    Args:
        data (dict): The data to include in the token payload.
        expires_delta (timedelta | None, optional): The expiration time for the token. Defaults to None.

    Returns:
        bytes: The encoded JWE token.
    """
    
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        token_expiry_time = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
        expire = datetime.now(timezone.utc) + timedelta(minutes=token_expiry_time)
    to_encode.update({"exp": expire.timestamp()})  #* Add expiration time to payload

    to_encode = json.dumps(to_encode).encode("utf-8")  #* Convert payload to bytes

    #* Create a JWE token
    encoded_jwe = jwe.encrypt(
        to_encode, os.getenv("SECRET_KEY"), algorithm="dir", encryption="A256GCM"
    )

    return encoded_jwe


def create_refresh_token(user_id: str, token_family: str) -> bytes:
    """Creates a new refresh token with unique JTI for replay protection.

    Args:
        user_id (str): The user ID.
        token_family (str): Token family for refresh token rotation.

    Returns:
        bytes: The encoded JWE refresh token.
    """
    
    # Generate unique token ID for replay protection
    token_jti = secrets.token_urlsafe(32)
    
    refresh_token_data = {
        "user_id": user_id,
        "token_family": token_family,
        "jti": token_jti,  # Unique token identifier
        "issued_at": datetime.now(timezone.utc).timestamp(),
        "type": "refresh"
    }
    
    # Refresh tokens have longer expiry
    refresh_token_expiry_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    expire = datetime.now(timezone.utc) + timedelta(days=refresh_token_expiry_days)
    refresh_token_data.update({"exp": expire.timestamp()})

    refresh_token_data = json.dumps(refresh_token_data).encode("utf-8")

    #* Create a JWE refresh token
    encoded_jwe = jwe.encrypt(
        refresh_token_data, os.getenv("SECRET_KEY"), algorithm="dir", encryption="A256GCM"
    )

    return encoded_jwe


def decode_refresh_token(refresh_token: str) -> RefreshTokenData | None:
    """Decode and validate a refresh token.

    Args:
        refresh_token (str): The refresh token to decode.

    Returns:
        RefreshTokenData | None: Token data if valid, None if invalid.
    """
    try:
        #* Decrypt the JWE token
        token_bytes = refresh_token.encode("utf-8")
        payload_bytes = jwe.decrypt(token_bytes, os.getenv("SECRET_KEY"))
        payload: dict = json.loads(payload_bytes)        # Validate token type
        if payload.get("type") != "refresh":
            return None

        user_id = payload.get("user_id")
        token_family = payload.get("token_family")
        jti = payload.get("jti")  # Unique token identifier
        issued_at = payload.get("issued_at")
        exp = payload.get("exp")

        if not all([user_id, token_family, jti, issued_at, exp]):
            return None

        #* Validate that the token has not expired
        if datetime.now(timezone.utc).timestamp() > exp:
            return None

        return RefreshTokenData(
            user_id=user_id,
            token_family=token_family,
            jti=jti,
            issued_at=issued_at
        )
    except Exception:
        return None


async def get_current_user(
    security_scopes: SecurityScopes, token: Annotated[str, Depends(oauth2_scheme)]
):
    """Get the current user from the token.

    Args:
        security_scopes (SecurityScopes): The security scopes required for the request.
        token (Annotated[str, Depends(oauth2_scheme)]): The access token.

    Raises:
        credentials_exception: Raised when credentials are invalid.
        ExpiredSignatureError: Raised when the token has expired.
        credentials_exception: Raised when the token is malformed.
        HTTPException: Raised when the user is not found.
        credentials_exception: Raised when the token is not active.
        credentials_exception: Raised when the token is not verified.
        HTTPException: Raised when the user does not have enough permissions.

    Returns:
        User: The authenticated user.
    """
    
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": authenticate_value},
    )
    try:
        #* Decrypt the JWE token
        token_bytes = token.encode("utf-8")
        payload_bytes = jwe.decrypt(token_bytes, os.getenv("SECRET_KEY"))
        payload: dict = json.loads(payload_bytes)

        username = payload.get("sub")
        exp = payload.get("exp")
        token_scopes: list = payload.get("scopes")
        token_data = TokenData(scopes=token_scopes, username=username)

        if username is None:
            raise credentials_exception

        #* Validate that the token has not expired
        if exp is None or datetime.now(timezone.utc).timestamp() > exp:
            raise ExpiredSignatureError

        token_data = TokenData(scopes=token_scopes, username=username)
    except (ValidationError):
        raise credentials_exception
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "Token has expired"}
        )
    except JWTError:
        raise credentials_exception

    user = await get_user(username=token_data.username)

    if user is None:
        raise credentials_exception

    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"message": "Not enough permissions"},
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Security(get_current_user, scopes=["me"])],
):
    """Get the current active user.

    Args:
        current_user (Annotated[User, Security, optional): The current user).

    Raises:
        HTTPException: Raised when the user is not active.

    Returns:
        User: The current active user.
    """
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"message": "Account does not exist"}
        )
    return current_user