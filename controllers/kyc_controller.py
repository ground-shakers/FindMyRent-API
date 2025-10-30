"""Controller for the Didit KYC API"""

import os

import time

import hashlib
import hmac

from httpx import AsyncClient

from models.users import LandLord

from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("DIDIT_API_KEY")
SECRET_KEY = os.getenv("DIDIT_WEBHOOK_SECRET_KEY")
WORKFLOW_ID = os.getenv("DIDIT_WORKFLOW_ID")
BASE_URL = "https://verification.didit.me/v2"
HEADERS = {
    "x-api-key": API_KEY,
}

async def create_kyc_session(user: LandLord) -> dict | None:
    """Create a KYC verification session for a user.

    Args:
        user (LandLord): The user for whom to create the KYC session.

    Returns:
    dict | None: The created KYC session data or None if failed.
    """

    try:
        body = {
            "workflow_id": WORKFLOW_ID,
            "vendor_data": user.id,
            "expected_details": {
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            "contact_details": {
                "email": user.email,
                "send_notification_emails": True,
                "phone": f"+{user.phone_number}",
            },
        }

        async with AsyncClient() as client:

            response = await client.post(
                f"{BASE_URL}/session/",
                headers=HEADERS,
                json=body
            )

            if response.status_code == 201:
                session_data = response.json()
                return session_data
            else:
                print(f"Failed to create KYC session: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        print(f"Error creating KYC session: {e}")
        return None

async def verify_kyc_webhook_signature(request_body: str, signature_header: str, timestamp_header: str) -> bool:
    """Verify the webhook signature from Didit KYC API."""

    # Check if timestamp is recent (within 5 minutes)
    timestamp = int(timestamp_header)
    current_time = int(time())

    if abs(current_time - timestamp) > 300:  # 5 minutes
        return False

    # Calculate expected signature
    expected_signature = hmac.new(
        SECRET_KEY.encode("utf-8"), request_body.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    # Compare signatures using constant-time comparison
    return hmac.compare_digest(signature_header, expected_signature)