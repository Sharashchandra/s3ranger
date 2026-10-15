"""Real boto3, AWS CLI and UI operations against disposable RustFS."""

import uuid

import pytest
from botocore.exceptions import ClientError
from textual.widgets import Input, ListView

from s3ranger.gateways.s3 import S3
from s3ranger.ui.app import S3Ranger
from s3ranger.ui.modals.download_modal import DownloadModal
from s3ranger.ui.modals.upload_modal import UploadModal
from s3ranger.ui.widgets.bucket_list import BucketList
from s3ranger.ui.widgets.object_list import ObjectList
from helpers import wait_until

pytestmark = pytest.mark.integration


@pytest.fixture
def storage(rustfs):
    client = rustfs["client"]
    names = ["s3ranger-" + uuid.uuid4().hex[:16] for _ in range(2)]
    for name in names:
        client.create_bucket(Bucket=name)
    S3.set_endpoint_url(rustfs["endpoint"])
    S3.set_region_name("us-east-1")
    S3.set_credentials("s3ranger-test", "s3ranger-test-secret")
    try:
        yield client, names
    finally:
        for name in names:
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=name):
                if page.get("Contents"):
                    client.delete_objects(
                        Bucket=name,
                        Delete={
                            "Objects": [{"Key": o["Key"]} for o in page["Contents"]]
                        },
                    )
            client.delete_bucket(Bucket=name)


def test_roundtrip_pagination_copy_move_delete(storage, tmp_path):
    client, (source, dest) = storage
    file = tmp_path / "notes ?#雪.txt"
    file.write_bytes(b"preview content\n")
    S3.upload_file(local_file_path=str(file), bucket_name=source, prefix="docs/")
    key = "docs/" + file.name
    assert S3.read_preview(bucket_name=source, key=key) == file.read_bytes()
    output = tmp_path / "saved.txt"
    S3.download_file(bucket_name=source, prefix=key, local_dir_path=str(output))
    assert output.read_bytes() == file.read_bytes()
    assert source in [b["Name"] for b in S3.list_buckets()["buckets"]]
    for i in range(6):
        client.put_object(Bucket=source, Key=f"page/{i}.txt", Body=str(i).encode())
    token = None
    keys = []
    while True:
        page = S3.list_objects_for_prefix_paginated(
            bucket_name=source, prefix="page/", max_keys=2, continuation_token=token
        )
        keys.extend(o["Key"] for o in page["files"])
        token = page["continuation_token"]
        if not token:
            break
    assert keys == [f"page/{i}.txt" for i in range(6)]
    S3.copy_file(
        source_s3_bucket=source,
        source_s3_key=key,
        destination_s3_bucket=dest,
        destination_s3_key="copy.txt",
    )
    assert S3.read_preview(bucket_name=source, key=key) == file.read_bytes()
    S3.move_file(
        source_s3_bucket=dest,
        source_s3_key="copy.txt",
        destination_s3_bucket=dest,
        destination_s3_key="renamed.txt",
    )
    assert S3.read_preview(bucket_name=dest, key="renamed.txt") == file.read_bytes()
    with pytest.raises(ClientError):
        client.head_object(Bucket=dest, Key="copy.txt")
    S3.delete_file(bucket_name=dest, prefix="renamed.txt")
    assert S3.list_objects(bucket_name=dest) == []


def test_recursive_cli_and_boto3_transfers(storage, tmp_path):
    client, (source, dest) = storage
    directory = tmp_path / "docs"
    directory.mkdir()
    (directory / "a.txt").write_text("a")
    (directory / "nested").mkdir()
    (directory / "nested/b.txt").write_text("b")
    S3.upload_directory(local_dir_path=str(directory), bucket_name=source)
    client.put_object(Bucket=source, Key="docs-other/keep.txt", Body=b"keep")
    S3.copy_directory(
        source_s3_bucket=source,
        source_s3_prefix="docs/",
        destination_s3_bucket=dest,
        destination_s3_prefix="copied/",
    )
    assert {o["Key"] for o in S3.list_objects(bucket_name=dest)} == {
        "copied/a.txt",
        "copied/nested/b.txt",
    }
    S3.move_directory(
        source_s3_bucket=dest,
        source_s3_prefix="copied/",
        destination_s3_bucket=dest,
        destination_s3_prefix="renamed/",
    )
    S3.download_directory(
        bucket_name=dest, prefix="renamed/", local_dir_path=str(tmp_path / "download")
    )
    assert (tmp_path / "download/renamed/nested/b.txt").read_text() == "b"
    S3.delete_directory(bucket_name=source, prefix="docs/")
    assert [o["Key"] for o in S3.list_objects(bucket_name=source)] == [
        "docs-other/keep.txt"
    ]
    S3.upload_directory_via_boto3(
        local_dir_path=str(directory), bucket_name=source, prefix="direct/"
    )
    S3.download_directory_via_boto3(
        bucket_name=source,
        prefix="direct/",
        local_dir_path=str(tmp_path / "direct-download"),
    )
    assert (tmp_path / "direct-download/direct/a.txt").read_text() == "a"
    S3.delete_directory_via_boto3(bucket_name=source, prefix="direct/")
    S3.delete_directory(bucket_name=dest, prefix="renamed/")
    assert S3.list_objects(bucket_name=dest) == []


async def test_ui_browse_upload_download(storage, rustfs, tmp_path):
    client, (source, _) = storage
    client.put_object(Bucket=source, Key="existing.txt", Body=b"existing")
    local = tmp_path / "upload.txt"
    local.write_text("uploaded through UI")
    application = S3Ranger(
        endpoint_url=rustfs["endpoint"],
        region_name="us-east-1",
        aws_access_key_id="s3ranger-test",
        aws_secret_access_key="s3ranger-test-secret",
        download_directory=str(tmp_path) + "/",
    )
    async with application.run_test(size=(120, 40)) as pilot:
        buckets = application.screen.query_one(BucketList)
        await wait_until(
            pilot, lambda: not buckets.is_loading and bool(buckets.buckets), timeout=15
        )
        view = buckets.query_one(ListView)
        view.index = next(
            i for i, b in enumerate(buckets.buckets) if b["name"] == source
        )
        view.focus()
        await pilot.press("enter")
        objects = application.screen.query_one(ObjectList)
        await wait_until(
            pilot, lambda: not objects.is_loading and bool(objects.objects), timeout=15
        )
        objects.focus_list()
        await wait_until(pilot, lambda: objects.query_one(ListView).has_focus)
        await pilot.press("u")
        assert isinstance(application.screen, UploadModal)
        application.screen.query_one(Input).value = str(local)
        await pilot.pause()
        await pilot.press("ctrl+enter")
        await wait_until(
            pilot, lambda: not isinstance(application.screen, UploadModal), timeout=15
        )
        await wait_until(
            pilot,
            lambda: not objects.is_loading
            and any(o["key"] == "upload.txt" for o in objects.objects),
            timeout=15,
        )
        assert (
            S3.read_preview(bucket_name=source, key="upload.txt") == local.read_bytes()
        )
        listing = objects.query_one(ListView)
        listing.index = next(
            i for i, o in enumerate(objects.objects) if o["key"] == "existing.txt"
        )
        listing.focus()
        await pilot.press("space", "d")
        assert isinstance(application.screen, DownloadModal)
        await pilot.press("ctrl+enter")
        await wait_until(
            pilot, lambda: not isinstance(application.screen, DownloadModal), timeout=15
        )
        assert (tmp_path / "existing.txt").read_bytes() == b"existing"
