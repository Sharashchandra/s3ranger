"""S3 request contracts and failure handling without network access."""

import os
import subprocess
from unittest.mock import ANY, Mock

import boto3
from botocore.stub import Stubber
import pytest

from s3ranger.gateways.s3 import S3


@pytest.fixture
def client():
    result = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    yield result
    result.close()


def test_bucket_and_object_requests(client):
    with Stubber(client) as stub:
        stub.add_response(
            "list_buckets",
            {"Buckets": [], "ContinuationToken": "next"},
            {"Prefix": "a", "MaxBuckets": 2, "ContinuationToken": "previous"},
        )
        assert S3.list_buckets(
            client=client, prefix="a", max_buckets=2, continuation_token="previous"
        ) == {"buckets": [], "continuation_token": "next"}
        stub.add_response("list_buckets", {}, {})
        assert S3.list_buckets(client=client) == {
            "buckets": [],
            "continuation_token": None,
        }
        stub.add_response(
            "list_objects_v2",
            {"NextContinuationToken": "next"},
            {
                "Bucket": "bucket",
                "Prefix": "dir/",
                "Delimiter": "/",
                "MaxKeys": 2,
                "ContinuationToken": "previous",
            },
        )
        assert S3.list_objects_for_prefix_paginated(
            client=client,
            s3_uri="s3://bucket/dir/",
            max_keys=2,
            continuation_token="previous",
        ) == {"files": [], "folders": [], "continuation_token": "next"}
        stub.add_response(
            "list_objects_v2", {}, {"Bucket": "bucket", "Prefix": "", "Delimiter": "/"}
        )
        assert S3.list_objects_for_prefix_paginated(
            client=client, bucket_name="bucket"
        ) == {"files": [], "folders": [], "continuation_token": None}
        stub.assert_no_pending_responses()
    with pytest.raises(ValueError):
        S3.list_objects(client=client)


def test_paginated_listing_accumulates_all_pages():
    client = Mock()
    paginator = client.get_paginator.return_value
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "a"}], "CommonPrefixes": [{"Prefix": "one/"}]},
        {},
        {"Contents": [{"Key": "b"}], "CommonPrefixes": [{"Prefix": "two/"}]},
    ]
    assert S3.list_objects(client=client, bucket_name="bucket") == [
        {"Key": "a"},
        {"Key": "b"},
    ]
    assert S3.list_objects_for_prefix(client=client, bucket_name="bucket") == {
        "files": [{"Key": "a"}, {"Key": "b"}],
        "folders": [{"Prefix": "one/"}, {"Prefix": "two/"}],
    }
    paginator.paginate.assert_called_with(Bucket="bucket", Prefix="", Delimiter="/")


@pytest.mark.parametrize(
    "explicit,profile", [(False, False), (False, True), (True, False), (True, True)]
)
def test_client_credential_precedence(monkeypatch, explicit, profile):
    session = Mock()
    monkeypatch.setattr("s3ranger.gateways.s3.boto3.Session", session)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "environment")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "environment-secret")
    monkeypatch.setenv("AWS_PROFILE", "environment-profile")
    S3.set_endpoint_url("http://localhost:9000")
    S3.set_region_name("eu-west-1")
    if explicit:
        S3.set_credentials("key", "secret", "token")
    if profile:
        S3.set_profile_name("work")
    session.return_value.client.return_value.list_buckets.return_value = {}
    S3.list_buckets()
    expected = {"region_name": "eu-west-1"}
    if explicit:
        expected.update(
            aws_access_key_id="key",
            aws_secret_access_key="secret",
            aws_session_token="token",
            botocore_session=ANY,
        )
    elif profile:
        expected["profile_name"] = "work"
    session.assert_called_once_with(**expected)
    session.return_value.client.assert_called_once_with(
        service_name="s3", endpoint_url="http://localhost:9000", region_name="eu-west-1"
    )
    assert os.environ["AWS_ACCESS_KEY_ID"] == "environment"
    assert os.environ["AWS_PROFILE"] == "environment-profile"


