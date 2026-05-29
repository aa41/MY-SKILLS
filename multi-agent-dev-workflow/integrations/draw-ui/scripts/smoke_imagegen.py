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


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
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


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with tempfile.TemporaryDirectory(prefix="draw-ui-smoke-") as tmp:
            tmp_dir = Path(tmp)
            config = {
                "version": "0.1.0",
                "active_provider": "mock-openai-image",
                "providers": [
                    {
                        "id": "mock-openai-image",
                        "type": "openai-compatible",
                        "enabled": True,
                        "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                        "api_key_env": "DRAW_UI_SMOKE_API_KEY",
                        "model": "gpt-image-2",
                        "endpoint": "/images/generations",
                    }
                ],
            }
            config_path = tmp_dir / "imagegen.json"
            output_path = tmp_dir / "mockup.png"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            env = {**os.environ, "DRAW_UI_SMOKE_API_KEY": "test-key"}
            command = [
                sys.executable,
                str(Path(__file__).with_name("generate_image.py")),
                "--imagegen-config",
                str(config_path),
                "--provider",
                "mock-openai-image",
                "--prompt",
                "Smoke UI mockup",
                "--output",
                str(output_path),
            ]
            subprocess.run(command, check=True, env=env)
            metadata_path = output_path.with_suffix(output_path.suffix + ".json")
            if not output_path.exists() or output_path.read_bytes() != PNG_1X1:
                raise SystemExit("generated image mismatch")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("provider") != "mock-openai-image":
                raise SystemExit("metadata provider mismatch")
            print(f"smoke ok: {output_path}")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
