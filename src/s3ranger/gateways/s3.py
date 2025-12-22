import os
import subprocess
from collections import namedtuple
from functools import wraps
from urllib.parse import urlparse

import boto3


class S3:
    # Class-level variables to store the endpoint URL, region, profile, and credentials
    _endpoint_url = None
    _region_name = None
    _profile_name = None
    _aws_access_key_id = None
    _aws_secret_access_key = None
    _aws_session_token = None

    @classmethod
    def set_endpoint_url(cls, endpoint_url: str | None = None) -> None:
        """Set the S3 endpoint URL for all S3 operations.

        Args:
            endpoint_url: The S3 endpoint URL. Set to None to use default AWS S3.
        """
        cls._endpoint_url = endpoint_url

    @classmethod
    def set_region_name(cls, region_name: str | None = None) -> None:
        """Set the AWS region name for all S3 operations.

        Args:
            region_name: The AWS region name. Set to None to use default.
        """
        cls._region_name = region_name

    @classmethod
    def set_profile_name(cls, profile_name: str | None = None) -> None:
        """Set the AWS profile name for all S3 operations.

        Args:
            profile_name: The AWS profile name. Set to None to use default.
        """
        cls._profile_name = profile_name

    @classmethod
    def get_profile_name(cls) -> str | None:
        """Get the current AWS profile name.

        Returns:
            The AWS profile name or None if using default.
        """
        return cls._profile_name

    @classmethod
    def get_endpoint_url(cls) -> str | None:
        """Get the current S3 endpoint URL.

        Returns:
            The S3 endpoint URL or None if using default AWS S3.
        """
        return cls._endpoint_url

    @classmethod
    def set_credentials(
        cls,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
    ) -> None:
        """Set the AWS credentials for all S3 operations.

        Args:
            aws_access_key_id: The AWS access key ID.
            aws_secret_access_key: The AWS secret access key.
            aws_session_token: The AWS session token (optional, for temporary credentials).
        """
        cls._aws_access_key_id = aws_access_key_id
        cls._aws_secret_access_key = aws_secret_access_key
        cls._aws_session_token = aws_session_token

    @classmethod
    def is_using_cli_credentials(cls) -> bool:
        """Check if CLI credentials are being used instead of a profile.

        Returns:
            True if using explicit CLI credentials, False otherwise.
        """
        return bool(cls._aws_access_key_id and cls._aws_secret_access_key)

    @classmethod
    def _run_aws_cli_command(cls, command_args: list[str]) -> str:
        """Run an AWS CLI command with proper error handling.

        Args:
            command_args: List of command arguments (without 'aws' prefix)

        Returns:
            The command output as a string

        Raises:
            RuntimeError: If the command fails with non-zero exit code
        """
        # Build the environment variables
        env = os.environ.copy()

        # Set credentials in environment if provided and not using profile
        if cls._aws_access_key_id and not cls._profile_name:
            env["AWS_ACCESS_KEY_ID"] = cls._aws_access_key_id
        if cls._aws_secret_access_key and not cls._profile_name:
            env["AWS_SECRET_ACCESS_KEY"] = cls._aws_secret_access_key
        if cls._aws_session_token and not cls._profile_name:
            env["AWS_SESSION_TOKEN"] = cls._aws_session_token

        # Build the full command
        command = ["aws", *command_args]

        # Add endpoint URL if specified
        if cls._endpoint_url:
            command.extend(["--endpoint-url", cls._endpoint_url])

        # Add region if specified
        if cls._region_name:
            command.extend(["--region", cls._region_name])

        # Add profile if specified
        if cls._profile_name:
            command.extend(["--profile", cls._profile_name])

        try:
            result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e.stderr)

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
                # Environment variables that boto3 reads for credentials
                # We temporarily unset these to prevent boto3 from auto-reading them
                aws_env_vars = [
                    "AWS_ACCESS_KEY_ID",
                    "AWS_SECRET_ACCESS_KEY",
                    "AWS_SESSION_TOKEN",
                    "AWS_PROFILE",
                    "AWS_DEFAULT_PROFILE",
                ]

                # Save and unset AWS env vars
                saved_env = {}
                for var in aws_env_vars:
                    if var in os.environ:
                        saved_env[var] = os.environ.pop(var)

                try:
                    # Create a new S3 client if not provided
                    client_kwargs = {"service_name": "s3"}
                    if S3._endpoint_url:
                        client_kwargs["endpoint_url"] = S3._endpoint_url
                    if S3._region_name:
                        client_kwargs["region_name"] = S3._region_name

                    # Create session with credentials following boto3 precedence order:
                    # 1. Explicit credentials (highest priority)
                    # 2. Profile name
                    # 3. Environment variables (handled automatically by boto3)
                    # 4. Shared credential files (handled automatically by boto3)

                    session_kwargs = {}

                    # Check if explicit credentials are provided (highest priority)
                    if S3._aws_access_key_id and S3._aws_secret_access_key:
                        session_kwargs["aws_access_key_id"] = S3._aws_access_key_id
                        session_kwargs["aws_secret_access_key"] = S3._aws_secret_access_key
                        if S3._aws_session_token:
                            session_kwargs["aws_session_token"] = S3._aws_session_token
                    # Otherwise, use profile if specified
                    elif S3._profile_name:
                        session_kwargs["profile_name"] = S3._profile_name

                    # If region is specified, add it to session (this can also be set via environment/config)
                    if S3._region_name:
                        session_kwargs["region_name"] = S3._region_name

                    session = boto3.Session(**session_kwargs)
                    kwargs["client"] = session.client(**client_kwargs)
                finally:
                    # Restore env vars
                    os.environ.update(saved_env)

            return func(*args, **kwargs)

        return wrapper

    @staticmethod
    def resolve_s3_uri(func):
        @wraps(func)
        def wrapper(
            *args,
            s3_uri: str | None = None,
            bucket_name: str | None = None,
            prefix: str | None = None,
            **kwargs,
        ):
            if not s3_uri and not bucket_name:
                raise ValueError("Either s3_uri or bucket and key must be provided")
            if s3_uri:
                bucket_name, prefix = S3.resolve_s3_location(s3_uri)
            return func(*args, bucket_name=bucket_name, prefix=prefix or "", **kwargs)

        return wrapper

    # -------------------------List------------------------- #

    @get_client
    @staticmethod
    def list_buckets(
        client: boto3.client,
        *,
        prefix: str | None = None,
        max_buckets: int | None = None,
        continuation_token: str | None = None,
    ) -> dict:
        """List S3 buckets with optional pagination and prefix filtering.

        Args:
            client: The boto3 S3 client (injected by decorator).
            prefix: Optional prefix to filter bucket names.
            max_buckets: Maximum number of buckets to return per page.
            continuation_token: Token for fetching the next page of results.

        Returns:
            dict with keys:
                - buckets: List of bucket dictionaries
                - continuation_token: Token for next page (None if no more pages)
        """
        print(f"Listing S3 buckets with prefix '{prefix or ''}', max_buckets={max_buckets}")

        # Build request parameters
        request_params = {}
        if prefix:
            request_params["Prefix"] = prefix
        if max_buckets:
            request_params["MaxBuckets"] = max_buckets
        if continuation_token:
            request_params["ContinuationToken"] = continuation_token

        response = client.list_buckets(**request_params)

        return {
            "buckets": response.get("Buckets", []),
            "continuation_token": response.get("ContinuationToken"),
        }

    @get_client
    @resolve_s3_uri
    @staticmethod
    def list_objects(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str | None = None,
    ) -> list[dict]:
        """List objects in a bucket with optional prefix."""
        paginator = client.get_paginator("list_objects_v2")
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix or "")

        print(f"Listing objects in bucket '{bucket_name}' with prefix '{prefix}'")
        objects = []
        for response in response_iterator:
            if "Contents" in response:
                objects.extend(response["Contents"])

        return objects

    @get_client
    @resolve_s3_uri
    @staticmethod
    def list_objects_for_prefix(client: boto3.client, *, bucket_name: str, prefix: str | None = None) -> dict:
        """List objects in a bucket for a specific prefix."""
        paginator = client.get_paginator("list_objects_v2")
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix or "", Delimiter="/")

        print(f"Listing objects in bucket '{bucket_name}' for prefix '{prefix}'")
        objects = {}
        for response in response_iterator:
            if "Contents" in response:
                objects["files"] = response["Contents"]
            if "CommonPrefixes" in response:
                objects["folders"] = response["CommonPrefixes"]

        return objects

    @get_client
    @resolve_s3_uri
    @staticmethod
    def list_objects_for_prefix_paginated(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str | None = None,
        max_keys: int | None = None,
        continuation_token: str | None = None,
    ) -> dict:
        """List objects in a bucket for a specific prefix with pagination support.

        Args:
            client: The boto3 S3 client (injected by decorator).
            bucket_name: The name of the S3 bucket.
            prefix: Optional prefix to filter objects.
            max_keys: Maximum number of keys (files + folders) to return per page.
            continuation_token: Token for fetching the next page of results.

        Returns:
            dict with keys:
                - files: List of file objects
                - folders: List of folder prefixes
                - continuation_token: Token for next page (None if no more pages)
        """
        print(f"Listing objects in bucket '{bucket_name}' for prefix '{prefix}', max_keys={max_keys}")

        # Build request parameters
        request_params = {
            "Bucket": bucket_name,
            "Prefix": prefix or "",
            "Delimiter": "/",
        }
        if max_keys:
            request_params["MaxKeys"] = max_keys
        if continuation_token:
            request_params["ContinuationToken"] = continuation_token

        response = client.list_objects_v2(**request_params)

        result = {
            "files": response.get("Contents", []),
            "folders": response.get("CommonPrefixes", []),
            "continuation_token": response.get("NextContinuationToken"),
        }

        return result

    # -------------------------Upload------------------------- #

    @get_client
    @resolve_s3_uri
    @staticmethod
    def upload_file(
        client: boto3.client,
        *,
        local_file_path: str,
        bucket_name: str,
        prefix: str | None = None,
    ) -> None:
        """Upload a file to S3."""
        if not prefix or prefix.endswith("/"):
            key = f"{prefix or ''}{os.path.basename(local_file_path)}"
        else:
            key = prefix

        print(f"Uploading file '{local_file_path}' to bucket '{bucket_name}' with key '{key}'")
        client.upload_file(local_file_path, bucket_name, key)

    @resolve_s3_uri
    @staticmethod
    def upload_directory(*, local_dir_path: str, bucket_name: str, prefix: str | None = None) -> None:
        """Upload a directory to S3."""
        local_dir_path = local_dir_path.rstrip("/")
        if not os.path.isdir(local_dir_path):
            raise ValueError(f"Local path '{local_dir_path}' is not a directory")
        print(f"Uploading folder: {local_dir_path} to s3://{bucket_name}/{prefix}")
        folder_name = os.path.basename(local_dir_path)

        # Build AWS CLI command arguments
        command_args = [
            "s3",
            "cp",
            local_dir_path,
            f"s3://{bucket_name}/{prefix or ''}{folder_name}",
            "--recursive",
        ]

        # Run the command with error handling
        S3._run_aws_cli_command(command_args)

    @get_client
    @resolve_s3_uri
    @staticmethod
    def upload_directory_via_boto3(
        client: boto3.client,
        *,
        local_dir_path: str,
        bucket_name: str,
        prefix: str | None = None,
    ) -> None:
        """Upload a directory to S3."""
        if not os.path.isdir(local_dir_path):
            raise ValueError(f"Local path '{local_dir_path}' is not a directory")

        for root, _, files in os.walk(local_dir_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, local_dir_path)
                key = f"{prefix}{relative_path.replace(os.sep, '/')}"

                print(f"Uploading file '{local_file_path}' to bucket '{bucket_name}' with key '{key}'")
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
        if local_dir_path.endswith("/"):
            # local_dir_path is a directory, extract filename from S3 prefix
            local_file_path = os.path.join(local_dir_path, os.path.basename(prefix))
            directory_path = local_dir_path
        else:
            # local_dir_path contains filename
            local_file_path = local_dir_path
            directory_path = os.path.dirname(local_dir_path)

        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

        print(f"Downloading file from s3://{bucket_name}/{prefix} to {local_file_path}")
        client.download_file(bucket_name, prefix, local_file_path)

    @resolve_s3_uri
    @staticmethod
    def download_directory(*, bucket_name: str, prefix: str | None = None, local_dir_path: str | None = None) -> None:
        """Download a directory from S3."""
        if not local_dir_path:
            local_dir_path = os.getcwd()

        # Extract the directory name from the prefix
        if prefix:
            # Remove trailing slashes and get the last part of the path
            s3_dir_name = prefix.rstrip("/").split("/")[-1]
        else:
            s3_dir_name = "root"

        # Create the target directory path
        target_dir = os.path.join(local_dir_path, s3_dir_name)

        # Ensure the target directory exists
        os.makedirs(target_dir, exist_ok=True)

        # Ensure target_dir is treated as a directory for directory downloads
        if not target_dir.endswith("/"):
            target_dir += "/"

        print(f"Downloading directory from s3://{bucket_name}/{prefix} to {target_dir}")

        # Build AWS CLI command arguments
        command_args = [
            "s3",
            "cp",
            f"s3://{bucket_name}/{prefix or ''}",
            target_dir,
            "--recursive",
        ]

        # Run the command with error handling
        S3._run_aws_cli_command(command_args)

    @get_client
    @resolve_s3_uri
    @staticmethod
    def download_directory_via_boto3(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str | None = None,
        local_dir_path: str = ".",
    ) -> None:
        """Download a directory from S3."""
        paginator = client.get_paginator("list_objects_v2")
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix or "")

        # Extract the directory name from the prefix
        if prefix:
            # Remove trailing slashes and get the last part of the path
            s3_dir_name = prefix.rstrip("/").split("/")[-1]
        else:
            s3_dir_name = "root"

        # Create the target directory path
        target_dir = os.path.join(local_dir_path, s3_dir_name)

        # Ensure the target directory exists
        os.makedirs(target_dir, exist_ok=True)

        print(f"Downloading directory from s3://{bucket_name}/{prefix} to {target_dir}")
        for response in response_iterator:
            if "Contents" in response:
                for obj in response["Contents"]:
                    file_key = obj["Key"]
                    # Calculate relative path from the prefix
                    relative_path = os.path.relpath(file_key, prefix or "")
                    local_file_path = os.path.join(target_dir, relative_path)
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
        prefix: str,
    ) -> None:
        """Delete a file from S3."""
        print(f"Deleting file s3://{bucket_name}/{prefix}")
        client.delete_object(Bucket=bucket_name, Key=prefix)

    @resolve_s3_uri
    @staticmethod
    def delete_directory(*, bucket_name: str, prefix: str | None = None) -> None:
        """Delete a directory from S3."""
        print(f"Deleting directory s3://{bucket_name}/{prefix}")

        # Build AWS CLI command arguments
        command_args = ["s3", "rm", f"s3://{bucket_name}/{prefix or ''}", "--recursive"]

        # Run the command with error handling
        S3._run_aws_cli_command(command_args)

    @get_client
    @resolve_s3_uri
    @staticmethod
    def delete_directory_via_boto3(
        client: boto3.client,
        *,
        bucket_name: str,
        prefix: str | None = None,
    ) -> None:
        """Delete a directory from S3."""
        paginator = client.get_paginator("list_objects_v2")
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix or "")

        print(f"Deleting directory s3://{bucket_name}/{prefix}")
        for response in response_iterator:
            if "Contents" in response:
                objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]
                client.delete_objects(Bucket=bucket_name, Delete={"Objects": objects_to_delete})

    # -------------------------Move------------------------- #

    @get_client
    @staticmethod
    def move_file(
        client: boto3.client,
        *,
        source_s3_bucket: str,
        source_s3_key: str,
        destination_s3_bucket: str,
        destination_s3_key: str,
    ):
        """Move a file from one S3 location to another."""
        print(
            f"Moving file from s3://{source_s3_bucket}/{source_s3_key} to s3://{destination_s3_bucket}/{destination_s3_key}"
        )
        client.copy_object(
            Bucket=destination_s3_bucket,
            CopySource={"Bucket": source_s3_bucket, "Key": source_s3_key},
            Key=destination_s3_key,
        )
        client.delete_object(Bucket=source_s3_bucket, Key=source_s3_key)

    @get_client
    @staticmethod
    def move_directory(
        client: boto3.client,
        *,
        source_s3_bucket: str,
        source_s3_prefix: str,
        destination_s3_bucket: str,
        destination_s3_prefix: str,
    ):
        """Move a directory from one S3 location to another."""
        print(
            f"Moving directory from s3://{source_s3_bucket}/{source_s3_prefix} to s3://{destination_s3_bucket}/{destination_s3_prefix}"
        )

        # Build AWS CLI command arguments
        command_args = [
            "s3",
            "mv",
            f"s3://{source_s3_bucket}/{source_s3_prefix}",
            f"s3://{destination_s3_bucket}/{destination_s3_prefix}",
            "--recursive",
        ]

        # Run the command with error handling
        S3._run_aws_cli_command(command_args)
