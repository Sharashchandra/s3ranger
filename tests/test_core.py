"""Configuration, credentials, CLI and presentation utility contracts."""

from unittest.mock import Mock

from click.testing import CliRunner
import pytest

from s3ranger import config, credentials, main
from s3ranger.gateways.s3 import S3
from s3ranger.ui import utils


def test_config_load_merge_and_errors(tmp_path, monkeypatch):
    assert config.load_config().theme == "Github Dark"
    path = tmp_path / "config.toml"
    path.write_text(
        'theme="Dracula"\nprofile_name="work"\nunknown="ignored"\nenable_pagination=true\n'
    )
    loaded = config.load_config(str(path))
    assert loaded.profile_name == "work"
    assert config.merge_config_with_cli_args(
        loaded, theme="Sepia", enable_pagination=False, profile_name=None
    ) == config.S3Config("work", "Sepia", False)
    monkeypatch.setattr(config, "CONFIG_FILE_PATH", path)
    assert config.load_config() == loaded
    for contents in ('invalid = "unterminated', 'theme="missing"'):
        path.write_text(contents)
        with pytest.raises(ValueError, match="Error loading config"):
            config.load_config(str(path))
    with pytest.raises(ValueError, match="Invalid theme"):
        config.S3Config(theme="missing")


def test_download_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert config.compress_path(str(tmp_path / "docs")) == "~/docs"
    assert config.compress_path("/elsewhere") == "/elsewhere"
    assert config.compress_path(str(tmp_path) + "-other") == str(tmp_path) + "-other"
    assert config.resolve_download_directory() == (
        "~/",
        "Default download directory ~/Downloads/ does not exist, falling back to current working directory",
    )
    assert "does not exist" in config.resolve_download_directory("missing")[1]
    (tmp_path / "Downloads").mkdir()
    assert config.resolve_download_directory() == ("~/Downloads/", None)
    assert config.resolve_download_directory("missing")[1]
    (tmp_path / "docs").mkdir()
    assert config.resolve_download_directory(" ~/docs ", "~/Downloads/") == (
        "~/docs/",
        None,
    )
    assert config.resolve_download_directory("missing", "~/docs/") == ("~/docs/", None)
    assert config.resolve_download_directory(" ", " ") == ("~/Downloads/", None)


@pytest.mark.parametrize(
    "args,expected",
    [
        (
            ("key", "secret", "token", "cli", "config"),
            credentials.ResolvedCredentials("key", "secret", "token", source="cli"),
        ),
        (
            (None, None, None, "cli", "config"),
            credentials.ResolvedCredentials(profile_name="cli", source="cli"),
        ),
        (
            (None, None, None, None, "config"),
            credentials.ResolvedCredentials(
                profile_name="config", source="config_file"
            ),
        ),
        (
            (None, None, None, None, None),
            credentials.ResolvedCredentials(source="default"),
        ),
    ],
)
def test_credential_precedence(args, expected):
    assert credentials.resolve_credentials(*args) == expected


@pytest.mark.parametrize(
    "kwargs", [{}, {"aws_access_key_id": "key"}, {"aws_secret_access_key": "secret"}]
)
def test_credential_validation(kwargs):
    with pytest.raises(ValueError):
        credentials.ResolvedCredentials(**kwargs).validate()
    credentials.ResolvedCredentials(profile_name="work").validate()
    credentials.ResolvedCredentials("key", "secret").validate()


def test_cli_precedence_and_errors(tmp_path, monkeypatch):
    app = Mock()
    monkeypatch.setattr(main, "S3Ranger", app)
    monkeypatch.setattr(
        main, "resolve_download_directory", lambda **kw: ("/downloads/", "warning")
    )
    path = tmp_path / "settings"
    path.write_text('profile_name="config"\ntheme="Sepia"\nenable_pagination=true')
    runner = CliRunner()
    result = runner.invoke(
        main.cli,
        [
            "--config",
            str(path),
            "--profile-name",
            "cli",
            "--theme",
            "dracula",
            "--disable-pagination",
            "--endpoint-url",
            "http://localhost:9000",
        ],
    )
    assert result.exit_code == 0, result.output
    kw = app.call_args.kwargs
    assert kw["profile_name"] == "cli"
    assert kw["theme"] == "Dracula"
    assert kw["enable_pagination"] is False
    assert kw["region_name"] == "us-east-1"
    app.return_value.run.assert_called_once()
    main.main(
        config=str(path),
        region_name="eu-west-1",
        aws_access_key_id="key",
        aws_secret_access_key="secret",
        aws_session_token="token",
    )
    assert app.call_args.kwargs["aws_session_token"] == "token"
    assert app.call_args.kwargs["theme"] == "Sepia"
    assert app.call_args.kwargs["enable_pagination"] is True
    assert runner.invoke(main.cli, ["--help"]).exit_code == 0
    assert runner.invoke(main.cli, ["--version"]).exit_code == 0
    assert runner.invoke(main.cli, ["--theme", "bad"]).exit_code != 0
    path.write_text('theme="bad"')
    assert runner.invoke(main.cli, ["--config", str(path)]).exit_code != 0


