"""Service for handling email templates."""

import logfire

from typing import Dict, Any

from pathlib import Path


class TemplateService:
    """Service for handling email templates."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir

    def load_template(self, template_name: str) -> str:
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

    def render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        """Render email template with data.

        Args:
            template_name (str): The name of the template to render (without extension).
            data (Dict[str, Any]): The data to use for rendering the template.

        Returns:
            str: The rendered email template.
        """
        template = self.load_template(template_name)

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
        return self.render_template(
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
        return self.render_template("welcome_email", {"NAME": name, "EMAIL": email})

    def render_password_reset_email(self, reset_link: str, email: str) -> str:
        """Render password reset email template.

        Args:
            reset_link (str): The password reset link.
            email (str): The email address of the user.

        Returns:
            str: The rendered password reset email template.
        """
        return self.render_template(
            "password_reset_email", {"RESET_LINK": reset_link, "EMAIL": email}
        )
