"""Listings router for handling all property listing endpoints."""

import logfire

from decimal import Decimal

from fastapi import (
    APIRouter,
    status,
    Depends,
    Security,
    UploadFile,
    Form,
    File,
    Query,
    BackgroundTasks,
    Path,
)
from fastapi.responses import JSONResponse

from models.users import LandLord, Admin
from models.listings import PropertyType, ListingCollectionTypes

from security.helpers import get_current_active_user
from services.email import get_email_service, EmailService
from services.template import get_template_service, TemplateService
from services.listings_service import get_listings_service, ListingsService

from typing import Annotated, List, Optional


router = APIRouter(
    prefix="/api/v1/listings",
    tags=["Property Listings"],
)


@router.post("")
async def create_property_listing(
    description: Annotated[
        str, Form(description="A brief description of the property being listed")
    ],
    price: Annotated[
        Decimal, Form(description="Rental price of the property", decimal_places=2, gt=0.00)
    ],
    address: Annotated[str, Form(description="Street address of the property")],
    city: Annotated[str, Form(description="City where the property is located")],
    state: Annotated[str, Form(description="State where the property is located")],
    bedrooms: Annotated[
        int, Form(description="Number of bedrooms in the property", gt=0)
    ],
    amenities: Annotated[
        List[str], Form(description="List of amenities available in the property")
    ],
    property_type: Annotated[
        PropertyType, Form(description="Type of property (e.g., apartment, house)")
    ],
    images: Annotated[
        List[UploadFile], File(description="Multiple images of the property")
    ],
    proof_of_ownership: Annotated[
        List[UploadFile], File(description="Proof of ownership documents")
    ],
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["cre:listing"])
    ],
    email_service: Annotated[EmailService, Depends(get_email_service)],
    template_service: Annotated[TemplateService, Depends(get_template_service)],
    background_tasks: BackgroundTasks,
    listings_service: Annotated[ListingsService, Depends(get_listings_service)],
):
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
    return await listings_service.create_property_listing(
        description=description,
        price=price,
        address=address,
        city=city,
        state=state,
        bedrooms=bedrooms,
        amenities=amenities,
        property_type=property_type,
        images=images,
        proof_of_ownership=proof_of_ownership,
        current_user=current_user,
        email_service=email_service,
        template_service=template_service,
        background_tasks=background_tasks,
    )


@router.put("/{listing_id}")
async def update_property_listing(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["upd:listing"])
    ],
    listing_id: Annotated[
        str,
        Path(
            description="The unique identifier of the property listing to update",
            min_length=24,
            max_length=24,
        ),
    ],
    email_service: Annotated[EmailService, Depends(get_email_service)],
    template_service: Annotated[TemplateService, Depends(get_template_service)],
    background_tasks: BackgroundTasks,
    listings_service: Annotated[ListingsService, Depends(get_listings_service)],
    description: Annotated[
        Optional[str],
        Form(description="A brief description of the property being listed"),
    ] = None,
    price: Annotated[
        Optional[Decimal],
        Form(description="Rental price of the property", decimal_places=2, gt=0.00),
    ] = None,
    address: Annotated[
        Optional[str], Form(description="Street address of the property")
    ] = None,
    city: Annotated[
        Optional[str], Form(description="City where the property is located")
    ] = None,
    state: Annotated[
        Optional[str], Form(description="State where the property is located")
    ] = None,
    bedrooms: Annotated[
        Optional[int], Form(description="Number of bedrooms in the property", gt=0)
    ] = None,
    amenities: Annotated[
        Optional[List[str]],
        Form(description="List of amenities available in the property"),
    ] = None,
    property_type: Annotated[
        Optional[PropertyType],
        Form(description="Type of property (e.g., apartment, house)"),
    ] = None,
    images: Annotated[
        List[UploadFile], File(description="Multiple images of the property")
    ] = [],
    proof_of_ownership: Annotated[
        List[UploadFile], File(description="Proof of ownership documents")
    ] = [],
):
    """Update an existing property listing.
    
    Updates the specified fields of a property listing. Any changes to location,
    proof of ownership, or images will reset the listing's verification status
    and trigger a re-verification process.
    
    ## Path Parameters
    | Parameter | Type | Description |
    |-----------|------|-------------|
    | listing_id | string (24 chars) | MongoDB ObjectId of the listing |
    
    ## Request Body (Form Data - all fields optional)
    | Field | Type | Description |
    |-------|------|-------------|
    | description | string | Updated property description |
    | price | decimal | Updated rental price (> 0) |
    | address | string | Updated street address |
    | city | string | Updated city |
    | state | string | Updated state |
    | bedrooms | int | Updated bedroom count (> 0) |
    | amenities | list[string] | Updated list of amenities |
    | property_type | PropertyType | bachelor, apartment, house, etc. |
    | images | list[file] | New property images to add |
    | proof_of_ownership | list[file] | New ownership documents |
    
    ## Verification Reset Triggers
    The following changes will reset verification status to `false`:
    - Address, city, or state changes
    - Proof of ownership document updates
    - Property images updates
    
    ## Success Response (200 OK)
    ```json
    {
        "message": "Property listing updated successfully",
        "listing": {
            "id": "507f1f77bcf86cd799439011",
            "description": "Updated description",
            "verified": false,
            "requiresReverification": true
        }
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Not authenticated | `{"detail": "Not authenticated"}` |
    | 403 | Not owner/admin | `{"detail": "Not authorized to update this listing"}` |
    | 404 | Listing not found | `{"detail": "Listing not found"}` |
    | 422 | Validation error | `{"detail": "Invalid file type"}` |
    | 500 | Internal error | `{"detail": "Failed to update listing"}` |
    
    ## Notes
    - Only provided fields will be updated
    - Image files must be valid image formats (jpg, png, webp)
    - Proof of ownership can be images or PDFs
    - Re-verification may take 1-3 business days
    """
    return await listings_service.update_property_listing(
        current_user=current_user,
        listing_id=listing_id,
        email_service=email_service,
        template_service=template_service,
        background_tasks=background_tasks,
        description=description,
        price=price,
        address=address,
        city=city,
        state=state,
        bedrooms=bedrooms,
        amenities=amenities,
        property_type=property_type,
        images=images,
        proof_of_ownership=proof_of_ownership,
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
        LandLord | Admin, Security(get_current_active_user, scopes=["read:listing"])
    ],
    listings_service: Annotated[ListingsService, Depends(get_listings_service)],
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
    return await listings_service.get_property_listing(
        listing_id=listing_id,
        current_user=current_user,
        collection=collection,
    )


