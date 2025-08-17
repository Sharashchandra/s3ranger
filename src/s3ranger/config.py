"""Configuration management for S3Ranger."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import toml

ALLOWED_THEMES = ["Github Dark", "Dracula", "Solarized", "Sepia"]
CONFIG_FILE_PATH = Path.home() / ".s3ranger.config"


@dataclass
class S3Config:
    """S3 configuration settings."""

    endpoint_url: Optional[str] = None
    region_name: Optional[str] = None
    profile_name: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None
    theme: str = "Github Dark"

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """Validate configuration settings."""
        # Rule 4: If endpoint_url is provided, region_name is mandatory
        if self.endpoint_url and not self.region_name:
            raise ValueError("region_name is required when endpoint_url is provided")

        # Rule 1: If profile_name is given, do not allow aws_access_key_id, aws_secret_access_key and aws_session_token
        if self.profile_name and any(
            [self.aws_access_key_id, self.aws_secret_access_key, self.aws_session_token]
        ):
            raise ValueError(
                "Cannot use profile_name when aws_access_key_id, aws_secret_access_key, or aws_session_token is provided"
            )

        # Rule 3: If aws_session_token is given without aws_access_key_id and aws_secret_access_key, it's an error
        if self.aws_session_token and not (
            self.aws_access_key_id and self.aws_secret_access_key
        ):
            raise ValueError(
                "aws_session_token requires both aws_access_key_id and aws_secret_access_key to be provided"
            )

        # Rule 2: If aws_access_key_id and aws_secret_access_key are given, aws_session_token is optional
        # This means if either access_key or secret_key is provided, both must be provided
        if (self.aws_access_key_id or self.aws_secret_access_key) and not (
            self.aws_access_key_id and self.aws_secret_access_key
        ):
            raise ValueError(
                "Both aws_access_key_id and aws_secret_access_key are required when providing credentials"
            )

        # Rule 5: Validate theme (optional and not dependent on other fields)
        if self.theme not in ALLOWED_THEMES:
            raise ValueError(
                f"Invalid theme '{self.theme}'. Allowed themes: {', '.join(ALLOWED_THEMES)}"
            )


def load_config(config_file_path: Optional[str] = None) -> S3Config:
    """Load configuration from file."""
    if config_file_path:
        config_path = Path(config_file_path)
    else:
        config_path = CONFIG_FILE_PATH

    if not config_path.exists():
        return S3Config()

    try:
        with open(config_path, "r") as f:
            config_data = toml.load(f)

        # Extract only the fields that belong to S3Config
        valid_fields = {field.name for field in S3Config.__dataclass_fields__.values()}

        # Filter config data to only include valid fields
        filtered_config = {
            key: value for key, value in config_data.items() if key in valid_fields
        }

        return S3Config(**filtered_config)

    except Exception as e:
        raise ValueError(f"Error loading config file {config_path}: {e}")


def merge_config_with_cli_args(config: S3Config, **cli_args) -> S3Config:
    """Merge configuration with CLI arguments, giving priority to CLI args."""
    # Start with config values
    merged_config = {}

    # Add all config values
    for field_name in S3Config.__dataclass_fields__:
        merged_config[field_name] = getattr(config, field_name)

    # Override with CLI args where provided (not None)
    for key, value in cli_args.items():
        if value is not None:
            merged_config[key] = value

    return S3Config(**merged_config)
