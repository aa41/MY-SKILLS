#!/usr/bin/env python3
"""Manage image generation provider configuration for workflow runs."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUPPORTED_PROVIDER_TYPES = {
    "openai-compatible",
    "gemini",
    "custom-http",
}

DEFAULT_GLOBAL_CONFIG = Path.home() / ".config" / "multi-agent-dev-workflow" / "imagegen.json"
DEFAULT_PROJECT_CONFIG = Path(".agent-workflows") / "config" / "imagegen.json"
DEFAULT_RUN_CONFIG = Path("config") / "imagegen.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key == "providers" and isinstance(value, list):
            base_providers = providers_by_id({"providers": merged.get("providers", [])})
            for provider in value:
                if not isinstance(provider, dict) or not provider.get("id"):
                    raise ValueError("provider overrides must be objects with id")
                provider_id = provider["id"]
                existing = base_providers.get(provider_id, {})
                base_providers[provider_id] = deep_merge(existing, provider)
            merged["providers"] = list(base_providers.values())
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def existing_paths(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def default_layer_paths(project_root: Path | None = None, run_dir: Path | None = None) -> list[Path]:
    paths = [DEFAULT_GLOBAL_CONFIG]
    if project_root:
        paths.append(project_root / DEFAULT_PROJECT_CONFIG)
    if run_dir:
        paths.append(run_dir / DEFAULT_RUN_CONFIG)
    return paths


def resolve_config(paths: list[Path]) -> tuple[dict[str, Any], list[Path]]:
    config = default_config()
    used: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        config = deep_merge(config, read_json(path))
        used.append(path)
    config["resolved_at"] = utc_now()
    config["resolved_from"] = [str(path) for path in used]
    return config, used


def default_config() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "active_provider": "openai-gpt-image-2",
        "providers": [
            {
                "id": "openai-gpt-image-2",
                "type": "openai-compatible",
                "enabled": True,
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-image-2",
                "endpoint": "/images/generations",
                "default_size": "1024x1024",
                "default_quality": "auto",
                "supports_reference_images": True,
                "supports_edit": True,
                "supports_transparent_background": False,
                "approval_required_for": [
                    "sensitive_image_upload",
                    "paid_model_call",
                    "external_network",
                ],
                "notes": "Use base_url to point at an OpenAI-compatible relay or gateway.",
            },
            {
                "id": "openai-compatible-relay",
                "type": "openai-compatible",
                "enabled": False,
                "base_url": "https://your-relay.example.com/v1",
                "api_key_env": "OPENAI_RELAY_API_KEY",
                "model": "gpt-image-2",
                "endpoint": "/images/generations",
                "default_size": "1024x1024",
                "default_quality": "auto",
                "supports_reference_images": True,
                "supports_edit": True,
                "supports_transparent_background": False,
                "approval_required_for": [
                    "sensitive_image_upload",
                    "paid_model_call",
                    "external_network",
                ],
                "notes": "Relay/middleware provider. Verify compatibility, retention, logging, and pricing before use.",
            },
            {
                "id": "gemini-image",
                "type": "gemini",
                "enabled": False,
                "base_url": "https://generativelanguage.googleapis.com",
                "api_key_env": "GEMINI_API_KEY",
                "model": "gemini-image-model",
                "endpoint": "provider-specific",
                "default_size": "1024x1024",
                "default_quality": "auto",
                "supports_reference_images": True,
                "supports_edit": False,
                "supports_transparent_background": False,
                "approval_required_for": [
                    "sensitive_image_upload",
                    "paid_model_call",
                    "external_network",
                ],
                "notes": "Placeholder provider. Verify current Gemini image API model and endpoint before execution.",
            },
            {
                "id": "custom-http-image",
                "type": "custom-http",
                "enabled": False,
                "base_url": "https://image-gateway.example.com",
                "api_key_env": "IMAGE_GATEWAY_API_KEY",
                "model": "provider-model-name",
                "endpoint": "/generate",
                "default_size": "1024x1024",
                "default_quality": "auto",
                "supports_reference_images": False,
                "supports_edit": False,
                "supports_transparent_background": False,
                "approval_required_for": [
                    "sensitive_image_upload",
                    "paid_model_call",
                    "external_network",
                ],
                "notes": "Generic HTTP image provider. Implement a provider adapter before execution.",
            },
        ],
    }


def schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ImageGenerationConfig",
        "type": "object",
        "required": ["version", "active_provider", "providers"],
        "properties": {
            "version": {"type": "string"},
            "created_at": {"type": "string"},
            "updated_at": {"type": "string"},
            "active_provider": {"type": "string"},
            "providers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "type",
                        "enabled",
                        "base_url",
                        "api_key_env",
                        "model",
                        "endpoint",
                    ],
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"enum": sorted(SUPPORTED_PROVIDER_TYPES)},
                        "enabled": {"type": "boolean"},
                        "base_url": {"type": "string"},
                        "api_key_env": {"type": "string"},
                        "model": {"type": "string"},
                        "endpoint": {"type": "string"},
                        "default_size": {"type": "string"},
                        "default_quality": {"type": "string"},
                        "supports_reference_images": {"type": "boolean"},
                        "supports_edit": {"type": "boolean"},
                        "supports_transparent_background": {"type": "boolean"},
                        "approval_required_for": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "notes": {"type": "string"},
                    },
                    "additionalProperties": True,
                },
            },
        },
        "additionalProperties": True,
    }


def providers_by_id(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    providers = config.get("providers")
    if not isinstance(providers, list):
        raise ValueError("providers must be an array")
    by_id: dict[str, dict[str, Any]] = {}
    for provider in providers:
        if not isinstance(provider, dict):
            raise ValueError("each provider must be an object")
        provider_id = provider.get("id")
        if not provider_id:
            raise ValueError("provider missing id")
        if provider_id in by_id:
            raise ValueError(f"duplicate provider id: {provider_id}")
        by_id[provider_id] = provider
    return by_id


def validate_config(config: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    providers = providers_by_id(config)
    active_provider = config.get("active_provider")
    if active_provider not in providers:
        raise ValueError(f"active_provider not found: {active_provider}")

    for provider_id, provider in providers.items():
        provider_type = provider.get("type")
        if provider_type not in SUPPORTED_PROVIDER_TYPES:
            raise ValueError(f"{provider_id}: unsupported type {provider_type}")
        for field in ("base_url", "api_key_env", "model", "endpoint"):
            if not provider.get(field):
                raise ValueError(f"{provider_id}: missing {field}")
        if provider.get("enabled") and "paid_model_call" not in provider.get("approval_required_for", []):
            warnings.append(f"{provider_id}: enabled provider should require paid_model_call approval")
        if provider_type == "openai-compatible" and not provider.get("base_url", "").rstrip("/").endswith("/v1"):
            warnings.append(f"{provider_id}: OpenAI-compatible base_url usually ends with /v1")
        if provider_id == active_provider and not provider.get("enabled"):
            warnings.append(f"{provider_id}: active provider is disabled")
    return warnings


def init_config(args: argparse.Namespace) -> None:
    config_path = resolve_init_config_path(args)
    schema_path = resolve_init_schema_path(args)
    if config_path.exists() and not args.force:
        raise SystemExit(f"Config already exists: {config_path}")
    write_json(config_path, default_config())
    if schema_path:
        write_json(schema_path, schema())
    print(f"Wrote imagegen config: {config_path}")
    if schema_path:
        print(f"Wrote imagegen schema: {schema_path}")


def resolve_init_config_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "config", None)
    if explicit:
        return Path(explicit)
    scope = getattr(args, "scope", None)
    if scope == "global":
        return DEFAULT_GLOBAL_CONFIG
    if scope == "project":
        return Path(args.project_root) / DEFAULT_PROJECT_CONFIG
    if scope == "run":
        if not args.run_dir:
            raise SystemExit("--run-dir is required with --scope run.")
        return Path(args.run_dir) / DEFAULT_RUN_CONFIG
    raise SystemExit("Provide --config or --scope.")


def resolve_init_schema_path(args: argparse.Namespace) -> Path | None:
    explicit = getattr(args, "schema", None)
    if explicit:
        return Path(explicit)
    scope = getattr(args, "scope", None)
    if scope == "run":
        return Path(args.run_dir) / "schemas" / "imagegen.schema.json"
    return None


def validate_command(args: argparse.Namespace) -> None:
    config = load_command_config(args)
    warnings = validate_config(config)
    if args.config:
        print(f"Valid imagegen config: {args.config}")
    else:
        print("Valid resolved imagegen config")
        if config.get("resolved_from") is not None:
            print(f"Resolved from: {', '.join(config.get('resolved_from') or ['built-in defaults'])}")
    for warning in warnings:
        print(f"Warning: {warning}")


def list_command(args: argparse.Namespace) -> None:
    config = load_command_config(args)
    providers = providers_by_id(config)
    print(f"Active provider: {config.get('active_provider')}")
    if config.get("resolved_from") is not None:
        print(f"Resolved from: {', '.join(config.get('resolved_from') or ['built-in defaults'])}")
    for provider_id, provider in providers.items():
        enabled = "enabled" if provider.get("enabled") else "disabled"
        print(
            f"- {provider_id}: {provider.get('type')} {enabled}, "
            f"model={provider.get('model')}, base_url={provider.get('base_url')}, "
            f"api_key_env={provider.get('api_key_env')}"
        )


def set_active_command(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    config = read_json(config_path)
    providers = providers_by_id(config)
    if args.provider not in providers:
        raise SystemExit(f"Unknown provider: {args.provider}")
    config["active_provider"] = args.provider
    config["updated_at"] = utc_now()
    if args.enable:
        providers[args.provider]["enabled"] = True
    write_json(config_path, config)
    warnings = validate_config(config)
    print(f"Set active provider: {args.provider}")
    for warning in warnings:
        print(f"Warning: {warning}")


def load_command_config(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "config", None):
        return read_json(Path(args.config))
    paths = default_layer_paths(
        project_root=Path(args.project_root).resolve() if getattr(args, "project_root", None) else None,
        run_dir=Path(args.run_dir).resolve() if getattr(args, "run_dir", None) else None,
    )
    config, _ = resolve_config(paths)
    return config


def resolve_command(args: argparse.Namespace) -> None:
    paths: list[Path]
    if args.config:
        paths = [Path(item) for item in args.config]
    else:
        paths = default_layer_paths(
            project_root=Path(args.project_root).resolve() if args.project_root else None,
            run_dir=Path(args.run_dir).resolve() if args.run_dir else None,
        )
    config, used = resolve_config(paths)
    warnings = validate_config(config)
    if args.output:
        write_json(Path(args.output), config)
        print(f"Wrote resolved imagegen config: {args.output}")
    else:
        print(json.dumps(config, ensure_ascii=False, indent=2))
    print(f"Resolved layers: {', '.join(str(path) for path in used) or 'built-in defaults only'}")
    for warning in warnings:
        print(f"Warning: {warning}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Write a default imagegen config and schema.")
    init.add_argument("--config", help="Config output path.")
    init.add_argument("--schema", help="Schema output path.")
    init.add_argument("--scope", choices=("global", "project", "run"), help="Default config scope.")
    init.add_argument("--project-root", default=".", help="Project root for --scope project.")
    init.add_argument("--run-dir", help="Run directory for --scope run.")
    init.add_argument("--force", action="store_true", help="Overwrite existing files.")

    validate = subparsers.add_parser("validate", help="Validate imagegen config.")
    validate.add_argument("--config", help="Config path.")
    validate.add_argument("--project-root", help="Project root for layered resolution.")
    validate.add_argument("--run-dir", help="Run directory for layered resolution.")

    list_providers = subparsers.add_parser("list", help="List configured providers.")
    list_providers.add_argument("--config", help="Config path.")
    list_providers.add_argument("--project-root", help="Project root for layered resolution.")
    list_providers.add_argument("--run-dir", help="Run directory for layered resolution.")

    set_active = subparsers.add_parser("set-active", help="Set active provider.")
    set_active.add_argument("--config", required=True, help="Config path.")
    set_active.add_argument("--provider", required=True, help="Provider id.")
    set_active.add_argument("--enable", action="store_true", help="Enable provider while setting active.")

    resolve = subparsers.add_parser("resolve", help="Resolve layered imagegen config.")
    resolve.add_argument("--config", action="append", help="Config layer path. Can be repeated.")
    resolve.add_argument("--project-root", help="Project root for default project layer.")
    resolve.add_argument("--run-dir", help="Run directory for default run layer.")
    resolve.add_argument("--output", help="Write resolved config to this path.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            init_config(args)
        elif args.command == "validate":
            validate_command(args)
        elif args.command == "list":
            list_command(args)
        elif args.command == "set-active":
            set_active_command(args)
        elif args.command == "resolve":
            resolve_command(args)
        else:
            parser.error("Unknown command.")
            return 2
    except ValueError as error:
        raise SystemExit(f"Invalid imagegen config: {error}") from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