@pytest.mark.parametrize(
    "profiles",
    [("AWS_PROFILE",), ("AWS_DEFAULT_PROFILE",), ("AWS_PROFILE", "AWS_DEFAULT_PROFILE")],
)
@pytest.mark.parametrize("token", [None, "explicit-token"])
def test_explicit_credentials_ignore_ambient_profiles(monkeypatch, profiles, token):
    for name in profiles:
        monkeypatch.setenv(name, "missing-profile")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "environment-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "environment-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "environment-token")
    S3.set_credentials("explicit-key", "explicit-secret", token)
    S3.set_region_name("us-east-1")
    environment = dict(os.environ)

    @S3.get_client
    def request(*, client):
        try:
            credentials = client._request_signer._credentials.get_frozen_credentials()
            assert credentials.access_key == "explicit-key"
            assert credentials.secret_key == "explicit-secret"
            assert credentials.token == token
            with Stubber(client) as stub:
                stub.add_response("list_buckets", {"Buckets": []}, {})
                assert client.list_buckets()["Buckets"] == []
                stub.assert_no_pending_responses()
        finally:
            client.close()

    request()
    assert dict(os.environ) == environment


def test_default_client_preserves_environment(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "environment")
    observed = []
    session = Mock()

    def create(**kw):
        observed.append(os.environ.get("AWS_ACCESS_KEY_ID"))
        return session

    monkeypatch.setattr("s3ranger.gateways.s3.boto3.Session", create)
    session.client.return_value.list_buckets.return_value = {}
    S3.list_buckets()
    assert observed == ["environment"]
    session.client.assert_called_once_with(service_name="s3")
    monkeypatch.setattr(
        "s3ranger.gateways.s3.boto3.Session", Mock(side_effect=RuntimeError("failure"))
    )
    with pytest.raises(RuntimeError):
        S3.list_buckets()
    assert os.environ["AWS_ACCESS_KEY_ID"] == "environment"


def test_cli_environment_and_failure(monkeypatch):
    run = Mock(return_value=Mock(stdout="ok"))
    monkeypatch.setattr(subprocess, "run", run)
    S3.set_credentials("key", "secret", "token")
    S3.set_endpoint_url("http://localhost:9000")
    S3.set_region_name("us-east-1")
    assert S3._run_aws_cli_command(["s3", "ls"]) == "ok"
    assert run.call_args.args[0] == [
        "aws",
        "s3",
        "ls",
        "--endpoint-url",
        "http://localhost:9000",
        "--region",
        "us-east-1",
    ]
    assert run.call_args.kwargs["env"]["AWS_SESSION_TOKEN"] == "token"
    S3.set_profile_name("work")
    S3._run_aws_cli_command(["s3", "ls"])
    assert run.call_args.args[0][-2:] == ["--profile", "work"]
    assert "AWS_ACCESS_KEY_ID" not in run.call_args.kwargs["env"]
    run.side_effect = subprocess.CalledProcessError(1, "aws", stderr="Access denied")
    with pytest.raises(RuntimeError, match="Access denied"):
        S3._run_aws_cli_command(["s3", "ls"])


@pytest.mark.parametrize(
    "prefix,key",
    [(None, "file.txt"), ("dir/", "dir/file.txt"), ("renamed.txt", "renamed.txt")],
)
def test_upload_file(prefix, key):
    client = Mock()
    S3.upload_file(
        client=client,
        bucket_name="bucket",
        local_file_path="/source/file.txt",
        prefix=prefix,
    )
    client.upload_file.assert_called_once_with("/source/file.txt", "bucket", key)


def test_directory_uploads_and_cli_commands(tmp_path, monkeypatch):
    directory = tmp_path / "docs"
    directory.mkdir()
    (directory / "a.txt").write_text("a")
    (directory / "nested").mkdir()
    (directory / "nested/b.txt").write_text("b")
    command = Mock()
    monkeypatch.setattr(S3, "_run_aws_cli_command", command)
    S3.upload_directory(local_dir_path=str(directory), s3_uri="s3://bucket/dir/")
    command.assert_called_with(
        ["s3", "cp", str(directory), "s3://bucket/dir/docs", "--recursive"]
    )
    client = Mock()
    S3.upload_directory_via_boto3(
        client=client, local_dir_path=str(directory), bucket_name="bucket"
    )
    assert {call.args[2] for call in client.upload_file.call_args_list} == {
        "a.txt",
        "nested/b.txt",
    }
    for method in (S3.upload_directory, S3.upload_directory_via_boto3):
        kw = {"client": client} if method == S3.upload_directory_via_boto3 else {}
        with pytest.raises(ValueError):
            method(local_dir_path=str(tmp_path / "missing"), bucket_name="bucket", **kw)


