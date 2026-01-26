"""Service for handling email templates."""

import logfire

from typing import Dict, Any, Literal

from pathlib import Path

from functools import lru_cache

# Template directory
TEMPLATES_DIR = Path("templates/emails")


class TemplateService:
    """Service for handling email templates."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def _load_template(self, template_name: str) -> str:
        """Load email template from file.

        Args:
            template_name (str): The name of the template to load (without extension).

        Raises:
            FileNotFoundError: If the template file is not found.

        Returns:
            str: The content of the email template.
        """
        template_path = self.templates_dir / f"{template_name}.html"

        if not template_path.exists():
            raise FileNotFoundError(f"Template '{template_name}' not found")

        with open(template_path, "r", encoding="utf-8") as file:
            return file.read()

    def _render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """Render email template with data.

        Args:
            template_name (str): The name of the template to render (without extension).
            data (Dict[str, Any]): The data to use for rendering the template.

        Returns:
            str: The rendered email template.
        """
        template = self._load_template(template_name)

        # Simple placeholder replacement
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            template = template.replace(placeholder, str(value))

        return template

    def render_verification_email(self, code: str, email: str) -> str:
        """Render verification email template.

        Args:
            code (str): The verification code.
            email (str): The email address of the user.

        Returns:
            str: The rendered verification email template.
        """
        return self._render_template(
            "verification_email", {"CODE": code, "EMAIL": email}
        )

    def render_welcome_email(self, name: str, email: str) -> str:
        """Render welcome email template.

        Args:
            name (str): The name of the user.
            email (str): The email address of the user.

        Returns:
            str: The rendered welcome email template.
        """
        return self._render_template("welcome_email", {"NAME": name, "EMAIL": email})

    def render_password_reset_email(self, reset_link: str, email: str) -> str:
        """Render password reset email template.

        Args:
            reset_link (str): The password reset link.
            email (str): The email address of the user.

        Returns:
            str: The rendered password reset email template.
        """
        return self._render_template(
            "password_reset_email", {"RESET_LINK": reset_link, "EMAIL": email}
        )

    def render_property_verification_update_email(
        self,
        landlord_name: str,
        property_address: str,
        property_city: str,
        property_state: str,
        property_type: str,
        bedrooms: int,
        price: float,
        listing_id: str,
        verification_status: Literal["accepted", "rejected"],
    ) -> str:
        """Render property verified email template.

        Args:
            landlord_name (str): The name of the landlord.
            property_address (str): The street address of the property.
            property_city (str): The city where the property is located.
            property_state (str): The state where the property is located.
            property_type (str): The type of property (e.g., single, shared, studio).
            bedrooms (int): The number of bedrooms.
            price (float): The monthly rental price.
            listing_id (str): The unique identifier of the listing.
            listing_url (str): The URL to view the listing.

        Returns:
            str: The rendered property verified email template.
        """
        return self._render_template(
            f"property_{verification_status}",
            {
                "LANDLORD_NAME": landlord_name,
                "PROPERTY_ADDRESS": property_address,
                "PROPERTY_CITY": property_city,
                "PROPERTY_STATE": property_state,
                "PROPERTY_TYPE": property_type,
                "BEDROOMS": str(bedrooms),
                "PRICE": f"{price:.2f}",
                "LISTING_ID": listing_id,
            },
        )

    def render_property_needs_verification_email(
        self,
        listing_id: str,
        property_address: str,
        property_city: str,
        property_state: str,
        property_type: str,
        bedrooms: int,
        price: float,
        submission_date: str,
        landlord_name: str,
        landlord_email: str,
        landlord_id: str,
        kyc_status: str,
        image_count: int,
        proof_count: int,
    ) -> str:
        """Render property needs verification email template for support/admin team.

        Args:
            listing_id (str): The unique identifier of the listing.
            property_address (str): The street address of the property.
            property_city (str): The city where the property is located.
            property_state (str): The state where the property is located.
            property_type (str): The type of property (e.g., single, shared, studio).
            bedrooms (int): The number of bedrooms.
            price (float): The monthly rental price.
            submission_date (str): The date and time when the listing was submitted.
            landlord_name (str): The full name of the landlord.
            landlord_email (str): The email address of the landlord.
            landlord_id (str): The unique identifier of the landlord.
            kyc_status (str): The KYC verification status of the landlord.
            image_count (int): The number of property images uploaded.
            proof_count (int): The number of proof of ownership documents uploaded.
            admin_panel_url (str): The URL to review the listing in the admin panel.

        Returns:
            str: The rendered property needs verification email template.
        """
        return self._render_template(
            "property_needs_verification",
            {
                "LISTING_ID": listing_id,
                "PROPERTY_ADDRESS": property_address,
                "PROPERTY_CITY": property_city,
                "PROPERTY_STATE": property_state,
                "PROPERTY_TYPE": property_type,
                "BEDROOMS": str(bedrooms),
                "PRICE": f"{price:.2f}",
                "SUBMISSION_DATE": submission_date,
                "LANDLORD_NAME": landlord_name,
                "LANDLORD_EMAIL": landlord_email,
                "LANDLORD_ID": landlord_id,
                "KYC_STATUS": kyc_status,
                "IMAGE_COUNT": str(image_count),
                "PROOF_COUNT": str(proof_count),
            },
        )

    def render_listing_pending_verification_email(
        self,
        landlord_name: str,
        property_address: str,
        property_city: str,
        property_state: str,
        property_type: str,
        bedrooms: int,
        price: float,
        listing_id: str,
        submission_date: str,
    ) -> str:
        """Render email template to notify landlord that their new listing is pending verification.

        Args:
            landlord_name (str): The name of the landlord.
            property_address (str): The street address of the property.
            property_city (str): The city where the property is located.
            property_state (str): The state where the property is located.
            property_type (str): The type of property (e.g., single, shared, studio).
            bedrooms (int): The number of bedrooms.
            price (float): The monthly rental price.
            listing_id (str): The unique identifier of the listing.
            submission_date (str): The date and time when the listing was submitted.

        Returns:
            str: The rendered listing pending verification email template.
        """
        return self._render_template(
            "listing_pending_verification",
            {
                "LANDLORD_NAME": landlord_name,
                "PROPERTY_ADDRESS": property_address,
                "PROPERTY_CITY": property_city,
                "PROPERTY_STATE": property_state,
                "PROPERTY_TYPE": property_type,
                "BEDROOMS": str(bedrooms),
                "PRICE": f"{price:.2f}",
                "LISTING_ID": listing_id,
                "SUBMISSION_DATE": submission_date,
            },
        )

    def render_listing_requires_reverification_email(
        self,
        landlord_name: str,
        property_address: str,
        property_city: str,
        property_state: str,
        property_type: str,
        bedrooms: int,
        price: float,
        listing_id: str,
        update_date: str,
    ) -> str:
        """Render email template to notify landlord that their listing update requires re-verification.

        Args:
            landlord_name (str): The name of the landlord.
            property_address (str): The street address of the property.
            property_city (str): The city where the property is located.
            property_state (str): The state where the property is located.
            property_type (str): The type of property (e.g., single, shared, studio).
            bedrooms (int): The number of bedrooms.
            price (float): The monthly rental price.
            listing_id (str): The unique identifier of the listing.
            update_date (str): The date and time when the listing was updated.

        Returns:
            str: The rendered listing requires re-verification email template.
        """
        return self._render_template(
            "listing_requires_reverification",
            {
                "LANDLORD_NAME": landlord_name,
                "PROPERTY_ADDRESS": property_address,
                "PROPERTY_CITY": property_city,
                "PROPERTY_STATE": property_state,
                "PROPERTY_TYPE": property_type,
                "BEDROOMS": str(bedrooms),
                "PRICE": f"{price:.2f}",
                "LISTING_ID": listing_id,
                "UPDATE_DATE": update_date,
            },
        )

    def render_property_verified_email(
        self,
        landlord_name: str,
        property_address: str,
        property_city: str,
        property_state: str,
        property_type: str,
        bedrooms: int,
        price: float,
        listing_id: str,
        listing_url: str,
    ) -> str:
        """Render property verified email template to notify landlord of successful verification.

        Args:
            landlord_name (str): The name of the landlord.
            property_address (str): The street address of the property.
            property_city (str): The city where the property is located.
            property_state (str): The state where the property is located.
            property_type (str): The type of property (e.g., single, shared, studio).
            bedrooms (int): The number of bedrooms.
            price (float): The monthly rental price.
            listing_id (str): The unique identifier of the listing.
            listing_url (str): The URL to view the live listing.

        Returns:
            str: The rendered property verified email template.
        """
        return self._render_template(
            "property_verified",
            {
                "LANDLORD_NAME": landlord_name,
                "PROPERTY_ADDRESS": property_address,
                "PROPERTY_CITY": property_city,
                "PROPERTY_STATE": property_state,
                "PROPERTY_TYPE": property_type,
                "BEDROOMS": str(bedrooms),
                "PRICE": f"{price:.2f}",
                "LISTING_ID": listing_id,
                "LISTING_URL": listing_url,
            },
        )


@lru_cache()
def get_template_service() -> TemplateService:
    """Get an instance of the TemplateService.

    Returns:
        TemplateService: An instance of the TemplateService.
    """
    return TemplateService(templates_dir=TEMPLATES_DIR)
