"""Describes the structure of the send email request."""

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any

from models.helpers import ContentType


class SendEmailRequest(BaseModel):
    to: EmailStr
    subject: str
    content: str
    content_type: ContentType = ContentType.HTML
    template_name: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None