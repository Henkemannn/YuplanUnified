"""ETag utilities for optimistic locking in menu operations."""
from __future__ import annotations

from datetime import datetime
from typing import Optional


def generate_menu_etag(menu_id: int, updated_at: datetime) -> str:
    """Generate ETag for a menu based on ID and updated timestamp.
    
    Args:
        menu_id: The menu ID
        updated_at: The menu's updated_at timestamp
        
    Returns:
        ETag string in format: W/"menu-{id}-{timestamp}"
    """
    # Use timestamp as integer milliseconds for consistency
    timestamp = int(updated_at.timestamp() * 1000)
    return f'W/"menu-{menu_id}-{timestamp}"'


def parse_etag(etag: Optional[str]) -> Optional[tuple[int, int]]:
    """Parse ETag to extract menu_id and timestamp.
    
    Args:
        etag: ETag string from If-Match header
        
    Returns:
        Tuple of (menu_id, timestamp) or None if invalid
    """
    if not etag:
        return None
    
    # Remove W/" prefix and " suffix
    etag = etag.strip()
    if etag.startswith('W/"') and etag.endswith('"'):
        etag = etag[3:-1]
    elif etag.startswith('"') and etag.endswith('"'):
        etag = etag[1:-1]
    
    # Parse menu-{id}-{timestamp}
    parts = etag.split('-')
    if len(parts) != 3 or parts[0] != 'menu':
        return None
    
    try:
        menu_id = int(parts[1])
        timestamp = int(parts[2])
        return (menu_id, timestamp)
    except ValueError:
        return None


def validate_etag(
    provided_etag: Optional[str],
    current_menu_id: int,
    current_updated_at: datetime
) -> tuple[bool, Optional[str]]:
    """Validate that provided ETag matches current menu state.
    
    Args:
        provided_etag: ETag from If-Match header
        current_menu_id: Current menu ID
        current_updated_at: Current menu updated_at timestamp
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not provided_etag:
        return False, "If-Match header required for this operation"
    
    parsed = parse_etag(provided_etag)
    if not parsed:
        return False, "Invalid ETag format"
    
    etag_menu_id, etag_timestamp = parsed
    
    if etag_menu_id != current_menu_id:
        return False, f"ETag menu ID mismatch (expected {current_menu_id}, got {etag_menu_id})"
    
    current_timestamp = int(current_updated_at.timestamp() * 1000)
    if etag_timestamp != current_timestamp:
        return False, (
            "Menu has been modified by another user. "
            "Please reload and try again."
        )
    
    return True, None
