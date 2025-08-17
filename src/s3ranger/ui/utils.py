from collections import namedtuple
from urllib.parse import urlparse

import boto3


def build_s3_uri(bucket_name: str, object_key: str = "") -> str:
    """Build an S3 URI from bucket and object key."""
    if object_key:
        return f"s3://{bucket_name}/{object_key}"
    return f"s3://{bucket_name}"


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse an S3 URI into bucket name and object key.

    Args:
        s3_uri: S3 URI in format 's3://bucket/key' or 's3://bucket'

    Returns:
        Tuple of (bucket_name, object_key)
    """
    s3_loc_obj = namedtuple("s3_location", ["bucket", "file_key"])
    s3_res = urlparse(s3_uri)
    s3_loc = s3_loc_obj(s3_res.netloc, s3_res.path[1:])

    return s3_loc


def generate_item_id(prefix: str, identifier: str) -> str:
    """Generate a prefixed item ID.

    Args:
        prefix: The prefix to use (e.g., "bucket-", "object-")
        identifier: The unique identifier

    Returns:
        Prefixed item ID
    """
    return f"{prefix}{identifier}"


def extract_identifier_from_id(item_id: str, prefix: str) -> str | None:
    """Extract identifier from a prefixed item ID.

    Args:
        item_id: The prefixed item ID
        prefix: The expected prefix

    Returns:
        The identifier or None if prefix doesn't match
    """
    if item_id and item_id.startswith(prefix):
        return item_id[len(prefix) :]
    return None


def format_file_size(size: int) -> str:
    """Format file size in human-readable format.

    Args:
        size: File size in bytes

    Returns:
        Formatted size string (e.g., "1.5 MB", "250 KB")
    """
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_object_display_text(name: str, size: int = 0) -> str:
    """Format display text for an object with size.

    Args:
        name: Object name
        size: Object size in bytes

    Returns:
        Formatted display text
    """
    size_str = format_file_size(size)
    return f"{name} ({size_str})"


def format_folder_display_text(name: str) -> str:
    """Format display text for a folder.

    Args:
        name: Folder name

    Returns:
        Formatted display text with folder emoji
    """
    return f"📁 {name}"


def get_parent_path(path: str) -> str:
    """Get the parent path from a given path.

    Args:
        path: File or folder path

    Returns:
        Parent path or empty string if no parent
    """
    if "/" in path:
        return "/".join(path.split("/")[:-1])
    return ""


def get_current_aws_profile() -> str:
    """Get the current AWS profile name.

    Returns:
        The name of the current AWS profile
    """
    try:
        # Import here to avoid circular import
        from s3ranger.gateways.s3 import S3

        # If a profile was set via CLI, use that
        cli_profile = S3.get_profile_name()
        if cli_profile:
            return cli_profile

        # Otherwise, get the current session profile
        session = boto3.session.Session()
        profiles = session.available_profiles
        if profiles:
            # If a profile is set via environment or config, use that
            # Otherwise, return the first available profile
            current_profile = session.profile_name or profiles[0]
            return current_profile
        return "default"
    except Exception:
        return "default"


def get_current_endpoint_url() -> str | None:
    """Get the current S3 endpoint URL or None if using default AWS S3.

    Returns:
        The current S3 endpoint URL or None if using default AWS S3.
    """
    try:
        # Import here to avoid circular import
        from s3ranger.gateways.s3 import S3

        return S3.get_endpoint_url()
    except Exception:
        return None
