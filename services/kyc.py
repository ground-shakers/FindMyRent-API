"""Contains all functions for handling KYC responses and validation."""
import logfire
import json

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


from typing import Optional


def validate_kyc_data(kyc_data: dict[str, str | int | dict | None]) -> KYCWebhookResponse:
    """This function validates and parses KYC webhook data into structured Pydantic models.

    Args:
        kyc_data (dict): The raw KYC data from the webhook.

    Returns:
        KYCWebhookResponse: The validated and structured KYC webhook response.
    """

    session_id: str = kyc_data.get("session_id")
    session_status: str = kyc_data.get("status")
    vendor_data: str = kyc_data.get("vendor_data")
    workflow_id: str = kyc_data.get("workflow_id")
    webhook_type: str = kyc_data.get("webhook_type")
    created_at: int = kyc_data.get("created_at")
    timestamp: int = kyc_data.get("timestamp")
    session_decision: Optional[dict[str, str | int | dict | list | None]] = (
        kyc_data.get("decision")
    )
    session_metadata: Optional[dict[str, str | int | float | bool]] = kyc_data.get(
        "metadata"
    )

    if not session_decision:
        # If there's no decision data, it indicates the session has just been initiated
        # There's no detailed decision to parse yet, so we directly validate the response
        validated_response = KYCWebhookResponse(**kyc_data)
    else:
        try:
            # Parse raw ID verification details from webhook for better IDE support
            id_verification_details: dict[str, str | int | list | dict | None] = (
                session_decision.get("id_verification")
            )
            id_verification_warnings: list[dict[str, str | int | float | dict]] = (
                id_verification_details.get("warnings", [])
            )
            id_verification_reviews: list[dict[str, str | None]] = session_decision.get(
                "reviews", []
            )

            # Parse raw address details from webhook for better IDE support
            parsed_address_details: Optional[dict[str, str | dict | None]] = (
                id_verification_details.get("parsed_address")
            )

            # Handle parsed_address being None
            validated_parsed_address_details: Optional[ParsedAddressDetails] = None
            if parsed_address_details:
                address_raw_results: Optional[dict[str, dict[str, str | dict]]] = (
                    parsed_address_details.get("raw_results")
                )

                if address_raw_results:
                    geometry: dict[
                        str, str | dict[str, float] | dict[str, dict[str, float]]
                    ] = address_raw_results.get("geometry", {})
                    location: dict[str, float] = geometry.get("location", {})
                    viewport: dict[str, dict[str, float]] = geometry.get("viewport", {})
                    northeast: dict[str, float] = viewport.get("northeast", {})
                    southwest: dict[str, float] = viewport.get("southwest", {})

                    validated_parsed_address_details = ParsedAddressDetails(
                        id=parsed_address_details.get("id"),
                        address_type=parsed_address_details.get("address_type"),
                        city=parsed_address_details.get("city"),
                        label=parsed_address_details.get("label"),
                        region=parsed_address_details.get("region"),
                        street_1=parsed_address_details.get("street_1"),
                        street_2=parsed_address_details.get("street_2"),
                        postal_code=parsed_address_details.get("postal_code"),
                        raw_results=AddressRawResults(
                            geometry=AddressGeometry(
                                location=(
                                    AddressCoordinates(
                                        latitude=location.get("lat"),
                                        longitude=location.get("lng"),
                                    )
                                    if location
                                    else None
                                ),
                                location_type=geometry.get("location_type"),
                                viewport=(
                                    AddressViewPortCoordinateDetails(
                                        northeast=(
                                            AddressCoordinates(
                                                latitude=northeast.get("lat"),
                                                longitude=northeast.get("lng"),
                                            )
                                            if northeast
                                            else None
                                        ),
                                        southwest=(
                                            AddressCoordinates(
                                                latitude=southwest.get("lat"),
                                                longitude=southwest.get("lng"),
                                            )
                                            if southwest
                                            else None
                                        ),
                                    )
                                    if viewport
                                    else None
                                ),
                            )
                        ),
                    )
                else:
                    # raw_results is None, create minimal ParsedAddressDetails
                    validated_parsed_address_details = ParsedAddressDetails(
                        id=parsed_address_details.get("id"),
                        address_type=parsed_address_details.get("address_type"),
                        city=parsed_address_details.get("city"),
                        label=parsed_address_details.get("label"),
                        region=parsed_address_details.get("region"),
                        street_1=parsed_address_details.get("street_1"),
                        street_2=parsed_address_details.get("street_2"),
                        postal_code=parsed_address_details.get("postal_code"),
                        raw_results=None,
                    )

            # Validate ID verification details
            extra_files_raw: list[str] = id_verification_details.get("extra_files", [])

            validated_id_verification_details = IDVerificationDetails(
                status=id_verification_details.get("status"),
                document_type=id_verification_details.get("document_type"),
                document_number=id_verification_details.get("document_number"),
                personal_number=id_verification_details.get("personal_number"),
                portrait_image=id_verification_details.get("portrait_image"),
                front_image=id_verification_details.get("front_image"),
                front_video=id_verification_details.get("front_video"),
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
                extra_files=extra_files_raw,
                warnings=[
                    IDVerificationWarnings(**warning)
                    for warning in id_verification_warnings
                ],
            )

            # Extract strongly typed fields from session_decision
            features: list[str] = session_decision.get("features", [])
            expected_details: dict[str, str | int] = session_decision.get(
                "expected_details", {}
            )
            contact_details: dict[str, str | bool | None] = session_decision.get(
                "contact_details", {}
            )
            session_number: int = session_decision.get("session_number")
            session_url: str = session_decision.get("session_url")
            decision_status: str = session_decision.get("status")
            decision_created_at: str = session_decision.get("created_at")
            callback: Optional[str] = session_decision.get("callback")

            # Validate KYC verification decision details
            validated_decision_details = KYCVerificationDecisionDetails(
                session_id=session_id,
                session_number=session_number,
                session_url=session_url,
                status=decision_status,
                workflow_id=workflow_id,
                features=features,
                vendor_data=vendor_data,
                metadata=session_metadata,
                expected_details=expected_details,
                contact_details=contact_details,
                callback=callback,
                id_verification=validated_id_verification_details,
                reviews=[
                    KYCSessionReviewDetails(**review)
                    for review in id_verification_reviews
                ],
                created_at=decision_created_at,
            )

            # Prepare final validated response with ALL required fields
            validated_response = KYCWebhookResponse(
                session_id=session_id,
                workflow_id=workflow_id,
                vendor_data=vendor_data,
                metadata=session_metadata,
                status=session_status,
                webhook_type=webhook_type,
                created_at=created_at,
                timestamp=timestamp,
                decision=validated_decision_details,
            )

        except Exception as e:
            logfire.error(f"Error validating KYC data: {str(e)}")
            logfire.error(f"Problematic data: {json.dumps(kyc_data, indent=2)}")
            raise e

    return validated_response