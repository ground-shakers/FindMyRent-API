"""Contains all functions for handling KYC responses and validation."""

from schema.kyc import (
    KYCWebhookResponse,
    KYCVerificationDecisionDetails,
    IDVerificationDetails,
    KYCSessionReviewDetails,
    IDVerificationWarnings,
    ParsedAddressDetails,
    AddressCoordinates,
    AddressGeometry,
    AddressViewPortCoordinateDetails,
    AddressRawResults,
)


def validate_kyc_data(kyc_data: dict) -> KYCWebhookResponse:
    """This function validates and parses KYC webhook data into structured Pydantic models.

    Args:
        kyc_data (dict): The raw KYC data from the webhook.

    Returns:
        KYCWebhookResponse: The validated and structured KYC webhook response.
    """
    
    
    session_id: str = kyc_data.get("session_id")
    session_status: str = kyc_data.get("status")
    vendor_data: str = kyc_data.get("vendor_data")
    session_decision: dict = kyc_data.get("decision")

    session_metadata: dict | None = kyc_data.get("metadata")

    if not session_decision:
        # If there's no decision data, it indicates the session has just been initiated
        # There's no detailed decision to parse yet, so we directly validate the response
        
        validated_response = KYCWebhookResponse(**kyc_data)
    else:
        # Parse raw ID verification details from webhook for better IDE support
        id_verification_details: dict = session_decision.get("id_verification")
        id_verification_warnings: list[dict] = id_verification_details.get("warnings")
        id_verification_reviews: list[dict] = session_decision.get("reviews")

        # Parse raw address details from webhook for better IDE support
        parsed_address_details: dict = id_verification_details.get("parsed_address")
        address_raw_results: dict[str, str | dict[str, dict[str, float | dict[str, float]]]] = (
            parsed_address_details.get("raw_results")
        )

        # Validate parsed address details
        validated_parsed_address_details = ParsedAddressDetails(
            id=parsed_address_details.get("id"),
            city=parsed_address_details.get("city"),
            region=parsed_address_details.get("region"),
            street_1=parsed_address_details.get("street_1"),
            street_2=parsed_address_details.get("street_2"),
            postal_code=parsed_address_details.get("postal_code"),
            raw_results=AddressRawResults(
                geometry=AddressGeometry(
                    location=AddressCoordinates(
                        latitude=address_raw_results.get("geometry")
                        .get("location")
                        .get("lat"),
                        longitude=address_raw_results.get("geometry")
                        .get("location")
                        .get("lng"),
                    ),
                    location_type=address_raw_results.get("geometry").get(
                        "location_type"
                    ),
                    viewport=AddressViewPortCoordinateDetails(
                        northeast=AddressCoordinates(
                            latitude=address_raw_results.get("geometry")
                            .get("viewport")
                            .get("northeast")
                            .get("lat"),
                            longitude=address_raw_results.get("geometry")
                            .get("viewport")
                            .get("northeast")
                            .get("lng"),
                        ),
                        southwest=AddressCoordinates(
                            latitude=address_raw_results.get("geometry")
                            .get("viewport")
                            .get("southwest")
                            .get("lat"),
                            longitude=address_raw_results.get("geometry")
                            .get("viewport")
                            .get("southwest")
                            .get("lng"),
                        ),
                    ),
                )
            ),
        )

        # Validate ID verification details
        validated_id_verification_details = IDVerificationDetails(
            status=id_verification_details.get("status"),
            document_type=id_verification_details.get("document_type"),
            document_number=id_verification_details.get("document_number"),
            personal_number=id_verification_details.get("personal_number"),
            portrait_image=id_verification_details.get("portrait_image"),
            front_image=id_verification_details.get("front_image"),
            back_image=id_verification_details.get("back_image"),
            back_video=id_verification_details.get("back_video"),
            full_front_image=id_verification_details.get("full_front_image"),
            full_back_image=id_verification_details.get("full_back_image"),
            date_of_birth=id_verification_details.get("date_of_birth"),
            age=id_verification_details.get("age"),
            expiration_date=id_verification_details.get("expiration_date"),
            date_of_issue=id_verification_details.get("date_of_issue"),
            issuing_state=id_verification_details.get("issuing_state"),
            issuing_state_name=id_verification_details.get("issuing_state_name"),
            first_name=id_verification_details.get("first_name"),
            last_name=id_verification_details.get("last_name"),
            full_name=id_verification_details.get("full_name"),
            gender=id_verification_details.get("gender"),
            address=id_verification_details.get("address"),
            formatted_address=id_verification_details.get("formatted_address"),
            place_of_birth=id_verification_details.get("place_of_birth"),
            marital_status=id_verification_details.get("marital_status"),
            nationality=id_verification_details.get("nationality"),
            parsed_address=validated_parsed_address_details,
            extra_files=id_verification_details.get("extra_files"),
            warnings=[
                IDVerificationWarnings(**warning)
                for warning in id_verification_warnings
            ],
        )

        # Validate KYC verification decision details
        validated_decision_details = KYCVerificationDecisionDetails(
            session_id=session_id,
            session_number=session_decision.get("session_number"),
            session_url=session_decision.get("session_url"),
            status=session_decision.get("status"),
            workflow_id=session_decision.get("workflow_id"),
            features=session_decision.get("features"),
            vendor_data=session_decision.get("vendor_data"),
            metadata=session_decision.get("metadata"),
            expected_details=session_decision.get("expected_details"),
            contact_details=session_decision.get("contact_details"),
            callback=session_decision.get("callback"),
            id_verification=validated_id_verification_details,
            reviews=[
                KYCSessionReviewDetails(**review) for review in id_verification_reviews
            ],
            created_at=session_decision.get("created_at"),
        )

        # Prepare final validated response
        validated_response = KYCWebhookResponse(
            session_id=session_id,
            status=session_status,
            vendor_data=vendor_data,
            decision=validated_decision_details,
            metadata=session_metadata,
        )
        
    return validated_response