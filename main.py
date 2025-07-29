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
def main(endpoint_url, region_name):
    """S3 Terminal UI - Browse and manage S3 buckets and objects."""
    # Validate that region-name is provided when endpoint-url is specified
    if endpoint_url and not region_name:
        raise click.ClickException("--region-name is required when using --endpoint-url")

    app = S3TUI(endpoint_url=endpoint_url, region_name=region_name)
    app.run()


if __name__ == "__main__":
    main()