@pytest.mark.parametrize("destination", ["out/", "out/renamed.txt", "renamed.txt"])
def test_file_download_creates_parent(tmp_path, monkeypatch, destination):
    monkeypatch.chdir(tmp_path)
    client = Mock()
    S3.download_file(
        client=client,
        bucket_name="bucket",
        prefix="dir/file.txt",
        local_dir_path=destination,
    )
    expected = "out/file.txt" if destination.endswith("/") else destination
    client.download_file.assert_called_once_with("bucket", "dir/file.txt", expected)
    S3.download_file(
        client=client,
        bucket_name="bucket",
        prefix="dir/file.txt",
        local_dir_path=destination,
    )


def test_recursive_download_and_delete(tmp_path, monkeypatch):
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [
        {},
        {"Contents": [{"Key": "dir/a.txt"}, {"Key": "dir/nested/b.txt"}]},
    ]
    S3.download_directory_via_boto3(
        client=client, bucket_name="bucket", prefix="dir/", local_dir_path=str(tmp_path)
    )
    assert {call.args[2] for call in client.download_file.call_args_list} == {
        str(tmp_path / "dir/a.txt"),
        str(tmp_path / "dir/nested/b.txt"),
    }
    S3.delete_directory_via_boto3(client=client, bucket_name="bucket", prefix="dir/")
    client.delete_objects.assert_called_once_with(
        Bucket="bucket",
        Delete={"Objects": [{"Key": "dir/a.txt"}, {"Key": "dir/nested/b.txt"}]},
    )
    client.get_paginator.return_value.paginate.return_value = []
    S3.download_directory_via_boto3(
        client=client, bucket_name="bucket", local_dir_path=str(tmp_path)
    )
    assert (tmp_path / "root").is_dir()
    command = Mock()
    monkeypatch.setattr(S3, "_run_aws_cli_command", command)
    monkeypatch.chdir(tmp_path)
    S3.download_directory(bucket_name="bucket")
    command.assert_called_with(
        ["s3", "cp", "s3://bucket/", str(tmp_path / "root") + "/", "--recursive"]
    )
    S3.download_directory(
        bucket_name="bucket", prefix="dir/", local_dir_path=str(tmp_path)
    )
    command.assert_called_with(
        ["s3", "cp", "s3://bucket/dir/", str(tmp_path / "dir") + "/", "--recursive"]
    )
    S3.delete_directory(bucket_name="bucket")
    command.assert_called_with(["s3", "rm", "s3://bucket/", "--recursive"])
    S3.delete_file(client=client, s3_uri="s3://bucket/file")
    client.delete_object.assert_called_once_with(Bucket="bucket", Key="file")


@pytest.mark.parametrize("move", [False, True])
def test_copy_move_contract_and_data_loss_prevention(move):
    client = Mock()
    method = S3.move_file if move else S3.copy_file
    args = dict(
        client=client,
        source_s3_bucket="source",
        source_s3_key="a ?#",
        destination_s3_bucket="dest",
        destination_s3_key="b ?#",
    )
    method(**args)
    client.copy_object.assert_called_once_with(
        Bucket="dest", CopySource={"Bucket": "source", "Key": "a ?#"}, Key="b ?#"
    )
    assert client.delete_object.call_count == int(move)
    if move:
        assert [call[0] for call in client.method_calls] == [
            "copy_object",
            "delete_object",
        ]
        client.reset_mock()
        client.copy_object.side_effect = RuntimeError("copy failed")
        with pytest.raises(RuntimeError):
            method(**args)
        client.delete_object.assert_not_called()


@pytest.mark.parametrize(
    "method,operation", [(S3.copy_directory, "cp"), (S3.move_directory, "mv")]
)
def test_recursive_copy_move(monkeypatch, method, operation):
    command = Mock()
    monkeypatch.setattr(S3, "_run_aws_cli_command", command)
    method(
        client=Mock(),
        source_s3_bucket="source",
        source_s3_prefix="a/",
        destination_s3_bucket="dest",
        destination_s3_prefix="b/",
    )
    command.assert_called_once_with(
        ["s3", operation, "s3://source/a/", "s3://dest/b/", "--recursive"]
    )
