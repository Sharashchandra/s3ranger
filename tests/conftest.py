"""Local regression harness: isolated AWS state, required RustFS, coverage gates."""

import json
import os
from pathlib import Path
import shutil
import sys
import threading
import subprocess
import time
import uuid

import boto3
from botocore.config import Config
import pytest

from s3ranger.gateways.s3 import S3

ROOT = Path(__file__).resolve().parents[1]
ACCESS_KEY = "s3ranger-test"
SECRET_KEY = "s3ranger-test-secret"


def pytest_addoption(parser):
    parser.addoption(
        "--offline",
        action="store_true",
        help="Explicitly run only offline tests (not full acceptance).",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--offline"):
        items[:] = [item for item in items if "integration" not in item.keywords]


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch, tmp_path):
    existing_threads = set(threading.enumerate())
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PATH",
        str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
    )
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("COLORTERM", "truecolor")
    for name in list(os.environ):
        if name.startswith("AWS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "aws-config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "aws-credentials"))
    from s3ranger import config

    monkeypatch.setattr(config, "CONFIG_FILE_PATH", tmp_path / "s3ranger.config")
    for name in (
        "_endpoint_url",
        "_region_name",
        "_profile_name",
        "_aws_access_key_id",
        "_aws_secret_access_key",
        "_aws_session_token",
    ):
        monkeypatch.setattr(S3, name, None)

    yield
    # asyncio owns its executor threads; native UI workers and debounce timers
    # must finish before state is restored for the next test.
    workers = [
        thread
        for thread in threading.enumerate()
        if thread not in existing_threads and not thread.name.startswith("asyncio_")
    ]
    for thread in workers:
        thread.join(timeout=2)
    assert not [thread.name for thread in workers if thread.is_alive()], (
        "UI worker or debounce timer leaked"
    )


@pytest.fixture(scope="session", autouse=True)
def rustfs(request):
    if request.config.getoption("--offline"):
        yield None
        return
    if not shutil.which("docker"):
        pytest.fail(
            "Docker is required. Install/start Docker Desktop, then run uv run pytest."
        )
    project = "s3ranger-tests-" + uuid.uuid4().hex[:12]
    command = [
        "docker",
        "compose",
        "-f",
        str(ROOT / "tests/compose.yaml"),
        "-p",
        project,
    ]

    def run(args, timeout=180):
        return subprocess.run(
            command + args, capture_output=True, text=True, check=True, timeout=timeout
        )

    client = None
    started = False
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=15)
        run(["version"], timeout=15)
        subprocess.run(
            [shutil.which("aws") or "aws", "--version"],
            capture_output=True,
            check=True,
            timeout=15,
        )
        started = True
        run(["up", "-d"])
        port = run(["port", "rustfs", "9000"]).stdout.strip().rsplit(":", 1)[-1]
        endpoint = f"http://127.0.0.1:{port}"
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            region_name="us-east-1",
            aws_access_key_id=ACCESS_KEY,
            aws_secret_access_key=SECRET_KEY,
            config=Config(
                s3={"addressing_style": "path"},
                connect_timeout=1,
                read_timeout=2,
                retries={"max_attempts": 0},
            ),
        )
        deadline = time.monotonic() + 60
        while True:
            try:
                client.list_buckets()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError("RustFS did not become ready within 60 seconds")
                time.sleep(0.2)
        yield {"client": client, "endpoint": endpoint}
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        logs = subprocess.run(
            command + ["logs", "--tail", "40"], capture_output=True, text=True
        ).stdout
        pytest.fail(f"Required RustFS integration service failed: {error}\n{logs}")
    finally:
        if client:
            client.close()
        if started:
            result = subprocess.run(
                command + ["down", "--volumes", "--remove-orphans"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode:
                pytest.fail(f"RustFS cleanup failed for {project}: {result.stderr}")


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    if (
        getattr(session.config.option, "no_cov", False)
        or getattr(session.config.option, "collectonly", False)
        or not getattr(session.config.option, "cov_source", None)
    ):
        return
    from coverage.exceptions import CoverageException

    reporter = session.config.pluginmanager.getplugin("terminalreporter")
    plugin = session.config.pluginmanager.getplugin("_cov")
    controller = getattr(plugin, "cov_controller", None)
    measured = getattr(controller, "cov", None)
    try:
        if measured is None or not measured.get_data().has_arcs():
            raise ValueError("Current branch coverage data is unavailable")
        output = ROOT / "coverage.json"
        measured.json_report(outfile=str(output))
        totals = json.loads(output.read_text())["totals"]
        if not totals["num_statements"] or not totals["num_branches"]:
            raise ValueError("Current line or branch coverage data is empty")
        line = 100 * totals["covered_lines"] / totals["num_statements"]
        branch = 100 * totals["covered_branches"] / totals["num_branches"]
    except (CoverageException, OSError, ValueError, KeyError) as error:
        reporter.write_line(f"Coverage gate failed: {error}")
        if session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        return
    reporter.write_line("")
    reporter.write_line(
        f"Separate coverage gates: lines {line:.2f}%, branches {branch:.2f}% (required: 90% each)"
    )
    if (line < 90 or branch < 90) and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
