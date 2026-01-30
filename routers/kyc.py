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
    """Creates a new KYC verification session for the authenticated user.
    
    This endpoint initiates the KYC verification flow with Didit and returns
    the session details including the URL where the user can complete verification.
    """
    return await kyc_service.create_kyc_verification_session(current_user)


@router.post("/webhook")
async def handle_kyc_webhook(
    request: Request,
    kyc_service: Annotated[KycService, Depends(get_kyc_service)],
):
    """Handles incoming KYC webhook callbacks from Didit.
    
    This endpoint receives and processes KYC verification status updates
    from the Didit provider.
    """
    return await kyc_service.handle_kyc_webhook(request)
