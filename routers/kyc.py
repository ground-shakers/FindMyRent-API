
from utils.logger import logger

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from schema.kyc import DiditWebhookPayload, WebhookResponse
from services.kyc import KYCService

router = APIRouter(
    prefix="/kyc",
    tags=["KYC Verification"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/webhook/didit",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Didit KYC Webhook",
    description="Webhook endpoint for receiving KYC verification status updates from Didit"
)
async def didit_webhook(payload: DiditWebhookPayload, request: Request):
    """
    Handle Didit KYC verification webhook.
    
    This endpoint receives webhook notifications from Didit when the KYC verification
    status changes. It updates the landlord's kyc_verified field based on the status:
    - "Approved": Sets kyc_verified to True
    - "Declined": Sets kyc_verified to False
    - Other statuses: No action taken
    
    The vendor_data field in the payload should contain the landlord's ID.
    """
    # Log the incoming webhook for debugging
    logger.info(f"Received Didit webhook for session {payload.session_id} with status: {payload.status}")
    
    try:
        # Process the webhook
        success, message = await KYCService.process_didit_webhook(payload)
        
        if success:
            return WebhookResponse(
                success=True,
                message=message,
                session_id=payload.session_id
            )
        else:
            # Return 400 for client errors (invalid data, landlord not found, etc.)
            logger.warning(f"Webhook processing failed: {message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error processing webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook"
        )


@router.get(
    "/status/{landlord_id}",
    summary="Get Landlord KYC Status",
    description="Get the current KYC verification status for a landlord"
)
async def get_kyc_status(landlord_id: str):
    """
    Get the current KYC verification status for a landlord.
    
    Args:
        landlord_id: The landlord's ID
        
    Returns:
        dict: Contains the KYC verification status
    """
    try:
        from beanie import PydanticObjectId
        landlord_object_id = PydanticObjectId(landlord_id)
        
        kyc_status = await KYCService.get_landlord_kyc_status(landlord_object_id)
        
        if kyc_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Landlord not found with ID: {landlord_id}"
            )
        
        return {
            "landlord_id": landlord_id,
            "kyc_verified": kyc_status,
            "status": "verified" if kyc_status else "not_verified"
        }
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid landlord ID format: {landlord_id}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting KYC status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
