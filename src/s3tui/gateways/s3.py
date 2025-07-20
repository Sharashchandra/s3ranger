import os
from collections import namedtuple
from functools import wraps
from urllib.parse import urlparse

import boto3
from awscli.clidriver import create_clidriver
from loguru import logger


class S3:
    @staticmethod
    def resolve_s3_location(s3_path):
        """Resolve S3 path to bucket and file_key.
        Args:
            s3_path (str): S3 file location (e.g., s3://<bucket_name>/<file_key>)
        Returns:
            namedtuple: Named tuple with bucket and file_key attributes.
        """
        s3_loc_obj = namedtuple("s3_location", ["bucket", "file_key"])
        s3_res = urlparse(s3_path)
        s3_loc = s3_loc_obj(s3_res.netloc, s3_res.path[1:])

        return s3_loc

    @staticmethod
    def get_client(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not kwargs.get("client"):
                # Create a new S3 client if not provided
                kwargs["client"] = boto3.client("s3")
            return func(*args, **kwargs)

        return wrapper

    @staticmethod
    def resolve_s3_uri(func):
        @wraps(func)
        def wrapper(*args, s3_uri: str = None, bucket_name: str = None, prefix: str = None, **kwargs):
            if not s3_uri and not bucket_name:
                raise ValueError("Either s3_uri or bucket and key must be provided")
            if s3_uri:
                bucket_name, prefix = S3.resolve_s3_location(s3_uri)
            return func(*args, bucket_name=bucket_name, prefix=prefix or "", **kwargs)

        return wrapper

    # -------------------------List------------------------- #

    @get_client
    @staticmethod
    def list_buckets(client: boto3.client, *, prefix: str = None, limit: int = 100) -> list[dict]:
        """List all S3 buckets."""
        logger.info(f"Listing S3 buckets with prefix '{prefix or ''}'")
        response = client.list_buckets(MaxBuckets=limit, Prefix=prefix or "")

        return response.get("Buckets", [])

    @get_client
    @resolve_s3_uri
    @staticmethod
    def list_objects(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str = None,
    ) -> list[dict]:
        """List objects in a bucket with optional prefix."""
        paginator = client.get_paginator("list_objects_v2")
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix or "")

        logger.info(f"Listing objects in bucket '{bucket_name}' with prefix '{prefix}'")
        objects = []
        for response in response_iterator:
            if "Contents" in response:
                objects.extend(response["Contents"])

        return objects

    # -------------------------Upload------------------------- #

    @get_client
    @resolve_s3_uri
    def upload_file(self, client: boto3.client, *, local_file_path: str, bucket_name: str, prefix: str = None) -> None:
        if not prefix or prefix.endswith("/"):
            key = f"{prefix}{os.path.basename(local_file_path)}"

        logger.info(f"Uploading file '{local_file_path}' to bucket '{bucket_name}' with key '{key}'")
        client.upload_file(local_file_path, bucket_name, key)

    @resolve_s3_uri
    @staticmethod
    def upload_directory(*, local_dir_path: str, bucket_name: str, prefix: str = None) -> None:
        """Upload a directory to S3."""
        if not os.path.isdir(local_dir_path):
            raise ValueError(f"Local path '{local_dir_path}' is not a directory")
        logger.info(f"Uploading folder: {local_dir_path} to s3://{bucket_name}/{prefix}")

        cli_driver = create_clidriver()
        cli_driver.main(["s3", "cp", local_dir_path, f"s3://{bucket_name}/{prefix or ''}", "--recursive"])

    @get_client
    @resolve_s3_uri
    @staticmethod
    def upload_directory_via_boto3(
        client: boto3.client,
        *,
        local_dir_path: str,
        bucket_name: str,
        prefix: str = None,
    ) -> None:
        """Upload a directory to S3."""
        if not os.path.isdir(local_dir_path):
            raise ValueError(f"Local path '{local_dir_path}' is not a directory")

        for root, _, files in os.walk(local_dir_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, local_dir_path)
                key = f"{prefix}{relative_path.replace(os.sep, '/')}"

                logger.info(f"Uploading file '{local_file_path}' to bucket '{bucket_name}' with key '{key}'")
                client.upload_file(local_file_path, bucket_name, key)

    # -------------------------Download------------------------- #
    @get_client
    @resolve_s3_uri
    @staticmethod
    def download_file(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str,
        local_dir_path: str,
    ) -> None:
        """Download a file from S3."""
        local_file_path = os.path.join(local_dir_path, os.path.basename(prefix))
        if not os.path.exists(local_dir_path):
            os.makedirs(local_dir_path)

        logger.info(f"Downloading file from s3://{bucket_name}/{prefix} to {local_file_path}")
        client.download_file(bucket_name, prefix, local_file_path)

    @resolve_s3_uri
    @staticmethod
    def download_directory(*, bucket_name: str, prefix: str = None, local_dir_path: str = None) -> None:
        """Download a directory from S3."""
        logger.info(f"Downloading directory from s3://{bucket_name}/{prefix} to {local_dir_path}")
        if not local_dir_path:
            local_dir_path = os.path.join(os.getcwd(), prefix or "")

        cli_driver = create_clidriver()
        cli_driver.main(["s3", "cp", f"s3://{bucket_name}/{prefix or ''}", local_dir_path, "--recursive"])

    @get_client
    @resolve_s3_uri
    @staticmethod
    def download_directory_via_boto3(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str = None,
        local_dir_path: str = ".",
    ) -> None:
        """Download a directory from S3."""
        paginator = client.get_paginator("list_objects_v2")
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix or "")

        if not os.path.exists(local_dir_path):
            os.makedirs(local_dir_path)

        logger.info(f"Downloading directory from s3://{bucket_name}/{prefix} to {local_dir_path}")
        for response in response_iterator:
            if "Contents" in response:
                for obj in response["Contents"]:
                    file_key = obj["Key"]
                    local_file_path = os.path.join(local_dir_path, os.path.relpath(file_key, prefix or ""))
                    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                    client.download_file(bucket_name, file_key, local_file_path)

    # -------------------------Delete------------------------- #
    @get_client
    @resolve_s3_uri
    @staticmethod
    def delete_file(
        client: boto3.client,
        *,
        bucket_name: str,
        file_key: str,
    ) -> None:
        """Delete a file from S3."""
        logger.info(f"Deleting file s3://{bucket_name}/{file_key}")
        client.delete_object(Bucket=bucket_name, Key=file_key)

    @resolve_s3_uri
    @staticmethod
    def delete_directory(*, bucket_name: str, prefix: str = None) -> None:
        """Delete a directory from S3."""
        logger.info(f"Deleting directory s3://{bucket_name}/{prefix}")
        cli_driver = create_clidriver()
        cli_driver.main(["s3", "rm", f"s3://{bucket_name}/{prefix or ''}", "--recursive"])

    @get_client
    @resolve_s3_uri
    @staticmethod
    def delete_directory_via_boto3(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str = None,
    ) -> None:
        """Delete a directory from S3."""
        paginator = client.get_paginator("list_objects_v2")
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix or "")

        logger.info(f"Deleting directory s3://{bucket_name}/{prefix}")
        for response in response_iterator:
            if "Contents" in response:
                objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]
                client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects_to_delete})
