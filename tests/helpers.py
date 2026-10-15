"""Small deterministic fixtures shared by interaction and visual tests."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock

from s3ranger.gateways.s3 import S3
from s3ranger.ui.app import S3Ranger
from s3ranger.ui.widgets.bucket_list import BucketList
from s3ranger.ui.widgets.object_list import ObjectList

DATE = datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc)
FILES = [
    {"Key": "notes.txt", "Size": 12, "LastModified": DATE},
    {"Key": "photo.bin", "Size": 2048, "LastModified": DATE},
]
FOLDERS = [{"Prefix": "docs/"}]
OBJECTS = [
    {"key": "notes.txt", "is_folder": False, "size": "12 B"},
    {"key": "docs", "is_folder": True, "size": ""},
]
URIS = ["s3://alpha/notes.txt", "s3://alpha/docs/"]
LONG_PREVIEW_KEY = "folder/" * 145 + "notes.txt"  # S3's 1,024-byte key limit.


def mock_storage(monkeypatch):
    buckets = Mock(
        return_value={
            "buckets": [
                {"Name": "alpha", "CreationDate": DATE, "BucketRegion": "us-east-1"},
                {"Name": "beta", "CreationDate": DATE},
            ],
            "continuation_token": None,
        }
    )

    def objects(**kw):
        prefix = kw.get("prefix") or ""
        if prefix:
            return {
                "files": [{**FILES[0], "Key": prefix + "notes.txt"}],
                "folders": [],
                "continuation_token": None,
            }
        return {"files": FILES, "folders": FOLDERS, "continuation_token": None}

    listing = Mock(side_effect=objects)
    monkeypatch.setattr(S3, "list_buckets", buckets)
    monkeypatch.setattr(S3, "list_objects_for_prefix_paginated", listing)
    monkeypatch.setattr(
        S3, "read_preview", Mock(return_value=b"first needle\nlast NEEDLE\n")
    )
    return buckets, listing


def app():
    return S3Ranger(download_directory="/downloads/", enable_pagination=True)


async def wait_until(pilot, condition, timeout=5):
    async with asyncio.timeout(timeout):
        while not condition():
            await pilot.pause()
            await asyncio.sleep(0)
    await pilot.pause()


async def open_bucket(pilot, name="alpha"):
    buckets = pilot.app.screen.query_one(BucketList)
    await wait_until(pilot, lambda: not buckets.is_loading and bool(buckets.buckets))
    view = buckets.query_one("#bucket-list-view")
    view.focus()
    view.index = next(i for i, b in enumerate(buckets.buckets) if b["name"] == name)
    await pilot.press("enter")
    objects = pilot.app.screen.query_one(ObjectList)
    await wait_until(pilot, lambda: not objects.is_loading and bool(objects.objects))
    objects._apply_focus()
    objects._ensure_focus()
    await pilot.pause()
    return objects
