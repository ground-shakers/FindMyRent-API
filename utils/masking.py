"""
Utility functions for masking sensitive data based on user premium status.
"""

from typing import Dict, Any, List


def mask_string(value: str, visible_chars: int = 3) -> str:
    """Mask a string, showing only first N characters.
    
    Args:
        value: The string to mask
        visible_chars: Number of characters to show
        
    Returns:
        Masked string with asterisks
    """
    if not value or len(value) <= visible_chars:
        return "*" * len(value) if value else "***"
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


def mask_email(email: str) -> str:
    """Mask an email address for non-premium users.
    
    Args:
        email: The email to mask
        
    Returns:
        Masked email (e.g., "joh***@***.com")
    """
    if not email or "@" not in email:
        return "***@***.***"
    
    local, domain = email.rsplit("@", 1)
    domain_parts = domain.rsplit(".", 1)
    
    masked_local = mask_string(local, 3)
    masked_domain = "***." + domain_parts[-1] if len(domain_parts) > 1 else "***"
    
    return f"{masked_local}@{masked_domain}"


def mask_phone(phone: str) -> str:
    """Mask a phone number for non-premium users.
    
    Args:
        phone: The phone number to mask
        
    Returns:
        Masked phone (e.g., "+264***")
    """
    if not phone:
        return "***"
    # Show country code/first few digits, mask the rest
    visible = min(4, len(phone) // 3)
    return phone[:visible] + "*" * (len(phone) - visible)


def mask_landlord_details(listing_data: Dict[str, Any], is_premium: bool) -> Dict[str, Any]:
    """Mask landlord contact details in a listing based on premium status.
    
    For non-premium users, masks:
    - landlord.email
    - landlord.first_name (partial)
    - landlord.last_name (partial)
    
    Args:
        listing_data: The listing dictionary (already serialized)
        is_premium: Whether the requesting user has premium
        
    Returns:
        Listing with masked or full landlord details
    """
    if is_premium:
        return listing_data
    
    # If landlord field exists and is not excluded
    if "landlord" in listing_data and listing_data["landlord"]:
        landlord = listing_data["landlord"]
        
        if "email" in landlord:
            landlord["email"] = mask_email(landlord["email"])
        
        if "first_name" in landlord:
            landlord["first_name"] = mask_string(landlord["first_name"], 2)
        if "firstName" in landlord:
            landlord["firstName"] = mask_string(landlord["firstName"], 2)
            
        if "last_name" in landlord:
            landlord["last_name"] = mask_string(landlord["last_name"], 1)
        if "lastName" in landlord:
            landlord["lastName"] = mask_string(landlord["lastName"], 1)
        
        # Add flag indicating details are masked
        landlord["masked"] = True
    
    # Add premium required notice
    listing_data["premium_required_for_contact"] = True
    
    return listing_data


def mask_listings_for_user(listings: List[Dict[str, Any]], is_premium: bool) -> List[Dict[str, Any]]:
    """Apply masking to a list of listings based on user premium status.
    
    Args:
        listings: List of serialized listing dictionaries
        is_premium: Whether the requesting user has premium
        
    Returns:
        List of listings with appropriate masking applied
    """
    return [mask_landlord_details(listing, is_premium) for listing in listings]
