"""Controller for the Didit KYC API"""

import os

import time

import hashlib
import hmac

from dotenv import load_dotenv

load_dotenv()

class KYCController:
    """Controller for handling KYC operations with the Didit KYC API."""

    def __init__(self):
        self.api_key = os.getenv("DIDIT_API_KEY")
        self.secret_key = os.getenv("DIDIT_WEBHOOK_SECRET_KEY")

    def create_kyc_verification_session(self):
        pass

    def retrieve_verification_session_results(self):
        pass

    def verify_kyc_webhook_signature(self, request_body: str, signature_header: str, timestamp_header: str) -> bool:
        """Verify the webhook signature from Didit KYC API."""
        
        # Check if timestamp is recent (within 5 minutes)
        timestamp = int(timestamp_header)
        current_time = int(time())
        
        if abs(current_time - timestamp) > 300:  # 5 minutes
            return False

        # Calculate expected signature
        expected_signature = hmac.new(
            self.secret_key.encode("utf-8"), request_body.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # Compare signatures using constant-time comparison
        return hmac.compare_digest(signature_header, expected_signature)
