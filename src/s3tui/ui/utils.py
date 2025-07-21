from collections import namedtuple
from urllib.parse import urlparse


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
