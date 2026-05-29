---
name: multi-agent-dev-workflow
description: Artifact-first multi-agent development workflow runner. Use when moving from research into implementation planning, creating a local workflow run, defining workflow/state/event/approval/skill manifest contracts, or scaffolding a controlled dev workflow that can later connect Codex subagents, image UI generation, UI replication, implementation agents, and QA gates.
---

# Multi-Agent Dev Workflow

## Overview

This skill implements the practical development workflow described by the multi-agent research run.

The first implementation is intentionally narrow:

- Create a repo-local development workflow run directory.
- Persist `requirement.md`, `workflow.yaml`, `state.json`, `events.jsonl`, approval artifacts, docs placeholders, logs, and lockfiles.
- Support `run`, `status`, `resume`, `start-docs`, `record`, `start-design`, `record-design`, `start-ui-replication`, `record-ui-replication`, `start-business-logic`, and `record-business-logic` commands.
- Keep all high-impact actions behind explicit approval gates.

It does not directly edit business code, install dependencies, call external systems, generate images, update visual baselines, or deploy. Those capabilities must be added later as explicit workflow nodes with manifest permissions and approval boundaries.

## Quick Start

Create a workflow run:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py run \
  --requirement "Build a multi-agent workflow MVP" \
  --project-root .
```

Check status:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py status \
  --run-dir .agent-workflows/dev/<run-id>
```

Approve or reject the initial scope gate:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py resume \
  --run-dir .agent-workflows/dev/<run-id> \
  --approval approval-scope-001 \
  --decision approve \
  --comment "Scope accepted for docs MVP."
```

Start the research/docs phase:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py start-docs \
  --run-dir .agent-workflows/dev/<run-id>
```

Record a role output:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py record \
  --run-dir .agent-workflows/dev/<run-id> \
  --role researcher-product \
  --file /tmp/researcher-product.md
```

Start design generation planning after docs approval:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py start-design \
  --run-dir .agent-workflows/dev/<run-id>
```

Record a design role output:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py record-design \
  --run-dir .agent-workflows/dev/<run-id> \
  --role imagegen-prompt-engineer \
  --file /tmp/imagegen-prompt-plan.md
```

Start UI replication planning after imagegen approval:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py start-ui-replication \
  --run-dir .agent-workflows/dev/<run-id>
```

Record a UI replication role output:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py record-ui-replication \
  --run-dir .agent-workflows/dev/<run-id> \
  --role ui-replication-planner \
  --file /tmp/ui-replication-plan.md
```

Start business logic planning after UI replication approval:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py start-business-logic \
  --run-dir .agent-workflows/dev/<run-id>
```

Record a business logic role output:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py record-business-logic \
  --run-dir .agent-workflows/dev/<run-id> \
  --role logic-implementation-planner \
  --file /tmp/logic-implementation-plan.md
```

## Run Directory

```text
.agent-workflows/
  dev/
    <run-id>/
      index.md
      requirement.md
      workflow.yaml
      state.json
      events.jsonl
      permissions.yaml
      config/
        imagegen.json
      schemas/
        state.schema.json
        event.schema.json
        skill-manifest.schema.json
        imagegen.schema.json
      docs/
        prd.md
        design-brief.md
        technical-design.md
        task-plan.md
        acceptance.md
      approvals/
        approval-scope-001.md
        approval-docs-001.md
      prompts/
        researcher-product.md
        researcher-architecture.md
        researcher-risk.md
        docs-synthesizer.md
        evidence-reviewer.md
        decision-reviewer.md
      artifacts/
        research/
          01-product-research.md
          02-architecture-research.md
          03-risk-research.md
          04-docs-synthesis.md
          05-evidence-review.md
          06-decision-review.md
        design/
          01-design-requirement-map.md
          02-imagegen-prompt-plan.md
          03-visual-qa-plan.md
          imagegen-resolved.json
          imagegen-dry-run-plan.json
          generated/
        implementation/
          01-ui-source-audit.md
          02-ui-replication-plan.md
          03-logic-contract-map.md
          04-logic-implementation-plan.md
          ui-replication-dry-run-plan.json
          business-logic-dry-run-plan.json
        validation/
          01-ui-validation-plan.md
          02-logic-test-plan.md
        acceptance/
      manifests/
        skills.lock
        subagents.lock
        model-versions.lock
      logs/
        tool-calls.jsonl
        agent-runs.md
        errors.md
```

## Safety Rules

- Artifact files are the source of truth; chat history is not.
- Append events to `events.jsonl`; do not rely only on `state.json`.
- Default permissions are deny.
- Researchers and reviewers should be read-only.
- Implementers require workspace-write and explicit scope.
- External writes, dependency installs, production data access, deployments, visual baseline updates, and image uploads containing sensitive material require approval.
- Test and acceptance agents must be independent from implementation agents.

## Current Scope

Implemented:

- Phase 0/1 scaffolding.
- Phase 2 research/docs prompt and artifact scaffolding.
- Phase 3 design generation planning with imagegen dry-run artifacts.
- Phase 4 UI replication planning with code-write approval gate.
- Phase 5 business logic planning with implementation/testing approval gate.
- Independent imagegen provider config for OpenAI-compatible APIs, relay/gateway services, Gemini placeholders, and custom HTTP providers.
- Local state and event ledger.
- Initial scope approval gate.
- Status and resume command.
- Role output recording and docs approval gate creation.
- Design role output recording and imagegen approval gate creation.
- UI replication role output recording and code-write approval gate creation.
- Business logic role output recording and implementation/testing approval gate creation.
- JSON schema artifacts for state, events, and skill manifests.

## Image Generation Config

Image generation is configured independently from workflow execution. The runner creates:

- `config/imagegen.json`
- `schemas/imagegen.schema.json`

Config is layered:

1. built-in defaults
2. global: `~/.config/multi-agent-dev-workflow/imagegen.json`
3. project: `.agent-workflows/config/imagegen.json`
4. run: `.agent-workflows/dev/<run-id>/config/imagegen.json`

The config supports these provider types:

- `openai-compatible`: OpenAI image endpoint or a relay/gateway with compatible routes. Set `base_url` to the relay URL, such as `https://your-relay.example.com/v1`.
- `gemini`: Gemini image provider placeholder. Verify current model and endpoint before implementing execution.
- `custom-http`: Generic image gateway placeholder for self-hosted or third-party image services.

Secrets are not stored in config. Use `api_key_env` to name the environment variable.

Commands:

```bash
python3 multi-agent-dev-workflow/scripts/imagegen_config.py list \
  --project-root . \
  --run-dir .agent-workflows/dev/<run-id>

python3 multi-agent-dev-workflow/scripts/imagegen_config.py resolve \
  --project-root . \
  --run-dir .agent-workflows/dev/<run-id> \
  --output /tmp/resolved-imagegen.json

python3 multi-agent-dev-workflow/scripts/imagegen_config.py set-active \
  --config .agent-workflows/dev/<run-id>/config/imagegen.json \
  --provider openai-compatible-relay \
  --enable

python3 multi-agent-dev-workflow/scripts/imagegen_config.py validate \
  --project-root . \
  --run-dir .agent-workflows/dev/<run-id>
```

Deferred:

- Native subagent execution.
- LangGraph integration.
- Actual gpt-image-2, Gemini, relay, or custom image model calls.
- Figma MCP integration.
- Playwright execution.
- Business code modification.
- GitHub/Linear/Jira synchronization.
- Temporal durable execution.
