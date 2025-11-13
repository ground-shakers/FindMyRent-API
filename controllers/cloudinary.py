"""
    Controller to handle interactions with Cloudinary's API for image uploads
"""
import os

import cloudinary

from pprint import pprint
from dotenv import load_dotenv

load_dotenv(override=True)

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
)

import cloudinary.uploader
import cloudinary.exceptions

# TODO: READ the cloudinary exceptions for improved exception handling

def upload_image_to_cloudinary(image_path: str) -> dict:
    """Uploads an image to Cloudinary and returns the upload response.

    Args:
        image_path (str): The local path to the image file to be uploaded.

    Returns:
        dict: The response from Cloudinary API containing the upload result.
    """
    response: dict = cloudinary.uploader.upload(image_path)
    return response