@router.get("")
async def get_property_listings(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["read:listing"])
    ],
    listings_service: Annotated[ListingsService, Depends(get_listings_service)],
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
    return await listings_service.get_property_listings(
        current_user=current_user,
        offset=offset,
        limit=limit,
        collection=collection,
    )


@router.post("/verify/{listing_id}")
async def verify_listing(
    current_user: Annotated[
        Admin, Security(get_current_active_user, scopes=["ver:listing"])
    ],
    listing_id: Annotated[
        str,
        Path(
            description="The unique identifier of the property listing to verify",
            min_length=24,
            max_length=24,
        ),
    ],
    verified: Annotated[
        bool,
        Query(
            description="The value to update the listings verification status to. True or False."
        ),
    ],
    background_tasks: BackgroundTasks,
    email_service: Annotated[EmailService, Depends(get_email_service)],
    template_service: Annotated[TemplateService, Depends(get_template_service)],
    listings_service: Annotated[ListingsService, Depends(get_listings_service)],
):
    """
    This endpoint allows admin users to change the verified field of a listing to either True or False, to indicate if the
    Listing has been verified. As such when ever a property needs to be verified, a request to this endpoint should be made, like wise when a property is unverified.
    
    ##NB Only admin users will have access to this endpoint
    ##NB Only verified listings are displayed to tenants.

    ## Possible Errors
    - 404 Not Found: If the specified listing does not exist.
    - 500 Internal Server Error: If there is an unexpected error during listing verification.
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
        "message": "Property listing verified successfully",
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
    return await listings_service.verify_listing(
        current_user=current_user,
        listing_id=listing_id,
        verified=verified,
        background_tasks=background_tasks,
        email_service=email_service,
        template_service=template_service,
    )


@router.delete("/{listing_id}")
async def delete_property_listing(
    listing_id: Annotated[
        str,
        Path(
            description="The unique identifier of the property listing to delete",
            min_length=24,
            max_length=24,
        ),
    ],
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["del:listing"])
    ],
    listings_service: Annotated[ListingsService, Depends(get_listings_service)],
):
    """
    This endpoint allows KYC verified users to delete their property listings
    on FindMyRent.

    ## Possible Errors
    - 404 Not Found: If the specified listing does not exist or does not belong to the user.
    - 500 Internal Server Error: If there is an unexpected error during listing deletion.
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
        "message": "Property listing deleted successfully"
    }
    ```
    """
    return await listings_service.delete_property_listing(
        listing_id=listing_id,
        current_user=current_user,
    )