#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
REPO_ROOT = Path(__file__).resolve().parents[4]
RUNNER = REPO_ROOT / "multi-agent-dev-workflow" / "scripts" / "workflow_runner.py"


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mawf-html-replication-smoke-") as tmp:
        project_root = Path(tmp)
        run(
            [
                sys.executable,
                str(RUNNER),
                "run",
                "--project-root",
                str(project_root),
                "--run-id",
                "html-replication-smoke",
                "--requirement",
                "Smoke test workflow-managed HTML replication and verification.",
            ],
            cwd=REPO_ROOT,
        )
        run_dir = project_root / ".agent-workflows" / "dev" / "html-replication-smoke"
        reference = run_dir / "artifacts" / "design" / "generated" / "reference.png"
        candidate = run_dir / "artifacts" / "validation" / "candidate.png"
        reference.parent.mkdir(parents=True, exist_ok=True)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        reference.write_bytes(PNG_1X1)
        candidate.write_bytes(PNG_1X1)

        html = "<!doctype html><html><body><main>Smoke UI</main></body></html>"
        run(
            [
                sys.executable,
                str(RUNNER),
                "replicate-ui-html",
                "--run-dir",
                str(run_dir),
                "--reference",
                "artifacts/design/generated/reference.png",
                "--name",
                "smoke",
                "--html",
                html,
                "--force",
            ],
            cwd=REPO_ROOT,
        )
        html_path = run_dir / "artifacts" / "implementation" / "html" / "smoke.html"
        manifest_path = run_dir / "artifacts" / "implementation" / "html" / "smoke.replication.json"
        if not html_path.exists() or "Smoke UI" not in html_path.read_text(encoding="utf-8"):
            raise SystemExit("replicated HTML artifact missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "success":
            raise SystemExit("replication manifest did not succeed")

        run(
            [
                sys.executable,
                str(RUNNER),
                "verify-ui-html",
                "--run-dir",
                str(run_dir),
                "--html",
                "artifacts/implementation/html/smoke.html",
                "--reference",
                "artifacts/design/generated/reference.png",
                "--candidate-screenshot",
                "artifacts/validation/candidate.png",
                "--name",
                "smoke",
            ],
            cwd=REPO_ROOT,
        )
        metrics_path = run_dir / "artifacts" / "validation" / "ui-html" / "smoke" / "verify-metrics.json"
        verification_path = run_dir / "artifacts" / "validation" / "ui-html" / "smoke" / "verification.json"
        if not metrics_path.exists() or not verification_path.exists():
            raise SystemExit("verification artifacts missing")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics["regions"][0]["rms_diff"] != 0:
            raise SystemExit("expected zero diff for identical reference and candidate")
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        if state.get("nodes", {}).get("draw_ui_html_verification", {}).get("status") != "success":
            raise SystemExit("verification node did not finish successfully")
        print(f"html replication smoke ok: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
