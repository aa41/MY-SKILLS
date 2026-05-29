# Imagegen Config

Image generation is an independent workflow capability. It is configured through JSON provider definitions and can later be bound to a workflow node or skill.

The config stores provider metadata and environment variable names, not secret values.

## Files

```text
~/.config/multi-agent-dev-workflow/imagegen.json
.agent-workflows/config/imagegen.json
config/imagegen.json
schemas/imagegen.schema.json
manifests/model-versions.lock
```

## Precedence

Configuration is layered in this order:

1. built-in defaults
2. global config: `~/.config/multi-agent-dev-workflow/imagegen.json`
3. project config: `.agent-workflows/config/imagegen.json`
4. run config: `.agent-workflows/dev/<run-id>/config/imagegen.json`

Later layers override earlier layers. Provider entries merge by `id`, so a project config can override only `base_url`, `api_key_env`, `enabled`, or `active_provider` without copying the full default config.

## Provider Types

- `openai-compatible`: OpenAI image endpoint or a relay/gateway that exposes compatible routes. Use `base_url` for relay support.
- `gemini`: Gemini image provider placeholder. Verify the current model and endpoint before execution.
- `custom-http`: Generic image gateway placeholder. Requires a provider adapter before execution.

## Commands

```bash
python3 multi-agent-dev-workflow/scripts/imagegen_config.py init \
  --config .agent-workflows/dev/<run-id>/config/imagegen.json \
  --schema .agent-workflows/dev/<run-id>/schemas/imagegen.schema.json

python3 multi-agent-dev-workflow/scripts/imagegen_config.py init \
  --scope project \
  --project-root . \
  --force

python3 multi-agent-dev-workflow/scripts/imagegen_config.py validate \
  --config .agent-workflows/dev/<run-id>/config/imagegen.json

python3 multi-agent-dev-workflow/scripts/imagegen_config.py validate \
  --project-root . \
  --run-dir .agent-workflows/dev/<run-id>

python3 multi-agent-dev-workflow/scripts/imagegen_config.py resolve \
  --project-root . \
  --run-dir .agent-workflows/dev/<run-id> \
  --output /tmp/resolved-imagegen.json

python3 multi-agent-dev-workflow/scripts/imagegen_config.py list \
  --project-root . \
  --run-dir .agent-workflows/dev/<run-id>

python3 multi-agent-dev-workflow/scripts/imagegen_config.py set-active \
  --config .agent-workflows/dev/<run-id>/config/imagegen.json \
  --provider openai-compatible-relay \
  --enable
```

## Minimal Project Override Example

```json
{
  "active_provider": "openai-compatible-relay",
  "providers": [
    {
      "id": "openai-compatible-relay",
      "enabled": true,
      "base_url": "https://relay.example.com/v1",
      "api_key_env": "RELAY_IMAGE_API_KEY",
      "model": "gpt-image-2"
    }
  ]
}
```

This overrides only the relay provider and leaves the rest of the default provider definitions intact.

## Safety

- Do not store raw API keys in config.
- Use `api_key_env` to name the environment variable.
- Keep `paid_model_call`, `external_network`, and `sensitive_image_upload` approval gates enabled.
- Treat relay/gateway providers as separate trust boundaries. Verify logging, retention, pricing, model compatibility, and output rights before use.
