"""
S3Ranger - S3 Terminal User Interface

This module provides the main CLI entry point for S3Ranger, a terminal-based interface
for browsing and managing S3 buckets and objects. It includes configuration management
and interactive setup capabilities.
"""

from pathlib import Path
from typing import Any, Dict

import click

from s3ranger import __version__
from s3ranger.config import CONFIG_FILE_PATH, load_config
from s3ranger.credentials import resolve_credentials
from s3ranger.ui.app import S3Ranger

# Constants
THEME_CHOICES = ["Github Dark", "Dracula", "Solarized", "Sepia"]
DEFAULT_THEME = "Github Dark"


def _load_existing_config(config_path: Path) -> Dict[str, Any]:
    """Load existing configuration from file if it exists."""
    if not config_path.exists():
        return {}

    try:
        import toml

        with open(config_path, "r") as f:
            config = toml.load(f)
        click.echo(f"Found existing configuration at {config_path}")
        click.echo()
        return config
    except Exception:
        return {}


def _prompt_for_value(prompt_text: str, current_value: str = "", hide_input: bool = False) -> str:
    """Helper function to prompt for a configuration value."""
    return click.prompt(
        prompt_text,
        default=current_value,
        show_default=bool(current_value),
        hide_input=hide_input,
        type=str,
    ).strip()


def _configure_s3_settings(existing_config: Dict[str, Any]) -> Dict[str, Any]:
    """Configure S3-related settings."""
    click.echo("S3 Configuration:")
    click.echo("-" * 16)

    config = {}

    # Profile Name
    current = existing_config.get("profile_name", "")
    profile_name = _prompt_for_value("AWS Profile Name", current)
    if profile_name:
        config["profile_name"] = profile_name

    return config


def _configure_theme(existing_config: Dict[str, Any]) -> str:
    """Configure theme selection."""
    click.echo()
    click.echo("Theme Configuration:")
    click.echo("-" * 18)

    current_theme = existing_config.get("theme", DEFAULT_THEME)

    click.echo("Available themes:")
    for i, theme in enumerate(THEME_CHOICES, 1):
        marker = " (current)" if theme == current_theme else ""
        click.echo(f"  {i}. {theme}{marker}")

    default_choice = THEME_CHOICES.index(current_theme) + 1 if current_theme in THEME_CHOICES else 1

    theme_choice = click.prompt(
        "Select theme (1-4)",
        default=default_choice,
        type=click.IntRange(1, 4),
    )

    return THEME_CHOICES[theme_choice - 1]


def _configure_pagination(existing_config: Dict[str, Any]) -> bool:
    """Configure pagination setting."""
    click.echo()
    click.echo("Performance Configuration:")
    click.echo("-" * 24)

    current = existing_config.get("enable_pagination", True)
    current_str = "enabled" if current else "disabled"
    click.echo(f"Current pagination: {current_str}")

    enable = click.confirm(
        "Enable pagination? (loads items incrementally as you scroll)",
        default=current,
    )

    return enable