def test_configuration_wizard(tmp_path, monkeypatch):
    runner = CliRunner()
    path = tmp_path / "settings"
    result = runner.invoke(
        main.cli, ["configure", "--config", str(path)], input="work\n2\nn\n/tmp\n"
    )
    assert result.exit_code == 0, result.output
    assert config.load_config(str(path)) == config.S3Config(
        "work", "Dracula", False, "/tmp"
    )
    assert main._load_existing_config(path)["theme"] == "Dracula"
    path.write_text('broken = "unterminated')
    assert main._load_existing_config(path) == {}
    assert main._load_existing_config(tmp_path / "missing") == {}
    monkeypatch.setattr(main, "CONFIG_FILE_PATH", path)
    result = runner.invoke(main.cli, ["configure"], input="\n1\ny\n\n")
    assert result.exit_code == 0
    assert config.load_config(str(path)).profile_name is None
    monkeypatch.setattr(main.click, "confirm", lambda *a, **k: False)
    main._validate_and_save_config({"theme": "bad"}, path)
    assert config.load_config(str(path)).theme == "Github Dark"
    monkeypatch.setattr(main.click, "confirm", lambda *a, **k: True)
    main._validate_and_save_config({"theme": "bad"}, path)
    assert "bad" in path.read_text()
    main._validate_and_save_config({}, tmp_path / "missing" / "config")


@pytest.mark.parametrize(
    "size,text",
    [
        (0, "0 B"),
        (1023, "1023 B"),
        (1024, "1.0 KB"),
        (1024**2, "1.0 MB"),
        (1024**3, "1.0 GB"),
    ],
)
def test_sizes(size, text):
    assert utils.format_file_size(size) == text


def test_uri_and_display_contracts():
    assert utils.build_s3_uri("bucket") == "s3://bucket"
    key = "folder/file ?#雪.txt"
    assert utils.parse_s3_uri(utils.build_s3_uri("bucket", key)) == ("bucket", key)
    assert S3.resolve_s3_location("s3://bucket/" + key) == ("bucket", key)
    assert utils.generate_item_id("bucket-", "name") == "bucket-name"
    assert utils.extract_identifier_from_id("bucket-name", "bucket-") == "name"
    assert utils.extract_identifier_from_id("other", "bucket-") is None
    assert utils.extract_identifier_from_id("", "bucket-") is None
    assert utils.format_object_display_text("file", 1024) == "file (1.0 KB)"
    assert utils.format_folder_display_text("docs") == "📁 docs"
    assert utils.get_parent_path("a/b/c") == "a/b"
    assert utils.get_parent_path("a") == ""


def test_connection_info(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert utils.get_current_aws_profile() == "default"
    assert utils.get_current_endpoint_url() is None
    S3.set_credentials("key", "secret")
    assert S3.is_using_cli_credentials()
    assert utils.get_current_aws_profile() == "custom"
    S3.set_profile_name("work")
    assert utils.get_current_aws_profile() == "work"
    aws = tmp_path / ".aws"
    aws.mkdir()
    (aws / "config").write_text("[profile work]\nendpoint_url=http://localhost:9000\n")
    assert utils.get_current_endpoint_url() == "http://localhost:9000"
    S3.set_endpoint_url("http://explicit:9000")
    assert utils.get_current_endpoint_url() == "http://explicit:9000"
    S3.set_endpoint_url()
    S3.set_profile_name("missing")
    assert utils.get_current_endpoint_url() is None
    S3.set_profile_name()
    S3.set_credentials()
    (aws / "config").write_text("[default]\nendpoint_url=http://default:9000\n")
    assert utils.get_current_endpoint_url() == "http://default:9000"
    monkeypatch.setattr(S3, "get_profile_name", Mock(side_effect=RuntimeError()))
    assert utils.get_current_aws_profile() == "default"
    monkeypatch.setattr(S3, "get_endpoint_url", Mock(side_effect=RuntimeError()))
    assert utils.get_current_endpoint_url() is None


@pytest.mark.parametrize(
    "module",
    [
        "s3ranger.ui.widgets.object_list",
        "s3ranger.ui.modals.preview_modal",
        "s3ranger.ui.widgets",
        "s3ranger.ui.modals",
        "s3ranger.main",
    ],
)
def test_modules_import_without_circular_dependencies(module):
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib, sys; importlib.import_module(sys.argv[1])",
            module,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
