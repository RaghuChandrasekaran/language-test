"""Pytest plugin that logs every test session to test_runs.jsonl."""

import json
import time
from pathlib import Path

_session_data = {}


def pytest_sessionstart(session):
    _session_data["start"] = time.time()
    _session_data["passed"] = []
    _session_data["failed"] = []


def pytest_runtest_logreport(report):
    if report.when == "call":
        if report.passed:
            _session_data["passed"].append(report.nodeid)
        elif report.failed:
            _session_data["failed"].append(report.nodeid)


def pytest_sessionfinish(session, exitstatus):
    log_path = Path(__file__).parent / "test_runs.jsonl"
    existing = 0
    if log_path.exists():
        existing = sum(1 for _ in open(log_path))

    entry = {
        "run": existing + 1,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_sec": round(time.time() - _session_data["start"], 2),
        "pass_count": len(_session_data["passed"]),
        "fail_count": len(_session_data["failed"]),
        "passed": _session_data["passed"],
        "failed": _session_data["failed"],
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
