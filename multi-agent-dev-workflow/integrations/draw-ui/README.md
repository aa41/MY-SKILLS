# draw-ui integration

Internal UI mockup and walkthrough capability for `multi-agent-dev-workflow`.
This directory is not a standalone skill. Normal execution goes through `multi-agent-dev-workflow/scripts/workflow_runner.py`.

---

## What it does

- Generates high-quality UI mockups from natural language descriptions
- Locks navigation/sidebar consistency across multiple screens using a reference image
- Uses proven prompt techniques (analogy-style or inventory-style) for better design quality
- Uses the workflow's configured image provider instead of hard-coded provider credentials
- Guides HTML reconstruction with asset strategy, browser screenshot comparison, and background-removal rules for logos and illustrations

## Requirements

- For scripted image generation: a workflow `imagegen.json` with an `openai-compatible` or `custom-http` provider. The provider's `api_key_env` names the required environment variable; raw keys are never stored in config.
- Python 3

## Usage

Inside a workflow run, use the runner-managed command:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py generate-ui-image \
  --run-dir .agent-workflows/dev/<run-id> \
  --provider openai-gpt-image-2 \
  --type wide \
  --name dashboard \
  --prompt "..."
```

The runner checks image-generation approval, reads run-level `config/imagegen.json`, invokes the internal adapter, and records output artifacts/events.

For HTML reconstruction, use:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py replicate-ui-html \
  --run-dir .agent-workflows/dev/<run-id> \
  --reference artifacts/design/generated/dashboard.png \
  --name dashboard \
  --html-file /tmp/dashboard.html
```

Then verify the result:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py verify-ui-html \
  --run-dir .agent-workflows/dev/<run-id> \
  --html artifacts/implementation/html/dashboard.html \
  --reference artifacts/design/generated/dashboard.png \
  --out-dir artifacts/validation/ui-html/dashboard
```

If no HTML is ready yet, run `replicate-ui-html` without `--html-file` to create a prompt package for a human or subagent. If `agent-browser` is unavailable, use `verify-ui-html --candidate-screenshot` with an existing browser screenshot.

The workflow may trigger this capability for requests like:

> 帮我设计一个 Dashboard 页面  
> Design a user profile screen  
> 出图，产品详情页

The agent will ask you a few questions first (what the page does, whether you have a reference screenshot, consistency requirements), then generate.

### Low-level adapter usage

```bash
# No reference image
multi-agent-dev-workflow/integrations/draw-ui/scripts/ask_draw.sh \
  --imagegen-config .agent-workflows/dev/<run-id>/config/imagegen.json \
  --provider openai-gpt-image-2 \
  --type wide \
  --name "dashboard" \
  --prompt "..."

# With reference image (locks sidebar/nav consistency)
multi-agent-dev-workflow/integrations/draw-ui/scripts/ask_draw.sh \
  --imagegen-config .agent-workflows/dev/<run-id>/config/imagegen.json \
  --provider openai-gpt-image-2 \
  --frame /path/to/sidebar-reference.png \
  --type wide \
  --name "dashboard" \
  --prompt "..."
```

When debugging the adapter directly, always pass the run config explicitly:

```bash
multi-agent-dev-workflow/integrations/draw-ui/scripts/ask_draw.sh \
  --imagegen-config .agent-workflows/dev/<run-id>/config/imagegen.json \
  --provider openai-gpt-image-2 \
  --type wide \
  --name dashboard \
  --prompt "..."
```

### Aspect ratio options

| `--type` | Ratio | Use case |
|----------|-------|----------|
| `wide` | 16:9 | Desktop app screens (default) |
| `classic` | 4:3 | Dashboard, data-heavy layouts |
| `square` | 1:1 | Cards, modals |
| `portrait` | 3:4 | Mobile screens |

## Key concepts

**Reference image strategy**

The reference image constrains what AI will copy. If your screenshot has existing content in the main area, AI will mimic that layout — limiting creative freedom.

Best practice: use a "clean frame" — a screenshot with only the sidebar/nav visible and the content area blank. This lets AI keep your chrome consistent while designing the content area freely.

**Prompt writing**

Don't write layout specs (pixels, columns, padding). Instead, describe the *business* using one of two approaches:

- **Analogy** — "Like reading the sheet music behind a hit song. Think Notion's calm meets a music producer's notes." → best for creative quality
- **Inventory** — "The page shows: user name, 30-day trend chart, active campaigns list with status badges." → most reliable for accuracy

Always use real example data instead of placeholders. `"2.3M views"` produces a far more realistic output than `"show view count"`.

**HTML reconstruction**

When turning a generated mockup or screenshot into HTML/CSS, split the work into code and assets:

- Build layout, cards, buttons, text, filters, and ordinary line icons with HTML/CSS/SVG.
- Generate standalone image assets for brand logos, empty-state illustrations, glassy/3D visuals, complex gradients, and other hard-to-code visual details. Use crops only as references for image-to-image redraw, not as final assets unless the source is already high-resolution and background-clean.
- Do not mix large illustrations, logos, and small icons in the same sprite sheet. Generate large illustration assets separately.
- For vendor logo rows, dark wordmarks, and small dark icons, generate a large pure-white source image and remove the white background conservatively. This avoids green fringing and protects thin strokes.
- For colorful illustrations and product visuals, use green-screen or real transparent output when available; white-background keying can damage white cards and highlights.
- If an icon sprite sheet is needed, make it machine-cuttable: pure white background, exact 4x4 grid, no borders, no labels, no shadows, no overlap, and each icon centered with wide padding.

This keeps the HTML clean while preserving the visual parts that image generation is best at.

## License

MIT