def _validate_and_save_config(config: Dict[str, Any], config_path: Path) -> None:
    """Validate and save the configuration."""
    click.echo()

    # Validate configuration
    try:
        from s3ranger.config import S3Config

        S3Config(**config)
        click.echo("✓ Configuration validated successfully!")
    except ValueError as e:
        click.echo(f"✗ Configuration validation failed: {e}")
        if not click.confirm("Save configuration anyway?"):
            click.echo("Configuration cancelled.")
            return

    # Save configuration
    click.echo()
    try:
        import toml

        with open(config_path, "w") as f:
            toml.dump(config, f)
        click.echo(f"✓ Configuration saved to {config_path}")
    except Exception as e:
        click.echo(f"✗ Failed to save configuration: {e}")


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version=__version__, prog_name="s3ranger")
@click.option(
    "--endpoint-url",
    type=str,
    help="Custom S3 endpoint URL (e.g., for S3-compatible services like MinIO)",
    default=None,
)
@click.option(
    "--region-name",
    type=str,
    help="AWS region name (required when using custom endpoint-url)",
    default=None,
    envvar="AWS_DEFAULT_REGION",
)
@click.option(
    "--profile-name",
    type=str,
    help="AWS profile name to use for authentication",
    default=None,
)
@click.option(
    "--aws-access-key-id",
    type=str,
    help="AWS access key ID for authentication",
    default=None,
)
@click.option(
    "--aws-secret-access-key",
    type=str,
    help="AWS secret access key for authentication",
    default=None,
)
@click.option(
    "--aws-session-token",
    type=str,
    help="AWS session token for temporary credentials",
    default=None,
)
@click.option(
    "--theme",
    type=click.Choice(THEME_CHOICES, case_sensitive=False),
    help="Theme to use for the UI",
    default=None,
)
@click.option(
    "--config",
    type=click.Path(exists=True, readable=True, path_type=str),
    help="Path to configuration file (default: ~/.s3ranger.config)",
    default=None,
)
def cli(
    ctx: click.Context,
    endpoint_url: str | None = None,
    region_name: str | None = None,
    profile_name: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
    theme: str | None = None,
    config: str | None = None,
):
    """S3 Terminal UI - Browse and manage S3 buckets and objects."""
    if ctx.invoked_subcommand is None:
        # Run the main app when no subcommand is specified
        main(
            endpoint_url=endpoint_url,
            region_name=region_name,
            profile_name=profile_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            theme=theme,
            config=config,
        )


@cli.command()
@click.option(
    "--config",
    type=click.Path(path_type=str),
    help="Path to configuration file (default: ~/.s3ranger.config)",
    default=None,
)
def configure(config: str | None = None):
    """Interactive configuration setup for S3Ranger"""
    # Determine config file path
    config_path = CONFIG_FILE_PATH
    if config:
        config_path = Path(config)

    click.echo("S3Ranger Configuration Setup")
    click.echo("=" * 30)
    click.echo("Press Space and Enter without typing anything to remove an existing value.")
    click.echo("Leave fields empty to use defaults or skip optional settings.")
    click.echo()

    # Load existing configuration
    existing_config = _load_existing_config(config_path)

    # Configure S3 settings
    s3_config = _configure_s3_settings(existing_config)

    # Configure theme
    s3_config["theme"] = _configure_theme(existing_config)

    # Configure pagination
    s3_config["enable_pagination"] = _configure_pagination(existing_config)

    # Validate and save configuration
    _validate_and_save_config(s3_config, config_path)


def main(
    endpoint_url: str | None = None,
    region_name: str | None = None,
    profile_name: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
    theme: str | None = None,
    config: str | None = None,
):
    """S3 Terminal UI - Browse and manage S3 buckets and objects."""
    try:
        # Load configuration from file
        config_obj = load_config(config)

        # Resolve credentials following strict priority order:
        # 1. CLI access key + secret key (highest priority)
        # 2. CLI profile name
        # 3. Config file profile name
        # 4. Error if nothing provided
        resolved_creds = resolve_credentials(
            cli_access_key=aws_access_key_id,
            cli_secret_key=aws_secret_access_key,
            cli_session_token=aws_session_token,
            cli_profile=profile_name,
            config_profile=config_obj.profile_name,
        )

        # endpoint_url and region_name only come from CLI
        # Default region to us-east-1 when endpoint_url is provided
        final_region_name = region_name
        if endpoint_url and not final_region_name:
            final_region_name = "us-east-1"
        final_theme = theme or config_obj.theme
        enable_pagination = config_obj.enable_pagination

    except ValueError as e:
        raise click.ClickException(str(e))

    # Create and run the application
    app = S3Ranger(
        endpoint_url=endpoint_url,
        region_name=final_region_name,
        profile_name=resolved_creds.profile_name,
        aws_access_key_id=resolved_creds.aws_access_key_id,
        aws_secret_access_key=resolved_creds.aws_secret_access_key,
        aws_session_token=resolved_creds.aws_session_token,
        theme=final_theme,
        enable_pagination=enable_pagination,
    )
    app.run()


if __name__ == "__main__":
    cli()
