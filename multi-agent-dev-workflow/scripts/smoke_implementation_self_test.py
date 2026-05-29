#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "multi-agent-dev-workflow" / "scripts" / "workflow_runner.py"


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mawf-implementation-smoke-") as tmp:
        project_root = Path(tmp)
        run(
            [
                sys.executable,
                str(RUNNER),
                "run",
                "--project-root",
                str(project_root),
                "--run-id",
                "implementation-smoke",
                "--requirement",
                "Smoke test implementation evidence and self-test workflow nodes.",
            ],
            cwd=REPO_ROOT,
        )
        run_dir = project_root / ".agent-workflows" / "dev" / "implementation-smoke"
        run(
            [
                sys.executable,
                str(RUNNER),
                "record-implementation",
                "--run-dir",
                str(run_dir),
                "--name",
                "smoke-change",
                "--summary",
                "Implemented smoke change evidence.",
                "--touched-file",
                "lib/smoke.dart",
                "--force",
            ],
            cwd=REPO_ROOT,
        )
        manifest_path = run_dir / "artifacts" / "implementation" / "smoke-change.implementation.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "success" or manifest.get("touched_files") != ["lib/smoke.dart"]:
            raise SystemExit("implementation manifest mismatch")

        run(
            [
                sys.executable,
                str(RUNNER),
                "run-self-test",
                "--run-dir",
                str(run_dir),
                "--name",
                "python-smoke",
                "--force",
                "--",
                sys.executable,
                "-c",
                "print('self test ok')",
            ],
            cwd=REPO_ROOT,
        )
        test_manifest_path = run_dir / "artifacts" / "validation" / "self-tests" / "python-smoke" / "self-test.json"
        test_manifest = json.loads(test_manifest_path.read_text(encoding="utf-8"))
        if test_manifest.get("status") != "success" or test_manifest.get("returncode") != 0:
            raise SystemExit("self-test manifest mismatch")
        stdout = (test_manifest_path.parent / "stdout.txt").read_text(encoding="utf-8")
        if "self test ok" not in stdout:
            raise SystemExit("self-test stdout missing")
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        if state.get("nodes", {}).get("self_test_execution", {}).get("status") != "success":
            raise SystemExit("self-test node did not finish successfully")
        print(f"implementation self-test smoke ok: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
