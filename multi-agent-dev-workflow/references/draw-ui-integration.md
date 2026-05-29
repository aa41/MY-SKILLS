# Draw UI Integration

`multi-agent-dev-workflow/integrations/draw-ui` is included inside this skill as the UI mockup and UI walkthrough integration for `multi-agent-dev-workflow`.

## Current Scope

- Generate UI mockup images through the workflow `config/imagegen.json`.
- Reconstruct image or screenshot mockups into HTML/CSS.
- Verify HTML reconstruction with browser screenshots and pixel comparison.

## Image Provider Contract

`draw-ui` does not read hard-coded API key names. Normal workflow execution uses:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py generate-ui-image \
  --run-dir .agent-workflows/dev/<run-id> \
  --provider openai-gpt-image-2 \
  --type wide \
  --name primary-ui \
  --prompt "..." \
  --output artifacts/design/generated/primary-ui.png
```

The runner validates the run state, checks `approval-imagegen-001` unless `--force` is used for a local smoke test, resolves run-level `config/imagegen.json`, then calls `integrations/draw-ui/scripts/ask_draw.sh`.

The provider must have:

- `type`: `openai-compatible` or `custom-http`
- `api_key_env`: environment variable name to read at runtime
- `model`: image model name, for example `gpt-image-2`
- `base_url`: provider or gateway URL
- `endpoint`: generation endpoint, for example `/images/generations`

Raw API keys must not be stored in repository files or workflow artifacts.

## Workflow Binding

Design generation writes:

- `artifacts/design/imagegen-resolved.json`
- `artifacts/design/imagegen-dry-run-plan.json`
- `artifacts/design/generated/*.png`
- `artifacts/design/generated/*.png.json`

UI replication consumes generated images and writes:

- `artifacts/implementation/html/`
- `artifacts/validation/`

## Target Replication Roadmap

Current implementation target:

- image or screenshot to HTML/CSS

Planned adapters:

- HTML to Flutter UI
- HTML to Android native UI
- HTML to iOS native UI

These adapters should be separate workflow nodes with their own artifacts, validation plans, and approval gates. They should not be hidden inside image generation.

## Verification

HTML verification uses:

- `multi-agent-dev-workflow/integrations/draw-ui/scripts/verify_html_mockup.sh`
- `multi-agent-dev-workflow/integrations/draw-ui/scripts/compare_mockup.py`

Future native UI verification should add platform-specific screenshot capture and compare against the same reference mockups.
