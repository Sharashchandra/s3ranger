"""Check manual publishing and credential failures without uploading anything."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml


WORKFLOW = yaml.load(
    (Path(__file__).resolve().parents[1] / ".github/workflows/publish.yml").read_text(),
    Loader=yaml.BaseLoader,
)
STEPS = WORKFLOW["jobs"]["publish"]["steps"]


def test_publish_is_manual_and_always_builds_main():
    assert list(WORKFLOW["on"]) == ["workflow_dispatch"]
    choice = WORKFLOW["on"]["workflow_dispatch"]["inputs"]["repository"]
    assert choice["type"] == "choice"
    assert choice["default"] == "TestPyPI"
    assert choice["options"] == ["TestPyPI", "PyPI"]
    checkout = next(step for step in STEPS if "checkout@" in step.get("uses", ""))
    assert checkout["with"] == {"ref": "main", "persist-credentials": "false"}
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert WORKFLOW["concurrency"] == {
        "group": "publish-${{ inputs.repository }}",
        "cancel-in-progress": "false",
    }
    assert not any("secrets." in str(step) for step in STEPS if "if" not in step)


@pytest.mark.parametrize(
    "repository,prefix,index",
    [("TestPyPI", "TEST_PYPI", "--index testpypi "), ("PyPI", "PYPI", "")],
)
@pytest.mark.parametrize("missing", [None, "USERNAME", "PASSWORD"])
def test_publish_routes_credentials_and_rejects_missing_secrets(
    repository, prefix, index, missing, tmp_path
):
    step = next(
        step for step in STEPS if step.get("name") == f"Publish to {repository}"
    )
    assert step["if"] == f"inputs.repository == '{repository}'"
    assert step["env"] == {
        "UV_PUBLISH_USERNAME": "${{ secrets." + prefix + "_USERNAME }}",
        "UV_PUBLISH_PASSWORD": "${{ secrets." + prefix + "_API_TOKEN }}",
    }
    environment = {
        **os.environ,
        "UV_PUBLISH_USERNAME": "__token__",
        "UV_PUBLISH_PASSWORD": "fake-token",
    }
    if missing:
        environment[f"UV_PUBLISH_{missing}"] = ""
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/s3ranger.whl").touch()
    result = subprocess.run(
        ["bash", "-e", "-c", 'uv() { printf "%s\\n" "$*"; }\n' + step["run"]],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if missing:
        assert result.returncode != 0
        assert "repository secret" in result.stderr
        assert result.stdout == ""
    else:
        assert result.returncode == 0, result.stderr
        assert (
            result.stdout
            == f"publish {index}--trusted-publishing never dist/s3ranger.whl\n"
        )
