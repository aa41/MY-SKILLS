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
    with tempfile.TemporaryDirectory(prefix="mawf-native-adapter-smoke-") as tmp:
        project_root = Path(tmp)
        run(
            [
                sys.executable,
                str(RUNNER),
                "run",
                "--project-root",
                str(project_root),
                "--run-id",
                "native-adapter-smoke",
                "--requirement",
                "Smoke test native UI adapter and verification workflow nodes.",
            ],
            cwd=REPO_ROOT,
        )
        run_dir = project_root / ".agent-workflows" / "dev" / "native-adapter-smoke"
        reference = run_dir / "artifacts" / "design" / "generated" / "reference.png"
        candidate = run_dir / "artifacts" / "validation" / "flutter-candidate.png"
        html_path = run_dir / "artifacts" / "implementation" / "html" / "smoke.html"
        reference.parent.mkdir(parents=True, exist_ok=True)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        reference.write_bytes(PNG_1X1)
        candidate.write_bytes(PNG_1X1)
        html_path.write_text("<!doctype html><html><body>Smoke UI</body></html>", encoding="utf-8")

        code = "import 'package:flutter/widgets.dart';\n\nclass SmokePage extends StatelessWidget { const SmokePage({super.key}); @override Widget build(BuildContext context) => const Text('Smoke UI'); }\n"
        run(
            [
                sys.executable,
                str(RUNNER),
                "adapt-ui-native",
                "--run-dir",
                str(run_dir),
                "--target",
                "flutter",
                "--html",
                "artifacts/implementation/html/smoke.html",
                "--reference",
                "artifacts/design/generated/reference.png",
                "--name",
                "smoke",
                "--code",
                code,
                "--force",
            ],
            cwd=REPO_ROOT,
        )
        output_path = run_dir / "artifacts" / "implementation" / "flutter" / "smoke.dart"
        manifest_path = run_dir / "artifacts" / "implementation" / "flutter" / "smoke.adapter.json"
        if not output_path.exists() or "SmokePage" not in output_path.read_text(encoding="utf-8"):
            raise SystemExit("native adapter output missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "success" or manifest.get("target") != "flutter":
            raise SystemExit("native adapter manifest mismatch")

        run(
            [
                sys.executable,
                str(RUNNER),
                "verify-native-ui",
                "--run-dir",
                str(run_dir),
                "--target",
                "flutter",
                "--reference",
                "artifacts/design/generated/reference.png",
                "--candidate-screenshot",
                "artifacts/validation/flutter-candidate.png",
                "--name",
                "smoke",
            ],
            cwd=REPO_ROOT,
        )
        metrics_path = run_dir / "artifacts" / "validation" / "flutter" / "smoke" / "verify-metrics.json"
        verification_path = run_dir / "artifacts" / "validation" / "flutter" / "smoke" / "verification.json"
        if not metrics_path.exists() or not verification_path.exists():
            raise SystemExit("native verification artifacts missing")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics["regions"][0]["rms_diff"] != 0:
            raise SystemExit("expected zero diff for identical native reference and candidate")
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        if state.get("nodes", {}).get("draw_ui_flutter_verification", {}).get("status") != "success":
            raise SystemExit("native verification node did not finish successfully")
        print(f"native adapter smoke ok: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
