from typing import List, Annotated, Optional
from pydantic import BaseModel, Field


class CloudinaryImageUploadResponse(BaseModel):
    """Response model for Cloudinary image upload.
    """
    
    api_key: Annotated[str, Field(description="API key used for authentication with Cloudinary")]
    asset_folder: Annotated[str, Field(description="Folder in Cloudinary where the asset is stored")]
    asset_id: Annotated[str, Field(description="Unique identifier for the asset in Cloudinary")]
    bytes: Annotated[int, Field(description="Size of the uploaded asset in bytes")]
    created_at: Annotated[str, Field(description="Timestamp when the asset was created")]
    display_name: Annotated[str, Field(description="Display name of the asset")]
    etag: Annotated[str, Field(description="ETag of the uploaded asset")]
    format: Annotated[str, Field(description="File format of the uploaded asset")]
    height: Annotated[int, Field(description="Height of the uploaded image in pixels")]
    original_extension: Annotated[Optional[str], Field(description="Original file extension of the uploaded asset", default=None)]
    original_filename: Annotated[Optional[str], Field(description="Original file name of the uploaded asset", default=None)]
    placeholder: Annotated[bool, Field(description="Whether the asset is a placeholder")]
    public_id: Annotated[str, Field(description="Public ID of the uploaded asset")]
    resource_type: Annotated[str, Field(description="Resource type of the uploaded asset")]
    secure_url: Annotated[str, Field(description="Secure URL of the uploaded asset")]
    signature: Annotated[str, Field(description="Signature of the uploaded asset")]
    tags: Annotated[List[str], Field(description="Tags associated with the uploaded asset")]
    type: Annotated[str, Field(description="Type of the uploaded asset")]
    url: Annotated[str, Field(description="URL of the uploaded asset")]
    version: Annotated[int, Field(description="Version of the uploaded asset")]
    version_id: Annotated[str, Field(description="Version ID of the uploaded asset")]
    width: Annotated[int, Field(description="Width of the uploaded image in pixels")]