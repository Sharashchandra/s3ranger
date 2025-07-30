import click

from s3tui.ui.app import S3TUI


@click.command()
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
def main(
    endpoint_url: str | None = None,
    region_name: str | None = None,
    profile_name: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
):
    """S3 Terminal UI - Browse and manage S3 buckets and objects."""
    # Validate that region-name is provided when endpoint-url is specified
    if endpoint_url and not region_name:
        raise click.ClickException("--region-name is required when using --endpoint-url")

    # Validate that if one credential parameter is provided, access key and secret key are both provided
    credentials_provided = any([aws_access_key_id, aws_secret_access_key, aws_session_token])
    if credentials_provided and not (aws_access_key_id and aws_secret_access_key):
        raise click.ClickException(
            "Both --aws-access-key-id and --aws-secret-access-key are required when providing credentials"
        )

    app = S3TUI(
        endpoint_url=endpoint_url,
        region_name=region_name,
        profile_name=profile_name,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
    )
    app.run()


if __name__ == "__main__":
    main()
