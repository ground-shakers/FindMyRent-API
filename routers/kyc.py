from fastapi import APIRouter, Request, Security
from fastapi.responses import JSONResponse

from security.helpers import get_current_active_user

from controllers.kyc_controller import create_kyc_session, verify_kyc_webhook_signature

from models.users import LandLord

from schema.kyc import CreateKYCSessionResponse

from typing import Annotated

router = APIRouter(
    prefix="/api/v1/kyc",
    tags=["KYC"],
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
    
    return validated_response