from s3tui.gateways.s3 import S3


class S3ListService:
    @classmethod
    def list_s3_buckets(cls, prefix: str = None, limit: int = 100) -> list[dict]:
        """List all S3 buckets with an optional prefix."""

        return S3.list_buckets(prefix=prefix, limit=limit)

    @classmethod
    def list_s3_objects(cls, bucket_name: str, prefix: str = None) -> list[dict]:
        """List objects in a specific S3 bucket with an optional prefix."""

        return S3.list_objects(bucket_name=bucket_name, prefix=prefix)
