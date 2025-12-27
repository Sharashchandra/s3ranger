"""Configuration management for S3Ranger."""

import os
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
    download_directory: Optional[str] = None

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


def compress_path(path: str) -> str:
    """Compress a path by replacing home directory with ~."""
    home = os.path.expanduser("~")
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


def resolve_download_directory(
    cli_download_dir: Optional[str] = None,
    config_download_dir: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """Resolve the download directory following the priority order.

    Priority order:
    1. CLI provided path (if exists and not empty)
    2. Config file path (if exists and not empty)
    3. Default ~/Downloads/ (if exists)
    4. Current working directory (fallback)

    Args:
        cli_download_dir: Download directory from CLI argument
        config_download_dir: Download directory from config file

    Returns:
        Tuple of (resolved path, optional warning message)
    """
    from s3ranger.ui.constants import DEFAULT_DOWNLOAD_DIRECTORY

    # Helper to check if path exists
    def path_exists(path: Optional[str]) -> bool:
        if not path or not path.strip():
            return False
        expanded = os.path.expanduser(path.strip())
        return os.path.isdir(expanded)

    # Helper to ensure path ends with trailing slash
    def ensure_trailing_slash(path: str) -> str:
        return path if path.endswith("/") else path + "/"

    # Track if user provided a path (to show warning if it doesn't exist)
    user_provided_path = cli_download_dir or config_download_dir

    # Priority 1: CLI provided path
    if path_exists(cli_download_dir):
        compressed = compress_path(os.path.expanduser(cli_download_dir.strip()))
        return ensure_trailing_slash(compressed), None

    # Priority 2: Config file path
    if path_exists(config_download_dir):
        compressed = compress_path(os.path.expanduser(config_download_dir.strip()))
        return ensure_trailing_slash(compressed), None

    # Priority 3: Default ~/Downloads/
    if path_exists(DEFAULT_DOWNLOAD_DIRECTORY):
        # If user provided a path but it doesn't exist, show warning
        if user_provided_path and user_provided_path.strip():
            warning = (
                f"Download directory '{user_provided_path}' does not exist, "
                f"falling back to {DEFAULT_DOWNLOAD_DIRECTORY}"
            )
            return DEFAULT_DOWNLOAD_DIRECTORY, warning
        return DEFAULT_DOWNLOAD_DIRECTORY, None

    # Priority 4: Current working directory (fallback)
    cwd = os.getcwd()
    resolved_path = ensure_trailing_slash(compress_path(cwd))

    # Build warning message
    if user_provided_path and user_provided_path.strip():
        warning = (
            f"Download directory '{user_provided_path}' does not exist, "
            f"and {DEFAULT_DOWNLOAD_DIRECTORY} also does not exist. "
            f"Falling back to current working directory"
        )
    else:
        warning = (
            f"Default download directory {DEFAULT_DOWNLOAD_DIRECTORY} does not exist, "
            "falling back to current working directory"
        )

    return resolved_path, warning
