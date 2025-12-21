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

    profile_name: Optional[str] = None
    theme: str = "Github Dark"
    enable_pagination: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self):
        """Validate configuration settings."""
        # Validate theme
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
