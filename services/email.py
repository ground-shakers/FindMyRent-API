"""Contains all the code related to the emailing service"""

import smtplib

import logfire

from typing import Optional, List

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from models.helpers import ContentType


class EmailService:
    """Service for handling email operations."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email

    def send_email(
        self,
        to: str,
        subject: str,
        content: str,
        content_type: ContentType = ContentType.HTML,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """Send an email.

        Args:
            to (str): Recipient email address
            subject (str): Subject of the email
            content (str): Content of the email
            content_type (ContentType, optional): ContentType of the email content. Defaults to ContentType.HTML.
            cc (Optional[List[str]], optional): List of email addresses to be carbon copied into the email. Defaults to None.
            bcc (Optional[List[str]], optional): List of email addresses to be blind carbon copied into the email. Defaults to None.

        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """
        try:
            if content_type == ContentType.MULTIPART:
                msg = self._create_multipart_message(to, subject, content, cc, bcc)
            else:
                msg = self._create_simple_message(
                    to, subject, content, content_type, cc, bcc
                )

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)

            logfire.info(f"Email sent successfully to {to}")
            return True

        except Exception as e:
            logfire.error(f"Failed to send email to {to}: {str(e)}")
            return False

    def _create_simple_message(
        self,
        to: str,
        subject: str,
        content: str,
        content_type: ContentType,
        cc: Optional[List[str]],
        bcc: Optional[List[str]],
    ) -> MIMEText:
        """Create a simple email message (plain or HTML).

        Args:
            to (str): Recipient email address
            subject (str): Subject of the email
            content (str): Content of the email
            content_type (ContentType): ContentType of the email
            cc (Optional[List[str]]): List of CC recipients
            bcc (Optional[List[str]]): List of BCC recipients

        Returns:
            MIMEText: _description_
        """
        mime_type = "plain" if content_type == ContentType.PLAIN else "html"
        msg = MIMEText(content, mime_type)
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to

        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        return msg

    def _create_multipart_message(
        self,
        to: str,
        subject: str,
        content: str,
        cc: Optional[List[str]],
        bcc: Optional[List[str]],
    ) -> MIMEMultipart:
        """Create a multipart email message (both plain and HTML).

        Args:
            to (str): Recipient email address
            subject (str): Subject of the email
            content (str): Content of the email
            cc (Optional[List[str]]): List of CC recipients
            bcc (Optional[List[str]]): List of BCC recipients

        Returns:
            MIMEMultipart: The created multipart email message.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = to

        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        # Add HTML part
        html_part = MIMEText(content, "html")
        msg.attach(html_part)

        return msg
