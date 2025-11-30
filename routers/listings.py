"""User router for handling all user-related endpoints."""

import logfire
import asyncio

from starlette.middleware import *

from fastapi import (
    APIRouter,
    status,
    Depends,
    Security,
    UploadFile,
    Form,
    File
)
from fastapi.responses import JSONResponse

from controllers.file_upload import upload_file_to_cloudinary

from models.users import LandLord
from models.listings import Listing, PropertyType, ListingLocation, LandLordDetailsSummary

from pymongo.errors import (
    WriteError,
    ConnectionFailure,
)

from controllers.file_upload import (
    validate_upload_results,
    to_image_upload_responses,
    validate_file_types,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_PROOF_OF_OWNERSHIP_TYPES
)

from beanie import WriteRules

from security.helpers import get_current_active_user

from typing import Annotated, List, Dict, Tuple
from pydantic import ValidationError
from decimal import Decimal

router = APIRouter(
    prefix="/api/v1/listings",
    tags=["Property Listings"],
)


@router.post("")
async def create_property_listing(description: Annotated[str, Form(description="A brief description of the property being listed")], price: Annotated[Decimal, Form(description="Rental price of the property", decimal_places=2, gt=0.00)], address: Annotated[str, Form(description="Street address of the property")], city: Annotated[str, Form(description="City where the property is located")], state: Annotated[str, Form(description="State where the property is located")], bedrooms: Annotated[int, Form(description="Number of bedrooms in the property", gt=0)], amenities: Annotated[List[str], Form(description="List of amenities available in the property")], property_type: Annotated[PropertyType, Form(description="Type of property (e.g., apartment, house)")], images: Annotated[List[UploadFile], File(description="Multiple images of the property")], proof_of_ownership: Annotated[List[UploadFile], File(description="Proof of ownership documents")], current_user: Annotated[LandLord, Security(get_current_active_user, scopes=["create-l"])]):
    """
    This endpoint allows KYC verified users to submit rental property to be verified
    and listed on FindMyRent.
    
    ## Possible Errors
    - 400 Bad Request: If the uploaded files are of invalid types or insufficient in number.
    - 500 Internal Server Error: If there is an unexpected error during file upload or listing creation.
    - 503 Service Unavailable: If the endpoint isn't accessible.
    
    ## Error response structure
    ```json
    {
        "detail": "Sample error message"
    }
    ```
    
    ## Success response structure
    ```json
    {
        "message": "Property listing is under review",
        "listingId": "4546assdgsuasf29"
    }
    ```
    """
    
    image_upload_tasks = []
    proof_upload_tasks = []

    with logfire.span(f"Creating new property listing for user: {current_user.email}"):
        if not len(images) >= 3:
            logfire.info("Insufficient images uploaded for property listing")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "At least 3 images are required for a property listing"})

        if not len(proof_of_ownership) >= 1:
            logfire.info("Insufficient proof of ownership documents uploaded for property listing")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "At least 1 proof of ownership document is required"})

        # Validate file types of the uploaded files
        if error := await validate_file_types(images, ALLOWED_IMAGE_TYPES, "image"):
            logfire.info("Invalid image file types uploaded for property listing")
            return error

        if error := await validate_file_types(proof_of_ownership, ALLOWED_PROOF_OF_OWNERSHIP_TYPES, "proof of ownership"):
            logfire.info("Invalid proof of ownership file types uploaded for property listing")
            return error

        for image in images:
            image_upload_tasks.append(upload_file_to_cloudinary(image))

        for proof in proof_of_ownership:
            proof_upload_tasks.append(upload_file_to_cloudinary(proof))

        image_results: List[Tuple[int, Dict | None]] = await asyncio.gather(*image_upload_tasks, return_exceptions=True)
        proof_results: List[Tuple[int, Dict | None]] = await asyncio.gather(*proof_upload_tasks, return_exceptions=True)
        
        logfire.info("Requests to upload images and documents, sent!")

        # Fail if any proof of ownership upload failed
        if error := await validate_upload_results(proof_results, "Failed to upload proof of ownership documents"):
            return error

        # Fail if any image upload failed
        if error := await validate_upload_results(image_results, "Failed to upload property images"):
            return error
        
        logfire.info("Documents and images uploaded successfully!")
        
        # Validate and extract upload responses
        try:
            image_upload_responses = await to_image_upload_responses(image_results)
            proof_upload_responses = await to_image_upload_responses(proof_results)
        except ValidationError:
            logfire.error("Validation error when processing upload responses for property listing")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to process uploaded files"},
            )

        new_listing = Listing(
            description=description,
            price=price,
            location=ListingLocation(
                address=address,
                city=city,
                state=state
            ),
            landlord=LandLordDetailsSummary(
                landlord_id=str(current_user.id),
                first_name=current_user.first_name,
                last_name=current_user.last_name,
            ),
            bedrooms=bedrooms,
            amenities=amenities,
            property_type=property_type,
        )

        for upload_response in image_upload_responses:
            new_listing.images.append(upload_response.secure_url)

        for upload_response in proof_upload_responses:
            new_listing.proof_of_ownership.append(upload_response.secure_url)
        
        # Save new listing to database
        try:
            await new_listing.save()
            current_user.listings.append(str(new_listing.id))
            await current_user.save()
        except WriteError:
            logfire.error(f"Write error when saving new listing for user: {current_user.email}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Failed to create property listing"},
            )
        except ConnectionFailure:
            logfire.error(f"Database connection failure when saving new listing for user: {current_user.email}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )

    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={
            "message": "Property listing is under review",
            "listingId": new_listing.model_dump(mode="json", include=["id"])
        }
    )