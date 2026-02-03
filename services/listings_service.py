"""
Listings service for handling property listing business logic.
"""

import logfire
import asyncio
import os

from functools import lru_cache
from datetime import datetime
from decimal import Decimal

from fastapi import status, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse

from models.users import LandLord, Admin
from models.listings import (
    Listing,
    PropertyType,
    ListingLocation,
    LandLordDetailsSummary,
    ListingCollectionTypes,
)
from models.helpers import UserType

from pymongo.errors import WriteError, ConnectionFailure, PyMongoError
from beanie import PydanticObjectId

from repositories.listing_repository import get_listing_repository, ListingRepository
from repositories.landlord_repository import get_landlord_repository, LandLordRepository

from services.notifications_service import get_notifications_service
from models.notifications import NotificationType

from controllers.file_upload import (
    upload_file_to_cloudinary,
    validate_upload_results,
    to_image_upload_responses,
    validate_file_types,
    file_greater_than_max_size,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_PROOF_OF_OWNERSHIP_TYPES,
)

from services.email import EmailService
from services.template import TemplateService

from typing import List, Dict, Tuple, Optional
from pydantic import ValidationError

from utils.masking import mask_landlord_details, mask_listings_for_user


class ListingsService:
    """Service class for handling property listing operations.

    This service encapsulates the business logic for creating, updating,
    retrieving, verifying, and deleting property listings.
    """

    def __init__(self):
        self.listing_repo = get_listing_repository()
        self.landlord_repo = get_landlord_repository()

    async def create_property_listing(
        self,
        description: str,
        price: Decimal,
        address: str,
        city: str,
        state: str,
        bedrooms: int,
        amenities: List[str],
        property_type: PropertyType,
        images: List[UploadFile],
        proof_of_ownership: List[UploadFile],
        current_user: LandLord,
        email_service: EmailService,
        template_service: TemplateService,
        background_tasks: BackgroundTasks,
    ):
        """Creates a new property listing for a KYC verified landlord.

        Validates the user's KYC status, uploads images and proof of ownership
        documents to Cloudinary, creates the listing in the database, and
        sends notification emails to the landlord and support team.

        Args:
            description (str): Brief description of the property.
            price (Decimal): Rental price of the property.
            address (str): Street address of the property.
            city (str): City where the property is located.
            state (str): State where the property is located.
            bedrooms (int): Number of bedrooms in the property.
            amenities (List[str]): List of amenities available.
            property_type (PropertyType): Type of property (apartment, house, etc.).
            images (List[UploadFile]): Images of the property (minimum 3).
            proof_of_ownership (List[UploadFile]): Ownership documents (minimum 1).
            current_user (LandLord): The authenticated landlord user.
            email_service (EmailService): Service for sending emails.
            template_service (TemplateService): Service for rendering email templates.
            background_tasks (BackgroundTasks): FastAPI background tasks.

        Returns:
            JSONResponse: Success response with the created listing or error response.
        """
        # Check if user is KYC verified
        if not current_user.kyc_verified:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "KYC verification is required to create a property listing."
                },
            )

        image_upload_tasks = []
        proof_upload_tasks = []

        with logfire.span(
            f"Creating new property listing for user: {current_user.email}"
        ):
            if not len(images) >= 3:
                logfire.info("Insufficient images uploaded for property listing")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "detail": "At least 3 images are required for a property listing"
                    },
                )

            if not len(proof_of_ownership) >= 1:
                logfire.info(
                    "Insufficient proof of ownership documents uploaded for property listing"
                )
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "detail": "At least 1 proof of ownership document is required"
                    },
                )

            # Validate file sizes of the uploaded files
            for file in images + proof_of_ownership:
                if await file_greater_than_max_size(file):
                    logfire.info(
                        f"{current_user.id} uploaded a file: {file.filename} exceeds maximum allowed size for property listing"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": f"File {file.filename} exceeds maximum allowed size of 100 MB."
                        },
                    )
                logfire.info(
                    f"{current_user.id} uploaded a file: {file.filename} is within the allowed size limit for property listing"
                )

            # Validate file types of the uploaded files
            if error := await validate_file_types(images, ALLOWED_IMAGE_TYPES, "image"):
                logfire.info("Invalid image file types uploaded for property listing")
                return error

            if error := await validate_file_types(
                proof_of_ownership, ALLOWED_PROOF_OF_OWNERSHIP_TYPES, "proof of ownership"
            ):
                logfire.info(
                    "Invalid proof of ownership file types uploaded for property listing"
                )
                return error

            for image in images:
                image_upload_tasks.append(upload_file_to_cloudinary(image))

            for proof in proof_of_ownership:
                proof_upload_tasks.append(upload_file_to_cloudinary(proof))

            image_results: List[Tuple[int, Dict | None]] = await asyncio.gather(
                *image_upload_tasks, return_exceptions=True
            )
            proof_results: List[Tuple[int, Dict | None]] = await asyncio.gather(
                *proof_upload_tasks, return_exceptions=True
            )

            logfire.info(
                f"Requests to upload images and documents, sent for {current_user.email}"
            )

            # Fail if any proof of ownership upload failed
            if error := await validate_upload_results(
                proof_results, "Failed to upload proof of ownership documents"
            ):
                return error

            # Fail if any image upload failed
            if error := await validate_upload_results(
                image_results, "Failed to upload property images"
            ):
                return error

            logfire.info(
                f"Documents and images uploaded successfully for {current_user.email}"
            )

            # Validate and extract upload responses
            try:
                image_upload_responses = await to_image_upload_responses(image_results)
                proof_upload_responses = await to_image_upload_responses(proof_results)
            except ValidationError:
                logfire.error(
                    f"Validation error when processing upload responses for property listing for user {current_user.email}"
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Failed to process uploaded files"},
                )

            new_listing = Listing(
                description=description,
                price=price,
                location=ListingLocation(address=address, city=city, state=state),
                landlord=LandLordDetailsSummary(
                    landlord_id=str(current_user.id),
                    first_name=current_user.first_name,
                    last_name=current_user.last_name,
                    email=current_user.email,
                ),
                bedrooms=bedrooms,
                property_type=property_type,
            )

            # amenities comes as ["pool,gym,parking"] (single string in a list)
            # so we need to split it into a list of strings
            if len(amenities) == 1 and "," in amenities[0]:
                amenities = [a.strip() for a in amenities[0].split(",")]

            new_listing.amenities = amenities

            for upload_response in image_upload_responses:
                new_listing.images.append(upload_response.secure_url)

            for upload_response in proof_upload_responses:
                new_listing.proof_of_ownership.append(upload_response.secure_url)

            # Save new listing to database
            try:
                await self.listing_repo.save(new_listing)
                current_user.listings.append(str(new_listing.id))
                await self.landlord_repo.save(current_user)
            except WriteError:
                logfire.error(
                    f"Write error when saving new listing for user: {current_user.email}"
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Failed to create property listing"},
                )
            except ConnectionFailure:
                logfire.error(
                    f"Database connection failure when saving new listing for user: {current_user.email}"
                )
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"detail": "Service unavailable. Please try again later."},
                )
            except PyMongoError as e:
                logfire.error(
                    f"Unexpected database error when saving new listing for user: {current_user.email} - {e}"
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "detail": "An unexpected error occurred while creating the property listing."
                    },
                )

        user_email_html_content = (
            template_service.render_listing_pending_verification_email(
                landlord_name=f"{current_user.first_name} {current_user.last_name}",
                property_address=new_listing.location.address,
                property_city=new_listing.location.city,
                property_state=new_listing.location.state,
                property_type=new_listing.property_type.value,
                bedrooms=new_listing.bedrooms,
                price=new_listing.price,
                listing_id=str(new_listing.id),
                submission_date=new_listing.updated_at,
            )
        )

        support_email_html_content = (
            template_service.render_property_needs_verification_email(
                landlord_name=f"{current_user.first_name} {current_user.last_name}",
                landlord_email=current_user.email,
                landlord_id=str(current_user.id),
                kyc_status="Verified" if current_user.kyc_verified else "Not Verified",
                submission_date=new_listing.updated_at,
                image_count=len(new_listing.images),
                proof_count=len(new_listing.proof_of_ownership),
                property_address=new_listing.location.address,
                property_city=new_listing.location.city,
                property_state=new_listing.location.state,
                property_type=new_listing.property_type.value,
                bedrooms=new_listing.bedrooms,
                price=new_listing.price,
                listing_id=str(new_listing.id),
            )
        )

        # Email landlord on pending verification
        background_tasks.add_task(
            email_service.send_email,
            current_user.email,
            "Property Listing Under Review",
            user_email_html_content,
        )
        background_tasks.add_task(
            email_service.send_email,
            os.getenv("FIND_MY_RENT_SUPPORT_EMAIL"),
            "Property Listing Needs Verification",
            support_email_html_content,
        )

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Property listing is under review",
                "listing": new_listing.model_dump(mode="json"),
            },
        )

    async def update_property_listing(
        self,
        current_user: LandLord,
        listing_id: str,
        email_service: EmailService,
        template_service: TemplateService,
        background_tasks: BackgroundTasks,
        description: Optional[str] = None,
        price: Optional[Decimal] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        bedrooms: Optional[int] = None,
        amenities: Optional[List[str]] = None,
        property_type: Optional[PropertyType] = None,
        images: List[UploadFile] = [],
        proof_of_ownership: List[UploadFile] = [],
    ):
        """Updates an existing property listing.

        Updates the specified fields of a listing. If certain fields are updated
        (address, city, state, bedrooms, amenities, property_type, images, or
        proof_of_ownership), the listing verification status is reset and a
        re-verification email is sent to the support team.

        Args:
            current_user (LandLord): The authenticated landlord user.
            listing_id (str): The unique identifier of the listing to update.
            email_service (EmailService): Service for sending emails.
            template_service (TemplateService): Service for rendering email templates.
            background_tasks (BackgroundTasks): FastAPI background tasks.
            description (Optional[str]): Updated property description.
            price (Optional[Decimal]): Updated rental price.
            address (Optional[str]): Updated street address.
            city (Optional[str]): Updated city.
            state (Optional[str]): Updated state.
            bedrooms (Optional[int]): Updated number of bedrooms.
            amenities (Optional[List[str]]): Updated list of amenities.
            property_type (Optional[PropertyType]): Updated property type.
            images (List[UploadFile]): New images to replace existing ones.
            proof_of_ownership (List[UploadFile]): New ownership documents.

        Returns:
            JSONResponse: Success response with the updated listing or error response.
        """
        image_upload_tasks = []
        proof_upload_tasks = []
        to_trigger_verification = [
            address,
            city,
            state,
            bedrooms,
            amenities,
            property_type,
            images,
            proof_of_ownership,
        ]

        if any(to_trigger_verification):
            logfire.info(
                f"Triggering verification for listing update by user: {current_user.email}"
            )

            listing_in_db = await self.listing_repo.find_by_landlord_and_id(
                str(current_user.id), listing_id
            )

            if not listing_in_db:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Property listing not found"},
                )

            listing_in_db.verified = None

        if images:
            # Validate file sizes of the uploaded files
            for file in images:
                if await file_greater_than_max_size(file):
                    logfire.info(
                        f"{current_user.id} uploaded a file: {file.filename} exceeds maximum allowed size for property listing"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": f"File {file.filename} exceeds maximum allowed size of 100 MB."
                        },
                    )
            # Validate file types of the uploaded files
            if error := await validate_file_types(images, ALLOWED_IMAGE_TYPES, "image"):
                logfire.info("Invalid image file types uploaded for property listing")
                return error

            for image in images:
                image_upload_tasks.append(upload_file_to_cloudinary(image))

            image_results: List[Tuple[int, Dict | None]] = await asyncio.gather(
                *image_upload_tasks, return_exceptions=True
            )

            logfire.info(f"Requests to upload images, sent for {current_user.email}")

            # Fail if any image upload failed
            if error := await validate_upload_results(
                image_results, "Failed to upload property images"
            ):
                return error

            logfire.info(
                f"Documents and images uploaded successfully for {current_user.email}"
            )

            # Validate and extract upload responses
            try:
                image_upload_responses = await to_image_upload_responses(image_results)

                # delete urls to old images if new ones submitted
                listing_in_db.images.clear()

                for upload_response in image_upload_responses:
                    listing_in_db.images.append(upload_response.secure_url)

            except ValidationError:
                logfire.error(
                    f"Validation error when processing upload responses for property listing for user {current_user.email}"
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Failed to process uploaded files"},
                )

        if proof_of_ownership:
            # Validate file sizes of the uploaded files
            for file in images:
                if await file_greater_than_max_size(file):
                    logfire.info(
                        f"{current_user.id} uploaded a file: {file.filename} exceeds maximum allowed size for property listing"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": f"File {file.filename} exceeds maximum allowed size of 100 MB."
                        },
                    )

            # Validate file types of the uploaded files
            if error := await validate_file_types(
                proof_of_ownership, ALLOWED_PROOF_OF_OWNERSHIP_TYPES, "proof of ownership"
            ):
                logfire.info(
                    "Invalid proof of ownership file types uploaded for property listing"
                )
                return error

            for proof in proof_of_ownership:
                proof_upload_tasks.append(upload_file_to_cloudinary(proof))

            proof_results: List[Tuple[int, Dict | None]] = await asyncio.gather(
                *proof_upload_tasks, return_exceptions=True
            )

            logfire.info(f"Requests to upload images, sent for {current_user.email}")

            # # Fail if any proof of ownership upload failed
            if error := await validate_upload_results(
                proof_results, "Failed to upload proof of ownership documents"
            ):
                return error

            logfire.info(
                f"Documents and images uploaded successfully for {current_user.email}"
            )

            # Validate and extract upload responses
            try:
                proof_upload_responses = await to_image_upload_responses(proof_results)

                listing_in_db.proof_of_ownership.clear()  # delete urls to old proof of ownership documents

                for upload_response in proof_upload_responses:
                    listing_in_db.proof_of_ownership.append(upload_response.secure_url)
            except ValidationError:
                logfire.error(
                    f"Validation error when processing upload responses for property listing for user {current_user.email}"
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "Failed to process uploaded files"},
                )

        listing_in_db.description = (
            description if description else listing_in_db.description
        )
        listing_in_db.price = price if price else listing_in_db.price
        listing_in_db.location.address = (
            address if address else listing_in_db.location.address
        )
        listing_in_db.location.state = (
            state if state else listing_in_db.location.state
        )
        listing_in_db.location.city = city if city else listing_in_db.location.city
        listing_in_db.bedrooms = bedrooms if bedrooms else listing_in_db.bedrooms
        listing_in_db.property_type = (
            property_type.value if property_type else listing_in_db.property_type.value
        )

        # amenities comes as ["pool,gym,parking"] (single string in a list)
        # so we need to split it into a list of strings
        if len(amenities) == 1 and "," in amenities[0]:
            amenities = [a.strip() for a in amenities[0].split(",")]

        listing_in_db.amenities = amenities if amenities else listing_in_db.amenities

        listing_in_db.updated_at = datetime.now()
        await self.listing_repo.save(listing_in_db)

        # Email support in background to verify the property listing again
        if any(to_trigger_verification):
            html_content = template_service.render_property_needs_verification_email(
                landlord_name=f"{current_user.first_name} {current_user.last_name}",
                landlord_email=current_user.email,
                landlord_id=str(current_user.id),
                kyc_status="Verified" if current_user.kyc_verified else "Not Verified",
                submission_date=datetime.now(),
                image_count=len(listing_in_db.images),
                proof_count=len(listing_in_db.proof_of_ownership),
                property_address=listing_in_db.location.address,
                property_city=listing_in_db.location.city,
                property_state=listing_in_db.location.state,
                property_type=listing_in_db.property_type.value,
                bedrooms=listing_in_db.bedrooms,
                price=listing_in_db.price,
                listing_id=str(listing_in_db.id),
            )

            logfire.info("Sending listing update verification email to support team")
            background_tasks.add_task(
                email_service.send_email,
                to="dev@ground-shakers.xyz",
                subject="Property Listing Update Verification",
                html_content=html_content,
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Property listing updated successfully",
                "listing": listing_in_db.model_dump(mode="json", by_alias=True),
            },
        )

    async def get_property_listing(
        self,
        listing_id: str,
        current_user: LandLord | Admin,
        collection: ListingCollectionTypes = ListingCollectionTypes.GENERAL,
    ):
        """Retrieves a specific property listing by ID.

        Fetches a single listing based on the collection type and user permissions.
        Admin users can retrieve any listing, while regular users can only retrieve
        their own listings (OWNED) or verified public listings (GENERAL).

        Args:
            listing_id (str): The unique identifier of the listing to retrieve.
            current_user (LandLord | Admin): The authenticated user.
            collection (ListingCollectionTypes): Type of collection to query from.

        Returns:
            JSONResponse: Success response with the listing or error response.
        """
        try:
            listing = None
            is_admin_user = (
                current_user.user_type == UserType.ADMIN
                or current_user.user_type == UserType.SUPER_USER
            )

            # Fetch listing when usertype is admin or superuser
            if is_admin_user:
                logfire.info("Admin user is fetching a listing")
                listing = await self.listing_repo.get_by_id(listing_id)
            # If fetching owned listings, ensure user is KYC verified
            elif collection == ListingCollectionTypes.OWNED:
                listing = await self.listing_repo.find_by_landlord_and_id(
                    str(current_user.id), listing_id
                )
            elif collection == ListingCollectionTypes.GENERAL:
                listing = await self.listing_repo.find_verified_by_id(listing_id)

            if not listing:
                logfire.info(
                    f"Listing with ID {listing_id} not found for user: {current_user.id}"
                )
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Property listing not found"},
                )

            # Serialize listing based on collection type or whether it's an admin user fetching the listing
            if collection == ListingCollectionTypes.OWNED or is_admin_user:
                serialized_listing = listing.model_dump(mode="json", by_alias=True)
            elif collection == ListingCollectionTypes.GENERAL:
                # Include landlord details but mask for non-premium users
                serialized_listing = listing.model_dump(
                    mode="json", by_alias=True, exclude=["proof_of_ownership"]
                )
                serialized_listing = mask_landlord_details(serialized_listing, current_user.premium)

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Property listing retrieved successfully",
                    "listing": serialized_listing,
                },
            )
        except ConnectionFailure:
            logfire.error(
                f"Database connection failure when retrieving listing ID: {listing_id} for user: {current_user.id}"
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(
                f"Unexpected database error when retrieving listing ID: {listing_id} for user: {current_user.id} - {e}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An unexpected error occurred while retrieving the property listing."
                },
            )
        except Exception as e:
            logfire.error(
                f"Unexpected error when retrieving listing ID: {listing_id} for user: {current_user.id} - {e}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An unexpected error occurred while retrieving the property listing."
                },
            )

    async def get_property_listings(
        self,
        current_user: LandLord,
        offset: int = 0,
        limit: int = 100,
        collection: ListingCollectionTypes = ListingCollectionTypes.GENERAL,
    ):
        """Retrieves a paginated list of property listings.

        Fetches multiple listings based on the collection type. For OWNED listings,
        returns all listings belonging to the current user. For GENERAL listings,
        returns only verified public listings.

        Args:
            current_user (LandLord): The authenticated user.
            offset (int): Number of items to skip for pagination.
            limit (int): Maximum number of items to return.
            collection (ListingCollectionTypes): Type of collection to query from.

        Returns:
            JSONResponse: Success response with the listings or error response.
        """
        try:
            # Check if user is KYC verified
            if collection == ListingCollectionTypes.OWNED:
                # Retrieve all listings for the current user with pagination, verified and unverified
                listings = await self.listing_repo.find_by_landlord(
                    str(current_user.id), offset, limit
                )
            elif collection == ListingCollectionTypes.GENERAL:
                # Retrieve all listings with pagination
                listings = await self.listing_repo.find_verified(offset, limit)

            # Handle case where no listings are found
            if not listings:
                logfire.info(
                    f"No listings found for user: {current_user.email} in collection: {collection}"
                )
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "No property listings found"},
                )

            # Serialize listings based on collection type
            serialized_listings = []
            if collection == ListingCollectionTypes.OWNED:
                serialized_listings = [
                    listing.model_dump(mode="json", by_alias=True)
                    for listing in listings
                ]
            elif collection == ListingCollectionTypes.GENERAL:
                # Include landlord details but mask for non-premium users
                serialized_listings = [
                    mask_landlord_details(
                        listing.model_dump(mode="json", by_alias=True, exclude=["proof_of_ownership"]),
                        current_user.premium
                    )
                    for listing in listings
                ]
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"listings": serialized_listings},
            )
        except ConnectionFailure:
            logfire.error(
                f"Database connection failure when retrieving listings for user: {current_user.email}"
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(
                f"Unexpected database error when retrieving listings for user: {current_user.email} - {e}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An unexpected error occurred while retrieving property listings."
                },
            )
        except Exception as e:
            logfire.error(
                f"Unexpected error when retrieving listings for user: {current_user.email} - {e}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An unexpected error occurred while retrieving property listings."
                },
            )

    async def verify_listing(
        self,
        current_user: Admin,
        listing_id: str,
        verified: bool,
        background_tasks: BackgroundTasks,
        email_service: EmailService,
        template_service: TemplateService,
    ):
        """Updates the verification status of a property listing.

        Admin-only endpoint to approve or reject a property listing. Sends
        an email notification to the landlord about the verification status.

        Args:
            current_user (Admin): The authenticated admin user.
            listing_id (str): The unique identifier of the listing to verify.
            verified (bool): The new verification status (True for approved, False for rejected).
            background_tasks (BackgroundTasks): FastAPI background tasks.
            email_service (EmailService): Service for sending emails.
            template_service (TemplateService): Service for rendering email templates.

        Returns:
            JSONResponse: Success response with the updated listing or error response.
        """
        listing_in_db = await self.listing_repo.get_by_id(listing_id)

        if not listing_in_db:
            logfire.info(
                f"Listing with ID {listing_id} not found for verification by user: {current_user.email}"
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Property listing not found"},
            )

        logfire.info(
            f"Updating verification status for listing ID {listing_id} to {verified} by user: {current_user.email}"
        )
        listing_in_db.verified = verified
        await self.listing_repo.save(listing_in_db)

        # Create in-app notification for landlord
        
        notifications_service = get_notifications_service()
        notification_type = NotificationType.LISTING_APPROVED if verified else NotificationType.LISTING_REJECTED
        notification_title = "Listing Approved" if verified else "Listing Rejected"
        notification_message = (
            f"Your listing at {listing_in_db.location.address}, {listing_in_db.location.city} has been {'approved and is now live' if verified else 'rejected'}."
        )
        
        await notifications_service.create_notification(
            user_id=str(listing_in_db.landlord.id),
            notification_type=notification_type,
            title=notification_title,
            message=notification_message,
            related_id=str(listing_in_db.id),
        )

        html_content = template_service.render_property_verification_update_email(
            landlord_name=f"{listing_in_db.landlord.first_name} {listing_in_db.landlord.last_name}",
            property_address=listing_in_db.location.address,
            property_city=listing_in_db.location.city,
            property_state=listing_in_db.location.state,
            property_type=listing_in_db.property_type.value,
            bedrooms=listing_in_db.bedrooms,
            price=listing_in_db.price,
            listing_id=str(listing_in_db.id),
            verification_status="accepted" if verified else "rejected",
        )

        logfire.info("Sending listing verification status email to landlord")
        background_tasks.add_task(
            email_service.send_email,
            to=listing_in_db.landlord.email,
            subject="Property Listing Verification Status",
            content=html_content,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Property listing verification status updated successfully",
                "listing": listing_in_db.model_dump(mode="json", by_alias=True),
            },
        )

    async def delete_property_listing(self, listing_id: str, current_user: LandLord):
        """Deletes a property listing.

        Allows landlords to delete their own listings or admin users to delete
        any listing. Removes the listing from the database and updates the
        user's listings array.

        Args:
            listing_id (str): The unique identifier of the listing to delete.
            current_user (LandLord): The authenticated user.

        Returns:
            JSONResponse: Success response or error response.
        """
        try:
            user_role = current_user.type.value
            listing = None
            # Landlords can only delete their own property listings
            if user_role == UserType.LANDLORD.value:
                listing = await self.listing_repo.find_by_landlord_and_id(
                    str(current_user.id), listing_id
                )
            # Admin/Support can delete any listing
            elif (
                user_role == UserType.ADMIN.value
                or user_role == UserType.SUPER_USER.value
            ):
                listing = await self.listing_repo.get_by_id(listing_id)

            if not listing:
                logfire.info(
                    f"Listing with ID {listing_id} not found for deletion by user: {current_user.id}"
                )
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "Property listing not found"},
                )

            current_user.listings.remove(str(listing.id))

            await self.landlord_repo.save(current_user)
            await self.listing_repo.delete(listing)

            return JSONResponse(
                status_code=status.HTTP_204_NO_CONTENT,
                content={"message": "Property listing deleted successfully"},
            )
        except ConnectionFailure:
            logfire.error(
                f"Database connection failure when deleting listing ID: {listing_id} for user: {current_user.id}"
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(
                f"Unexpected database error when deleting listing ID: {listing_id} for user: {current_user.id} - {e}"
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An unexpected error occurred while deleting the property listing."
                },
            )

    async def search_property_listings(
        self,
        current_user: LandLord,
        query: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        property_type: Optional[PropertyType] = None,
        min_bedrooms: Optional[int] = None,
        max_bedrooms: Optional[int] = None,
        amenities: Optional[List[str]] = None,
        available_only: bool = True,
        offset: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        """Searches property listings with various filter criteria.

        Searches through verified listings and returns matches based on the
        provided filters. All filters are optional and can be combined.

        Args:
            query (Optional[str]): Text search on property description.
            min_price (Optional[Decimal]): Minimum rental price filter.
            max_price (Optional[Decimal]): Maximum rental price filter.
            city (Optional[str]): Filter by city name (case-insensitive).
            state (Optional[str]): Filter by state name (case-insensitive).
            property_type (Optional[PropertyType]): Filter by property type.
            min_bedrooms (Optional[int]): Minimum number of bedrooms.
            max_bedrooms (Optional[int]): Maximum number of bedrooms.
            amenities (Optional[List[str]]): Required amenities (all must match).
            available_only (bool): Only return available listings. Defaults to True.
            offset (int): Number of listings to skip. Defaults to 0.
            limit (int): Maximum listings to return. Defaults to 20.
            sort_by (str): Field to sort by. Defaults to "created_at".
            sort_order (str): Sort direction ("asc" or "desc"). Defaults to "desc".

        Returns:
            JSONResponse: Search results with listings, total count, and pagination info.
        """
        try:
            with logfire.span("Searching property listings"):
                # Validate price range
                if min_price is not None and max_price is not None:
                    if min_price > max_price:
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={"detail": "min_price cannot be greater than max_price"},
                        )

                # Validate bedroom range
                if min_bedrooms is not None and max_bedrooms is not None:
                    if min_bedrooms > max_bedrooms:
                        return JSONResponse(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            content={"detail": "min_bedrooms cannot be greater than max_bedrooms"},
                        )

                # Build filters dict for repository
                filters = {
                    "query": query,
                    "min_price": min_price,
                    "max_price": max_price,
                    "city": city,
                    "state": state,
                    "property_type": property_type,
                    "min_bedrooms": min_bedrooms,
                    "max_bedrooms": max_bedrooms,
                    "amenities": amenities,
                    "available_only": available_only,
                }

                logfire.info(f"Searching listings with filters: {filters}")

                # Execute search
                listings, total = await self.listing_repo.search_listings(
                    filters=filters,
                    offset=offset,
                    limit=limit,
                    sort_by=sort_by,
                    sort_order=sort_order,
                )

                logfire.info(f"Search returned {len(listings)} listings out of {total} total matching")

                # Serialize listings with landlord details masked for non-premium users
                serialized_listings = [
                    mask_landlord_details(
                        listing.model_dump(mode="json", by_alias=True, exclude=["proof_of_ownership"]),
                        current_user.premium
                    )
                    for listing in listings
                ]

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "listings": serialized_listings,
                        "total": total,
                        "offset": offset,
                        "limit": limit,
                        "has_more": (offset + len(listings)) < total,
                    },
                )

        except ConnectionFailure:
            logfire.error("Database connection failure during listing search")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service unavailable. Please try again later."},
            )
        except PyMongoError as e:
            logfire.error(f"Unexpected database error during listing search: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An unexpected error occurred while searching listings."
                },
            )
        except Exception as e:
            logfire.error(f"Unexpected error during listing search: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An unexpected error occurred while searching listings."
                },
            )


@lru_cache()
def get_listings_service():
    """Returns a cached instance of ListingsService.

    Uses lru_cache to ensure only one instance of ListingsService is created
    and reused across the application.

    Returns:
        ListingsService: The singleton ListingsService instance.
    """
    return ListingsService()
