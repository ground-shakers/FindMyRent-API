"""
KYC router for handling Know Your Customer verification endpoints.
"""

import logfire

from fastapi import APIRouter, Request, Security, Depends

from security.helpers import get_current_active_user

from models.users import LandLord

from schema.kyc import CreateKYCSessionResponse

from services.kyc_service import get_kyc_service, KycService

from typing import Annotated


router = APIRouter(
    prefix="/api/v1/kyc",
    tags=["KYC Verification"],
)


@router.post("/session", response_model=CreateKYCSessionResponse)
async def create_kyc_verification_session(
    current_user: Annotated[
        LandLord, Security(get_current_active_user, scopes=["me"])
    ],
    kyc_service: Annotated[KycService, Depends(get_kyc_service)],
):
    """Create a new KYC verification session for the authenticated user.
    
    This endpoint initiates the Know Your Customer (KYC) verification flow
    using the Didit identity verification service. Users must complete KYC
    verification to list properties on the platform.
    
    ## Verification Flow
    1. Call this endpoint to create a verification session
    2. Redirect user to the `verification_url` in the response
    3. User completes identity verification on Didit's platform
    4. Didit sends webhook notification to `/api/v1/kyc/webhook`
    5. User's KYC status is updated in the database
    
    ## Request Headers
    | Header | Required | Description |
    |--------|----------|-------------|
    | Authorization | Yes | Bearer token: `Bearer <access_token>` |
    
    ## Success Response (200 OK)
    ```json
    {
        "session_id": "sess_abc123xyz...",
        "verification_url": "https://verify.didit.com/session/abc123...",
        "expires_at": "2024-01-31T22:00:00Z"
    }
    ```
    
    ## Error Responses
    | Status | Description | Response Body |
    |--------|-------------|---------------|
    | 401 | Invalid/missing token | `{"detail": "Not authenticated"}` |
    | 403 | Insufficient permissions | `{"detail": "Not enough permissions"}` |
    | 409 | Already verified | `{"detail": "User is already KYC verified"}` |
    | 500 | External service error | `{"detail": "Failed to create verification session"}` |
    | 503 | Service unavailable | `{"detail": "KYC service temporarily unavailable"}` |
    
    ## Notes
    - Sessions expire after a set time (typically 30 minutes)
    - Users can create new sessions if previous ones expire
    - KYC verification is required before creating property listings
    """
    return await kyc_service.create_kyc_verification_session(current_user)


@router.post("/webhook")
async def handle_kyc_webhook(
    request: Request,
    kyc_service: Annotated[KycService, Depends(get_kyc_service)],
):
    """Handle incoming KYC webhook callbacks from Didit.
    
    This webhook endpoint receives and processes KYC verification status updates
    from the Didit identity verification provider. It is called automatically
    when a user completes (or fails) the verification process.
    
    ## Webhook Security
    - Validates webhook signature from Didit
    - Rejects requests with invalid or missing signatures
    - Only processes webhooks from verified Didit IP addresses
    
    ## Expected Webhook Payload
    ```json
    {
        "event": "verification.completed",
        "session_id": "sess_abc123xyz...",
        "status": "approved",
        "user_id": "user_id_from_metadata",
        "verification": {
            "document_type": "passport",
            "country": "ZA",
            "verified_at": "2024-01-31T20:30:00Z"
        }
    }
    ```
    
    ## Verification Statuses
    | Status | Description | User Action |
    |--------|-------------|-------------|
    | `approved` | Identity verified successfully | User can now list properties |
    | `declined` | Verification failed | User should retry with valid documents |
    | `pending` | Requires manual review | Wait for Didit to complete review |
    | `expired` | Session expired | User should start a new session |
    
    ## Response
    | Status | Description |
    |--------|-------------|
    | 200 | Webhook processed successfully |
    | 400 | Invalid webhook payload |
    | 401 | Invalid webhook signature |
    | 500 | Internal processing error |
    
    ## Notes
    - This endpoint is called by Didit, not by the client application
    - Webhook signature verification is critical for security
    - User's KYC status and permissions are updated automatically
    """
    return await kyc_service.handle_kyc_webhook(request)

