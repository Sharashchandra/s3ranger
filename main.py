from pathlib import Path

import click

from s3tui.config import CONFIG_FILE_PATH, load_config, merge_config_with_cli_args
from s3tui.ui.app import S3TUI


@click.group(invoke_without_command=True)
@click.pass_context
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
    envvar="AWS_ACCESS_KEY_ID",
)
@click.option(
    "--aws-secret-access-key",
    type=str,
    help="AWS secret access key for authentication",
    default=None,
    envvar="AWS_SECRET_ACCESS_KEY",
)
@click.option(
    "--aws-session-token",
    type=str,
    help="AWS session token for temporary credentials",
    default=None,
    envvar="AWS_SESSION_TOKEN",
)
@click.option(
    "--theme",
    type=click.Choice(["Github Dark", "Dracula", "Solarized", "Sepia"], case_sensitive=False),
    help="Theme to use for the UI",
    default=None,
)
@click.option(
    "--config",
    type=click.Path(exists=True, readable=True, path_type=str),
    help="Path to configuration file (default: ~/.s3tui.config)",
    default=None,
)
def cli(
    ctx,
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
        # Run the main app
        main(
            endpoint_url,
            region_name,
            profile_name,
            aws_access_key_id,
            aws_secret_access_key,
            aws_session_token,
            theme,
            config,
        )


@cli.command()
@click.option(
    "--config",
    type=click.Path(path_type=str),
    help="Path to configuration file (default: ~/.s3tui.config)",
    default=None,
)
def configure(config: str | None = None):
    """Interactive configuration setup for S3TUI"""
    # Determine config file path
    config_path = CONFIG_FILE_PATH
    if config:
        config_path = Path(config)

    click.echo("S3TUI Configuration Setup")
    click.echo("=" * 30)
    click.echo("Press Space and Enter without typing anything to remove an existing value.")
    click.echo("Leave fields empty to use defaults or skip optional settings.")
    click.echo()

    # Load existing config if it exists
    existing_config = {}
    if config_path.exists():
        try:
            import toml

            with open(config_path, "r") as f:
                existing_config = toml.load(f)
            click.echo(f"Found existing configuration at {config_path}")
            click.echo()
        except Exception:
            pass

    config = {}

    # S3 Configuration
    click.echo("S3 Configuration:")
    click.echo("-" * 16)

    current = existing_config.get("endpoint_url", "")
    endpoint_url = click.prompt(
        "Endpoint URL (for S3-compatible services like MinIO)", default=current, show_default=bool(current), type=str
    ).strip()
    if endpoint_url:
        config["endpoint_url"] = endpoint_url

    current = existing_config.get("region_name", "")
    region_name = click.prompt("AWS Region Name", default=current, show_default=bool(current), type=str).strip()
    if region_name:
        config["region_name"] = region_name

    current = existing_config.get("profile_name", "")
    profile_name = click.prompt("AWS Profile Name", default=current, show_default=bool(current), type=str).strip()
    if profile_name:
        config["profile_name"] = profile_name

    # Only ask for credentials if profile is not set
    if not profile_name:
        click.echo()
        click.echo("AWS Credentials (leave empty if using profile or environment variables):")

        current = existing_config.get("aws_access_key_id", "")
        access_key = click.prompt("AWS Access Key ID", default=current, show_default=bool(current), type=str).strip()
        if access_key:
            config["aws_access_key_id"] = access_key

        current = existing_config.get("aws_secret_access_key", "")
        secret_key = click.prompt(
            "AWS Secret Access Key", default=current, show_default=bool(current), hide_input=True, type=str
        ).strip()
        if secret_key:
            config["aws_secret_access_key"] = secret_key

        current = existing_config.get("aws_session_token", "")
        session_token = click.prompt(
            "AWS Session Token (optional)", default=current, show_default=bool(current), type=str
        ).strip()
        if session_token:
            config["aws_session_token"] = session_token

    # Theme Configuration
    click.echo()
    click.echo("Theme Configuration:")
    click.echo("-" * 18)

    current_theme = existing_config.get("theme", "Github Dark")
    theme_choices = ["Github Dark", "Dracula", "Solarized", "Sepia"]

    click.echo("Available themes:")
    for i, theme in enumerate(theme_choices, 1):
        marker = " (current)" if theme == current_theme else ""
        click.echo(f"  {i}. {theme}{marker}")

    theme_choice = click.prompt(
        "Select theme (1-4)",
        default=theme_choices.index(current_theme) + 1 if current_theme in theme_choices else 1,
        type=click.IntRange(1, 4),
    )
    config["theme"] = theme_choices[theme_choice - 1]

    # Validate configuration
    click.echo()
    try:
        from s3tui.config import S3Config

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

        # Merge with CLI arguments (CLI takes priority)
        config_obj = merge_config_with_cli_args(
            config_obj,
            endpoint_url=endpoint_url,
            region_name=region_name,
            profile_name=profile_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            theme=theme,
        )
    except ValueError as e:
        raise click.ClickException(str(e))

    app = S3TUI(
        endpoint_url=config_obj.endpoint_url,
        region_name=config_obj.region_name,
        profile_name=config_obj.profile_name,
        aws_access_key_id=config_obj.aws_access_key_id,
        aws_secret_access_key=config_obj.aws_secret_access_key,
        aws_session_token=config_obj.aws_session_token,
        theme=config_obj.theme,
    )
    app.run()


if __name__ == "__main__":
    cli()
