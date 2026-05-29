#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
REPO_ROOT = Path(__file__).resolve().parents[4]
RUNNER = REPO_ROOT / "multi-agent-dev-workflow" / "scripts" / "workflow_runner.py"


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if payload.get("model") != "gpt-image-2":
            self.send_error(400, "unexpected model")
            return
        if not payload.get("prompt"):
            self.send_error(400, "missing prompt")
            return
        body = json.dumps(
            {
                "data": [
                    {
                        "b64_json": base64.b64encode(PNG_1X1).decode("ascii"),
                    }
                ]
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, check=True, text=True, capture_output=True)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with tempfile.TemporaryDirectory(prefix="mawf-draw-ui-runner-smoke-") as tmp:
            project_root = Path(tmp)
            run(
                [
                    sys.executable,
                    str(RUNNER),
                    "run",
                    "--project-root",
                    str(project_root),
                    "--run-id",
                    "draw-ui-runner-smoke",
                    "--requirement",
                    "Smoke test workflow-managed draw-ui generation.",
                ],
                cwd=REPO_ROOT,
            )
            run_dir = project_root / ".agent-workflows" / "dev" / "draw-ui-runner-smoke"
            config_path = run_dir / "config" / "imagegen.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["active_provider"] = "mock-openai-image"
            config["providers"] = [
                {
                    "id": "mock-openai-image",
                    "type": "openai-compatible",
                    "enabled": True,
                    "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                    "api_key_env": "DRAW_UI_SMOKE_API_KEY",
                    "model": "gpt-image-2",
                    "endpoint": "/images/generations",
                    "approval_required_for": [
                        "sensitive_image_upload",
                        "paid_model_call",
                        "external_network",
                    ],
                }
            ]
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

            output = "artifacts/design/generated/runner-primary-ui.png"
            env = {**os.environ, "DRAW_UI_SMOKE_API_KEY": "test-key"}
            run(
                [
                    sys.executable,
                    str(RUNNER),
                    "generate-ui-image",
                    "--run-dir",
                    str(run_dir),
                    "--provider",
                    "mock-openai-image",
                    "--prompt",
                    "Workflow runner smoke UI mockup",
                    "--output",
                    output,
                    "--force",
                ],
                cwd=REPO_ROOT,
                env=env,
            )

            image_path = run_dir / output
            metadata_path = image_path.with_suffix(image_path.suffix + ".json")
            if not image_path.exists() or image_path.read_bytes() != PNG_1X1:
                raise SystemExit("workflow-generated image mismatch")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("provider") != "mock-openai-image":
                raise SystemExit("workflow-generated metadata provider mismatch")
            state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            node = state.get("nodes", {}).get("draw_ui_image_generation", {})
            if node.get("status") != "success":
                raise SystemExit("workflow node did not finish successfully")
            events = (run_dir / "events.jsonl").read_text(encoding="utf-8")
            if "draw_ui_image_generation_completed" not in events:
                raise SystemExit("workflow completion event missing")
            print(f"workflow smoke ok: {image_path}")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
