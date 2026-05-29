#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_ROOT = Path.home() / ".local" / "share" / "draw" / "outputs"
DEFAULT_MIME = "image/png"

ASPECT_RATIOS = {
    "ultrawide": "21:9",
    "wide": "16:9",
    "square": "1:1",
    "portrait": "3:4",
    "classic": "4:3",
}


@dataclass(frozen=True)
class ProviderConfig:
    provider_id: str
    provider_type: str
    api_key_env: str
    model: str
    base_url: str
    endpoint: str


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def find_provider(config: dict[str, Any], provider_id: str = "") -> dict[str, Any]:
    active_provider = provider_id or str(config.get("active_provider") or "")
    providers = config.get("providers")
    if not isinstance(providers, list):
        raise SystemExit("[ERROR] imagegen config providers must be an array.")
    for provider in providers:
        if isinstance(provider, dict) and provider.get("id") == active_provider:
            return provider
    raise SystemExit(f"[ERROR] imagegen provider not found: {active_provider}")


def load_provider_config(config_path: str, provider_id: str = "") -> ProviderConfig:
    config = read_json(Path(config_path).expanduser())
    provider = find_provider(config, provider_id)
    provider_type = str(provider.get("type") or "")
    if provider_type not in {"openai-compatible", "custom-http"}:
        raise SystemExit(
            "[ERROR] draw-ui image generation supports openai-compatible or custom-http providers. "
            f"Got {provider_type!r} from {provider.get('id')!r}."
        )
    result = ProviderConfig(
        provider_id=str(provider.get("id") or ""),
        provider_type=provider_type,
        api_key_env=str(provider.get("api_key_env") or ""),
        model=str(provider.get("model") or ""),
        base_url=str(provider.get("base_url") or ""),
        endpoint=str(provider.get("endpoint") or ""),
    )
    missing = [
        name
        for name, value in (
            ("id", result.provider_id),
            ("api_key_env", result.api_key_env),
            ("model", result.model),
            ("base_url", result.base_url),
            ("endpoint", result.endpoint),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"[ERROR] imagegen provider is missing required fields: {', '.join(missing)}")
    return result


def resolve_api_key(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def sanitize_name(value: str, fallback: str = "image") -> str:
    value = value.strip()
    value = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-_.")
    return (value or fallback)[:80]


def build_output_path(*, output_arg: str, image_type: str, topic: str, explicit_name: str, ext: str) -> Path:
    if output_arg:
        out = Path(output_arg).expanduser().resolve()
        return out if out.suffix else out.with_suffix(ext)
    now = datetime.now()
    day_dir = DEFAULT_OUTPUT_ROOT / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_name(explicit_name or topic, fallback=image_type)
    return day_dir / f"{now.strftime('%Y%m%d-%H%M%S')}__{image_type}__{base_name}{ext}"


def metadata_path_for(image_path: Path) -> Path:
    return image_path.with_suffix(image_path.suffix + ".json")


def guess_extension(mime_type: str | None) -> str:
    if not mime_type:
        return ".png"
    guessed = mimetypes.guess_extension(mime_type)
    if guessed == ".jpe":
        return ".jpg"
    return guessed or ".png"


def download_file(url: str, dest: Path, timeout: int = 120) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        dest.write_bytes(response.read())


def resolve_ref(raw: str, tmp_dir: Path) -> Path:
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        suffix = Path(parsed.path).suffix or ".png"
        dest = tmp_dir / f"ref-{len(list(tmp_dir.iterdir())) + 1}{suffix}"
        download_file(raw, dest)
        return dest
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Reference not found: {raw}")
    return path


def data_url_for(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or DEFAULT_MIME
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def endpoint_url(provider: ProviderConfig) -> str:
    base = provider.base_url.rstrip("/")
    endpoint = provider.endpoint
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return f"{base}/{endpoint.lstrip('/')}"


def build_payload(*, provider: ProviderConfig, prompt: str, refs: list[Path], aspect_ratio: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": provider.model,
        "prompt": prompt,
        "n": 1,
    }
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if refs:
        payload["reference_images"] = [data_url_for(path) for path in refs]
    return payload


def post_json(*, url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def image_from_response(response: dict[str, Any]) -> tuple[bytes, str]:
    data = response.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            if isinstance(first.get("b64_json"), str):
                return base64.b64decode(first["b64_json"]), DEFAULT_MIME
            if isinstance(first.get("url"), str):
                with tempfile.TemporaryDirectory(prefix="draw-image-url-") as tmp:
                    path = Path(tmp) / "image"
                    download_file(first["url"], path)
                    return path.read_bytes(), mimetypes.guess_type(first["url"])[0] or DEFAULT_MIME
            image = first.get("image")
            if isinstance(image, str):
                return decode_image_string(image)
    for key in ("b64_json", "image", "image_base64"):
        value = response.get(key)
        if isinstance(value, str):
            return decode_image_string(value)
    raise RuntimeError("Could not extract image bytes from image provider response.")


def decode_image_string(value: str) -> tuple[bytes, str]:
    if value.startswith("data:"):
        header, encoded = value.split(",", 1)
        mime = header[5:].split(";", 1)[0] or DEFAULT_MIME
        return base64.b64decode(encoded), mime
    return base64.b64decode(value), DEFAULT_MIME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate UI images through workflow imagegen config.")
    parser.add_argument("--type", choices=sorted(ASPECT_RATIOS.keys()), default="wide", help="Aspect ratio preset.")
    parser.add_argument("--prompt", required=True, help="Full prompt for image generation.")
    parser.add_argument("--ref", action="append", default=[], help="Reference image path or URL (repeatable).")
    parser.add_argument("--name", default="", help="Optional short output name.")
    parser.add_argument("-o", "--output", default="", help="Output image path.")
    parser.add_argument("--model", default="", help="Model override.")
    parser.add_argument("--base-url", default="", help=argparse.SUPPRESS)
    parser.add_argument("--endpoint", default="", help=argparse.SUPPRESS)
    parser.add_argument("--imagegen-config", required=True, help="Workflow imagegen config path.")
    parser.add_argument("--provider", default="", help="Provider id inside --imagegen-config.")
    parser.add_argument("--timeout", type=int, default=300, help="HTTP timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provider = load_provider_config(args.imagegen_config, args.provider)
    if args.model:
        provider = ProviderConfig(**{**provider.__dict__, "model": args.model})
    if args.base_url:
        provider = ProviderConfig(**{**provider.__dict__, "base_url": args.base_url})
    if args.endpoint:
        provider = ProviderConfig(**{**provider.__dict__, "endpoint": args.endpoint})

    api_key = resolve_api_key(provider.api_key_env)
    if not api_key:
        print(
            f"[ERROR] No {provider.api_key_env} found. Set the environment variable named by imagegen config.",
            file=sys.stderr,
        )
        return 1

    aspect_ratio = ASPECT_RATIOS[args.type]
    with tempfile.TemporaryDirectory(prefix="draw-refs-") as tmp:
        refs = [resolve_ref(raw, Path(tmp)) for raw in args.ref]
        output_path = build_output_path(
            output_arg=args.output,
            image_type=args.type,
            topic=args.name or "image",
            explicit_name=args.name,
            ext=".png",
        )
        payload = build_payload(provider=provider, prompt=args.prompt, refs=refs, aspect_ratio=aspect_ratio)
        response = post_json(
            url=endpoint_url(provider),
            api_key=api_key,
            payload=payload,
            timeout=args.timeout,
        )
        image_bytes, image_mime = image_from_response(response)
        final_path = output_path if output_path.suffix else output_path.with_suffix(guess_extension(image_mime))
        final_path.parent.mkdir(parents=True, exist_ok=True)
        final_path.write_bytes(image_bytes)

    meta_path = metadata_path_for(final_path)
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "type": args.type,
        "aspect_ratio": aspect_ratio,
        "prompt": args.prompt,
        "refs": [str(path) for path in refs],
        "provider": provider.provider_id,
        "provider_type": provider.provider_type,
        "model": provider.model,
        "base_url": provider.base_url,
        "endpoint": provider.endpoint,
        "api_key_env": provider.api_key_env,
        "imagegen_config": args.imagegen_config,
        "output_path": str(final_path),
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"output_path={final_path}")
    print(f"metadata_path={meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
