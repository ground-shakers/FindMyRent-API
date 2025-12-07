"""
    Controller to handle interactions with Cloudinary's API for image uploads
"""
import os

import cloudinary
import filetype
import logfire

from typing import Tuple

from fastapi import status, UploadFile

from dotenv import load_dotenv
from httpx import AsyncClient, HTTPError, ConnectTimeout, NetworkError, Limits
from datetime import datetime

from fastapi.responses import JSONResponse

from schema.file_upload import CloudinaryImageUploadResponse

from typing import List, Set, Tuple, Dict

load_dotenv(override=True)

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")


ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png"]
ALLOWED_PROOF_OF_OWNERSHIP_TYPES = ["application/pdf", "image/png"]
MAX_FILE_SIZE_MB = 100 * 1024 * 1024  # 100 MB

async def file_greater_than_max_size(file: UploadFile | list[UploadFile]) -> bool:
    """
    Check if the uploaded file exceeds the maximum allowed size.

    Args:
        file (UploadFile | list[UploadFile]): The uploaded file(s) to check.

    Returns:
        bool: True if the file is larger than the maximum size, False otherwise.
    """
    return file.size > MAX_FILE_SIZE_MB


async def to_image_upload_responses(
    results: List[Tuple[int, Dict | None]],
) -> List[CloudinaryImageUploadResponse]:
    """Convert results tuples to CloudinaryImageUploadResponse objects.

    Args:
        results (list[tuple[int, dict  |  None]]): List of tuples containing status codes and response dicts.

    Returns:
        list[CloudinaryImageUploadResponse]: List of validated CloudinaryImageUploadResponse objects.
    """
    return [CloudinaryImageUploadResponse(**resp) for _, resp in results]


async def validate_upload_results(
    results: List[Tuple[int, Dict | None]], error_message: str
):
    """
    Validate the results of image uploads.

    Args:
        results (List[Tuple[int, Dict | None]]): List of tuples containing status codes and response dicts.
        error_message (str): Error message to return if validation fails.

    Returns:
        JSONResponse | None: JSONResponse with error details or None if all uploads succeeded.
    """
    for status_code, _ in results:
        if status_code != 200:
            return JSONResponse(
                status_code=status_code, content={"detail": error_message}
            )
    return None


async def validate_file_types(
    files: List[UploadFile], allowed_types: Set[str], file_category: str
) -> JSONResponse | None:
    """
    Validate that all uploaded files match allowed MIME types.

    Args:
        files: List of uploaded files (UploadFile objects)
        allowed_types: Set of allowed MIME types (e.g., {'image/jpeg', 'image/png'})
        file_category: Description of file category for error message (e.g., 'image', 'proof of ownership')

    Returns:
        JSONResponse with 400 status if validation fails, None if all files are valid

    Example:
        >>> if error := await validate_file_types(images, ALLOWED_IMAGE_TYPES, "image"):
        >>>     return error
    """
    for file in files:
        # Read file content asynchronously
        content = await file.read()
        kind = filetype.guess(content)

        # Reset file pointer for subsequent reads
        await file.seek(0)

        if not kind or kind.mime not in allowed_types:
            # Extract file extensions from MIME types for user-friendly message
            allowed_extensions = ", ".join(
                sorted(set(mime.split("/")[1].upper() for mime in allowed_types))
            )

            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": f"Invalid {file_category} file type: {file.filename}. "
                    f"Allowed types are {allowed_extensions}."
                },
            )

    return None


async def upload_file_to_cloudinary(image: UploadFile) -> Tuple[int, dict | None]:
    """Uploads an image to Cloudinary and returns the upload response.

    Args:
        image (UploadFile): The image file to be uploaded.

    Returns:
        Tuple[int, dict | None]: A tuple containing the HTTP status code and the response JSON from Cloudinary if successful, or None if failed.
    """

    TIMESTAMP = str(int(datetime.now().timestamp()))

    url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

    payload = {
        "timestamp": TIMESTAMP,
        "api_key": API_KEY,
        "signature": cloudinary.utils.api_sign_request(
            {"timestamp": TIMESTAMP},
            os.getenv("CLOUDINARY_API_SECRET"),
        ),
    }

    logfire.info("Uploading image to Cloudinary")
    
    files = {"file": image.file}

    logfire.info("Image to be uploaded to cloudinary opened successfully")

    try:
        connection_limits = Limits(max_keepalive_connections=20, max_connections=20)

        async with AsyncClient(timeout=30, limits=connection_limits) as client:
            response = await client.post(url, data=payload, files=files)
    except (NetworkError) as e:
            logfire.error(f"Network error occurred while uploading image to Cloudinary: {e}")
            return status.HTTP_503_SERVICE_UNAVAILABLE, None
    except (ConnectTimeout) as e:
            logfire.error(f"Connection timed out while uploading image to Cloudinary: {e}")
            return status.HTTP_504_GATEWAY_TIMEOUT, None
    except HTTPError as e:
        logfire.error(f"HTTP error occurred while uploading image to Cloudinary: {e}")
        return status.HTTP_500_INTERNAL_SERVER_ERROR, None

    # Return status code and response JSON if successful
    if response.status_code == status.HTTP_200_OK:
        logfire.info(f"Image uploaded successfully to Cloudinary: {response.text}")
        return response.status_code, response.json()
    
    # Return status code and None if upload failed
    logfire.error(f"Failed to upload image to Cloudinary: {response.text}")
    return response.status_code, None
