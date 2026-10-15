"""The separate coverage gates must use the current pytest-cov measurement."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import conftest as harness


@pytest.mark.parametrize("directory", [".", "tests"])
def test_gate_ignores_stale_data_with_custom_coverage_file(tmp_path, directory):
    tests = tmp_path / "tests"
    tests.mkdir()
    shutil.copyfile(harness.__file__, tests / "conftest.py")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
    )
    (tmp_path / "sample.py").write_text(
        "def choose(value):\n    if value:\n        return 1\n    return 0\n"
    )
    test = tests / "test_sample.py"
    test.write_text(
        "from sample import choose\n"
        "def test_choose():\n    assert choose(True) == 1\n    assert choose(False) == 0\n"
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--offline",
        "--cov=sample",
        "--cov-branch",
        "--cov-report=term",
    ]
    environment = {**os.environ, "COVERAGE_FILE": str(tmp_path / ".coverage")}
    seed = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert seed.returncode == 0, seed.stdout + seed.stderr
    assert "lines 100.00%, branches 100.00%" in seed.stdout
    stale = (tmp_path / ".coverage").read_bytes()
    test.write_text(
        "from sample import choose\ndef test_choose():\n    assert choose(True) == 1\n"
    )
    environment["COVERAGE_FILE"] = str(tmp_path / "current.coverage")
    result = subprocess.run(
        command,
        cwd=tmp_path / directory,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "lines 75.00%, branches 50.00%" in result.stdout
    assert (tmp_path / ".coverage").read_bytes() == stale
    totals = json.loads((tmp_path / "coverage.json").read_text())["totals"]
    assert totals["covered_lines"] / totals["num_statements"] == 0.75
    assert totals["covered_branches"] / totals["num_branches"] == 0.5


@pytest.mark.parametrize(
    "lines,branches,initial,expected",
    [(90, 90, 0, 0), (89, 100, 0, 1), (100, 89, 0, 1), (80, 80, 2, 2)],
)
def test_each_threshold_and_existing_failure(
    monkeypatch, tmp_path, lines, branches, initial, expected
):
    measured = Mock()
    measured.json_report.side_effect = lambda *, outfile: Path(outfile).write_text(
        json.dumps(
            {
                "totals": {
                    "covered_lines": lines,
                    "num_statements": 100,
                    "covered_branches": branches,
                    "num_branches": 100,
                },
            }
        )
    )
    reporter = Mock()
    plugins = {
        "_cov": SimpleNamespace(cov_controller=SimpleNamespace(cov=measured)),
        "terminalreporter": reporter,
    }
    session = SimpleNamespace(
        config=SimpleNamespace(
            option=SimpleNamespace(
                no_cov=False, collectonly=False, cov_source=["s3ranger"]
            ),
            pluginmanager=SimpleNamespace(getplugin=plugins.get),
        ),
        exitstatus=initial,
    )
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    harness.pytest_sessionfinish(session, initial)
    assert session.exitstatus == expected
    measured.json_report.assert_called_once()


@pytest.mark.parametrize("state", ["missing", "no-data", "no-branches"])
def test_missing_measurement_fails(monkeypatch, tmp_path, state):
    measured = Mock()
    measured.get_data.return_value.has_arcs.return_value = state != "no-branches"
    from coverage.exceptions import NoDataError

    measured.json_report.side_effect = NoDataError("No current data")
    reporter = Mock()
    plugin = (
        None
        if state == "missing"
        else SimpleNamespace(cov_controller=SimpleNamespace(cov=measured))
    )
    session = SimpleNamespace(
        config=SimpleNamespace(
            option=SimpleNamespace(
                no_cov=False, collectonly=False, cov_source=["s3ranger"]
            ),
            pluginmanager=SimpleNamespace(
                getplugin={"_cov": plugin, "terminalreporter": reporter}.get
            ),
        ),
        exitstatus=0,
    )
    monkeypatch.setattr(harness, "ROOT", tmp_path)
    harness.pytest_sessionfinish(session, 0)
    assert session.exitstatus == 1
    assert any(
        "Coverage gate failed" in str(call)
        for call in reporter.write_line.call_args_list
    )
