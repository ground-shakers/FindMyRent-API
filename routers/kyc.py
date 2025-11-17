import json
import logfire

from fastapi import APIRouter, Request, Security, HTTPException, status
from fastapi.responses import JSONResponse

from security.helpers import get_current_active_user

from controllers.didit import create_kyc_session, verify_kyc_webhook_signature
from services.kyc import validate_kyc_data


from models.users import LandLord
from beanie import PydanticObjectId

from schema.kyc import CreateKYCSessionResponse

from typing import Annotated

from pprint import pprint

router = APIRouter(
    prefix="/api/v1/kyc",
    tags=["KYC Verification"],
)


@router.post("/session", response_model=CreateKYCSessionResponse)
async def create_kyc_verification_session(current_user: Annotated[LandLord, Security(get_current_active_user, scopes=["me"])]):
    response = await create_kyc_session(current_user)
    
    if not response:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Failed to create KYC session"
            }
        )
        
    validated_response = CreateKYCSessionResponse(**response)
    
    pprint(validated_response)
    
    current_user.kyc_verification_trail.append(validated_response) # Append KYC session to user's verification trail
    
    await current_user.save()  # Save the updated user document


    return validated_response


@router.post("/webhook")
async def handle_kyc_webhook(request: Request):

    with logfire.span("Handling KYC webhook..."):
        # Get the raw request body as string
        body = await request.body()
        body_str = body.decode()

        # Parse JSON for later use
        json_body: dict = json.loads(body_str)

        # Get headers
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not all([signature, timestamp]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

        try:

            verified_webhook_signature = await verify_kyc_webhook_signature(body_str, signature, timestamp)

            logfire.info("KYC webhook signature verified successfully")

            if not verified_webhook_signature:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

            # Validate and parse KYC data
            validated_kyc_data = validate_kyc_data(kyc_data=json_body)

            logfire.info("KYC Webhook response validated successfully")

            user_in_db = await LandLord.get(PydanticObjectId(validated_kyc_data.vendor_data))

            if not user_in_db:
                logfire.error(f"User not found for KYC webhook with vendor_data: {validated_kyc_data.vendor_data}")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"detail": "User not found for KYC webhook"}
                )

            # If decision not present it means flow is not completed yet
            # Add the webhook response to the user's kyc trail
            if not validated_kyc_data.decision:
                user_in_db.kyc_verification_trail.append(validated_kyc_data)

                await user_in_db.save()

                logfire.info(f"KYC webhook data appended to user {user_in_db.email} without decision. Current status: {validated_kyc_data.status}")

                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={"detail": "KYC data appended without decision"}
                )

            # If decision is present, check if decision status is "Approved"
            if validated_kyc_data.decision.status == "Approved":

                user_in_db.kyc_verified = True # Mark user as kyc verified
                user_in_db.kyc_verification_trail.append(validated_kyc_data) # Append kyc response to trail

                await user_in_db.save()

                logfire.info(f"KYC verified for user: {user_in_db.email}")
            else:
                user_in_db.kyc_verification_trail.append(validated_kyc_data) # Append kyc response to trail
                logfire.info(f"KYC not approved for user: {user_in_db.email} with decision: {validated_kyc_data.decision.status}")

        except Exception as e:
            logfire.info(f"Problematic data: {json.dumps(json_body, indent=2)}")
            logfire.error(f"Error verifying KYC webhook signature: {str(e)}")
