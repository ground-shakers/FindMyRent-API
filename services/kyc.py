
from utils.logger import logger

from typing import Optional
from beanie import PydanticObjectId

from models.users import LandLord
from schema.kyc import DiditWebhookPayload


class KYCService:
    """Service for handling KYC verification operations."""

    @staticmethod
    async def process_didit_webhook(payload: DiditWebhookPayload) -> tuple[bool, str]:
        """
        Process Didit webhook payload and update landlord KYC status.
        
        Args:
            payload: The Didit webhook payload
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Only process status updates
            if payload.webhook_type != "status.updated":
                return False, f"Unsupported webhook type: {payload.webhook_type}"
            
            # Extract vendor_data which should contain the landlord ID
            if not payload.vendor_data:
                logger.warning(f"No vendor_data found in webhook payload for session {payload.session_id}")
                return False, "No vendor_data (landlord ID) found in payload"
            
            # Find the landlord by ID
            try:
                landlord_id = PydanticObjectId(payload.vendor_data)
                landlord = await LandLord.get(landlord_id)
            except Exception as e:
                logger.error(f"Invalid landlord ID in vendor_data: {payload.vendor_data}. Error: {e}")
                return False, f"Invalid landlord ID: {payload.vendor_data}"
            
            if not landlord:
                logger.warning(f"Landlord not found with ID: {payload.vendor_data}")
                return False, f"Landlord not found with ID: {payload.vendor_data}"
            
            # Process based on status
            if payload.status == "Approved":
                # Update KYC status to verified
                landlord.kyc_verified = True
                await landlord.save()
                
                logger.info(f"KYC approved for landlord {landlord_id} (session: {payload.session_id})")
                return True, f"KYC status updated to verified for landlord {landlord_id}"
                
            elif payload.status == "Declined":
                # Update KYC status to not verified
                landlord.kyc_verified = False
                await landlord.save()
                
                # Log the reason if available in decision reviews
                reason = "No reason provided"
                if payload.decision and payload.decision.reviews:
                    latest_review = payload.decision.reviews[-1]  # Get the latest review
                    reason = latest_review.comment
                
                logger.info(f"KYC declined for landlord {landlord_id} (session: {payload.session_id}). Reason: {reason}")
                return True, f"KYC status updated to not verified for landlord {landlord_id}. Reason: {reason}"
                
            else:
                # For other statuses like "In Progress", "In Review", etc., we don't update the KYC status
                logger.info(f"KYC status '{payload.status}' for landlord {landlord_id} (session: {payload.session_id}) - no action taken")
                return True, f"KYC status '{payload.status}' received - no action required"
                
        except Exception as e:
            logger.error(f"Error processing Didit webhook: {e}")
            return False, f"Internal error processing webhook: {str(e)}"

    @staticmethod
    async def get_landlord_kyc_status(landlord_id: PydanticObjectId) -> Optional[bool]:
        """
        Get the current KYC verification status for a landlord.
        
        Args:
            landlord_id: The landlord's ID
            
        Returns:
            bool or None: KYC status if landlord exists, None otherwise
        """
        try:
            landlord = await LandLord.get(landlord_id)
            return landlord.kyc_verified if landlord else None
        except Exception as e:
            logger.error(f"Error fetching landlord KYC status: {e}")
            return None