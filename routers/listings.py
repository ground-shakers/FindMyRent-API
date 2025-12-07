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
    File,
    Query,
    Path
)
from fastapi.responses import JSONResponse

from controllers.file_upload import upload_file_to_cloudinary

from models.users import LandLord
from models.listings import Listing, PropertyType, ListingLocation, LandLordDetailsSummary, ListingCollectionTypes

from pymongo.errors import (
    WriteError,
    ConnectionFailure,
    PyMongoError
)
from beanie import PydanticObjectId

from controllers.file_upload import (
    validate_upload_results,
    to_image_upload_responses,
    validate_file_types,
    file_greater_than_max_size,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_PROOF_OF_OWNERSHIP_TYPES
)

from security.helpers import get_current_active_user

from typing import Annotated, List, Dict, Tuple, Optional
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
        "listing": {
            "description": "Sample description",
            "price": 2000.0,
            "location": {
                "address": "Sample address",
                "city": "Sample city",
                "state": "Sample state"
            },
            "bedrooms": 3,
            "createdAt": "2023-10-05T14:48:00Z",
            "landlord": {
                "landlordId": 123ddfe2121,
                "firstName": John,
                "lastName": Doe
            },
            "amenities": [
                "pool",
                "gym",
                "parking"
            ],
            "updatedAt": "2023-10-05T14:48:00Z",
            "propertyType": "Bachelor",
            "verified": True,
            "images": [
                "https://res.cloudinary.com/.../image_1.jpg",
                "https://res.cloudinary.com/.../image_2.jpg",
                "https://res.cloudinary.com/.../image_3.jpg"
            ],
            "available": True,
            "proofOfOwnership": [
                "https://res.cloudinary.com/.../proof_of_ownership_1.jpg",
                "https://res.cloudinary.com/.../proof_of_ownership_2.jpg"
            ]
        }
    }
    ```
    """
    # Check if user is KYC verified
    if not current_user.kyc_verified:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "KYC verification is required to create a property listing."},
        )

    image_upload_tasks = []
    proof_upload_tasks = []

    with logfire.span(f"Creating new property listing for user: {current_user.email}"):
        if not len(images) >= 3:
            logfire.info("Insufficient images uploaded for property listing")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "At least 3 images are required for a property listing"})

        if not len(proof_of_ownership) >= 1:
            logfire.info("Insufficient proof of ownership documents uploaded for property listing")
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "At least 1 proof of ownership document is required"})

        # Validate file sizes of the uploaded files
        for file in images + proof_of_ownership:
            if await file_greater_than_max_size(file):
                logfire.info(f"{current_user.id} uploaded a file: {file.filename} exceeds maximum allowed size for property listing")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": f"File {file.filename} exceeds maximum allowed size of 100 MB."}
                )
            logfire.info(f"{current_user.id} uploaded a file: {file.filename} is within the allowed size limit for property listing")

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
            property_type=property_type,
        )

        # amenities comes as ["pool,gym,parking"] (single string in a list)
        # so we need to split it into a list of strings
        if len(amenities) == 1 and ',' in amenities[0]:
            amenities = [a.strip() for a in amenities[0].split(',')]

        new_listing.amenities = amenities

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
        except PyMongoError as e:
            logfire.error(f"Unexpected database error when saving new listing for user: {current_user.email} - {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An unexpected error occurred while creating the property listing."},
            )

    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={
            "message": "Property listing is under review",
            "listing": new_listing.model_dump(mode="json")
        }
    )


@router.get("/{listing_id}")
async def get_property_listing(
    listing_id: Annotated[
        str,
        Path(
            description="The unique identifier of the property listing to retrieve",
            min_length=24,
            max_length=24,
        ),
    ],
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["read-l"])
    ],
    collection: Annotated[
        ListingCollectionTypes,
        Query(description="Retrieve owned listings or general. Defaults to 'general'"),
    ] = ListingCollectionTypes.GENERAL,
):
    """
    This endpoint allows KYC verified users to retrieve a specific property listing
    on FindMyRent.

    ## Possible Errors
    - 404 Not Found: If the specified listing does not exist.
    - 500 Internal Server Error: If there is an unexpected error during listing retrieval.
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
        "listing": {
            description: Sample description,
            price: 2000.0,
            location: {
                address: Sample address,
                city: Sample city,
                state: Sample state
            },
            bedrooms: 3,
            createdAt: 2023-10-05T14:48:00Z,
            landlord: {
                landlord_id: 123ddfe2121,
                first_name: John,
                last_name: Doe,
            },
            amenities: [
                pool,
                gym,
                parking
            ],
            updatedAt: 2023-10-05T14:48:00Z,
            propertyType: Bachelor,
            verified: True,
            images: [
                https://res.cloudinary.com/.../image_1.jpg,
                https://res.cloudinary.com/.../image_2.jpg,
                https://res.cloudinary.com/.../image_3.jpg
            ],
            available: True,
            proofOfOwnership: [
                https://res.cloudinary.com/.../proof_of_ownership_1.jpg,
                https://res.cloudinary.com/.../proof_of_ownership_2.jpg
            ]
        }
    }
    ```
    """
    try:
        listing = None

        # If fetching owned listings, ensure user is KYC verified
        if collection == ListingCollectionTypes.OWNED:
            listing = await Listing.find_one(
                Listing.id == PydanticObjectId(listing_id),
                Listing.landlord.landlord_id == str(current_user.id)
            )
        elif collection == ListingCollectionTypes.GENERAL:
            listing = await Listing.find_one(
                Listing.id == PydanticObjectId(listing_id),
                Listing.verified == True
            )

        if not listing:
            logfire.info(f"Listing with ID {listing_id} not found for user: {current_user.id}")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Property listing not found"},
            )

        # Serialize listing based on collection type
        if collection == ListingCollectionTypes.OWNED:
            serialized_listing = listing.model_dump(mode="json", by_alias=True)
        elif collection == ListingCollectionTypes.GENERAL:
            serialized_listing = listing.model_dump(mode="json", by_alias=True, exclude=["proof_of_ownership", "landlord"])

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Property listing retrieved successfully",
                "listing": serialized_listing
            },
        )
    except ConnectionFailure:
        logfire.error(f"Database connection failure when retrieving listing ID: {listing_id} for user: {current_user.id}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service unavailable. Please try again later."},
        )
    except PyMongoError as e:
        logfire.error(f"Unexpected database error when retrieving listing ID: {listing_id} for user: {current_user.id} - {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred while retrieving the property listing."},
        )
    except Exception as e:
        logfire.error(f"Unexpected error when retrieving listing ID: {listing_id} for user: {current_user.id} - {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred while retrieving the property listing."},
        )


@router.get("")
async def get_property_listings(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["read-l"])
    ],
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="The number of items to skip before starting to collect the result set.",
        ),
    ] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    collection: Annotated[
        ListingCollectionTypes,
        Query(description="Retrieve owned listings or general. Defaults to 'general'"),
    ] = ListingCollectionTypes.GENERAL,
):
    """
    This endpoint allows KYC verified users to retrieve theirs and other property listings
    on FindMyRent. This endpoint allows users not KYC verified to retrieve other property listings as well.

    ## Possible Errors
    - 404 Not Found: If the specified listing does not exist or does not belong to the user.
    - 500 Internal Server Error: If there is an unexpected error during listing retrieval.
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
        "listings": [
            {
                description: Sample description,
                price: 2000.0,
                location: {
                    address: Sample address,
                    city: Sample city,
                    state: Sample state
                },
                bedrooms: 3,
                createdAt: 2023-10-05T14:48:00Z,
                landlord: {
                    landlord_id: 123ddfe2121,
                    first_name: John,
                    last_name: Doe,
                },
                amenities: [
                    pool,
                    gym,
                    parking
                ],
                updatedAt: 2023-10-05T14:48:00Z,
                propertyType: Bachelor,
                verified: True,
                images: [
                    https://res.cloudinary.com/.../image_1.jpg,
                    https://res.cloudinary.com/.../image_2.jpg,
                    https://res.cloudinary.com/.../image_3.jpg
                ],
                available: True,
                proofOfOwnership: [
                    https://res.cloudinary.com/.../proof_of_ownership_1.jpg,
                    https://res.cloudinary.com/.../proof_of_ownership_2.jpg
                ]
            }
        ]
    }
    ```
    """
    try:
        # Check if user is KYC verified
        if collection == ListingCollectionTypes.OWNED:
            # Retrieve all listings for the current user with pagination
            listings = await Listing.find(Listing.landlord.landlord_id == str(current_user.id)).skip(offset).limit(limit).to_list()
        elif collection == ListingCollectionTypes.GENERAL:
            # Retrieve all listings with pagination
            listings = await Listing.find_many(Listing.verified == True).skip(offset).limit(limit).to_list()
        
        # Handle case where no listings are found  
        if not listings:
            logfire.info(f"No listings found for user: {current_user.email} in collection: {collection}")
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "No property listings found"},
            )
        
        # Serialize listings based on collection type
        serialized_listings = []
        if collection == ListingCollectionTypes.OWNED:
            serialized_listings = [
                listing.model_dump(mode="json", by_alias=True) for listing in listings
            ]
        elif collection == ListingCollectionTypes.GENERAL:
            serialized_listings = [
                listing.model_dump(mode="json", by_alias=True, exclude=["proof_of_ownership", "landlord"]) for listing in listings
            ]
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"listings": serialized_listings},
        )
    except ConnectionFailure:
        logfire.error(f"Database connection failure when retrieving listings for user: {current_user.email}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service unavailable. Please try again later."},
        )
    except PyMongoError as e:
        logfire.error(f"Unexpected database error when retrieving listings for user: {current_user.email} - {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred while retrieving property listings."},
        )
    except Exception as e:
        logfire.error(f"Unexpected error when retrieving listings for user: {current_user.email} - {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred while retrieving property listings."},
        )
