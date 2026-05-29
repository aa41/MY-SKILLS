# Workflow Contract

This document describes the MVP contract implemented by `scripts/workflow_runner.py`.

## Principles

- Artifact files are the source of truth.
- `state.json` is the current machine-readable snapshot.
- `events.jsonl` is the append-only event ledger.
- Approval decisions are persisted as Markdown artifacts and reflected in state.
- Permission defaults are deny.

## Status Values

- `initialized`
- `waiting_for_approval`
- `ready`
- `running`
- `partial`
- `failed`
- `completed`
- `cancelled`

## Initial Gate

Every run starts with `approval-scope-001`.

- `approve` moves the run to `ready` / `research_docs`.
- `reject` moves the run to `cancelled` / `scope_rejected`.

## Research / Docs Phase

`start-docs` creates prompts and artifact placeholders for six roles:

- `researcher-product`
- `researcher-architecture`
- `researcher-risk`
- `docs-synthesizer`
- `evidence-reviewer`
- `decision-reviewer`

Role outputs are recorded with `record`.

When all six roles have `success` status, the runner creates `approval-docs-001` and moves the run to `waiting_for_approval` / `docs_approval`.

- approving `approval-docs-001` moves the run to `ready` / `design_generation`
- rejecting `approval-docs-001` moves the run to `cancelled` / `docs_approval_rejected`

## Design Generation Phase

`start-design` creates prompts and artifact placeholders for three roles:

- `design-requirement-mapper`
- `imagegen-prompt-engineer`
- `visual-qa-reviewer`

It also validates `config/imagegen.json` and writes dry-run artifacts:

- `artifacts/design/imagegen-resolved.json`
- `artifacts/design/imagegen-dry-run-plan.json`

No external image generation API is called by `start-design`.

Design role outputs are recorded with `record-design`.

When all three design roles have `success` status and the dry-run plan exists, the runner creates `approval-imagegen-001` and moves the run to `waiting_for_approval` / `imagegen_approval`.

- approving `approval-imagegen-001` moves the run to `ready` / `ui_replication`
- rejecting `approval-imagegen-001` moves the run to `cancelled` / `imagegen_approval_rejected`

## UI Replication Phase

`start-ui-replication` creates prompts and artifact placeholders for three roles:

- `ui-source-auditor`
- `ui-replication-planner`
- `ui-validation-planner`

It also writes:

- `artifacts/implementation/ui-replication-dry-run-plan.json`

No product code is edited by `start-ui-replication`.

UI replication role outputs are recorded with `record-ui-replication`.

When all three UI replication roles have `success` status and the dry-run plan exists, the runner creates `approval-ui-replication-001` and moves the run to `waiting_for_approval` / `ui_replication_approval`.

- approving `approval-ui-replication-001` moves the run to `ready` / `business_logic`
- rejecting `approval-ui-replication-001` moves the run to `cancelled` / `ui_replication_approval_rejected`

## Business Logic Phase

`start-business-logic` creates prompts and artifact placeholders for three roles:

- `logic-contract-mapper`
- `logic-implementation-planner`
- `logic-test-planner`

It also writes:

- `artifacts/implementation/business-logic-dry-run-plan.json`

No product code, dependencies, migrations, tests, or external systems are changed by `start-business-logic`.

Business logic role outputs are recorded with `record-business-logic`.

When all three business logic roles have `success` status and the dry-run plan exists, the runner creates `approval-business-logic-001` and moves the run to `waiting_for_approval` / `business_logic_approval`.

- approving `approval-business-logic-001` moves the run to `ready` / `acceptance`
- rejecting `approval-business-logic-001` moves the run to `cancelled` / `business_logic_approval_rejected`

## Implementation Evidence and Self-Test Execution

After `approval-business-logic-001` is approved, implementation evidence can be recorded with:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py record-implementation \
  --run-dir .agent-workflows/dev/<run-id> \
  --name <implementation-name> \
  --summary-file <summary.md> \
  --touched-file <path>
```

This writes an implementation manifest under `artifacts/implementation/`, updates `state.json`, and appends events. If no summary, touched files, or patch evidence are provided, it creates a prompt package with `pending_implementation` status.

Self-tests are explicit commands only:

```bash
python3 multi-agent-dev-workflow/scripts/workflow_runner.py run-self-test \
  --run-dir .agent-workflows/dev/<run-id> \
  --name <test-name> \
  --cwd <project-root> \
  -- <test-command>
```

The runner stores stdout, stderr, return code, and a manifest under `artifacts/validation/self-tests/`. It does not install dependencies, rewrite tests, run migrations, or call external services unless the provided command does so under a separate approval.

## Acceptance Phase

`start-acceptance` creates prompts and artifact placeholders for three roles:

- `acceptance-matrix-author`
- `evidence-completeness-reviewer`
- `final-acceptance-reporter`

It also writes:

- `artifacts/acceptance/acceptance-dry-run-plan.json`

No deployment, external write, production data access, product code mutation, test mutation, or baseline update is performed by `start-acceptance`.

Acceptance role outputs are recorded with `record-acceptance`. Recording `acceptance-matrix-author` also updates `docs/acceptance.md`.

When all three acceptance roles have `success` status and the dry-run plan exists, the runner creates `approval-acceptance-001` and moves the run to `waiting_for_approval` / `final_acceptance`.

- approving `approval-acceptance-001` moves the run to `completed` / `completed`
- rejecting `approval-acceptance-001` moves the run to `cancelled` / `final_acceptance_rejected`

## Deferred Nodes

The MVP deliberately does not execute subagents, install dependencies, run migrations, deploy, or perform external sync. Image generation, UI replication handoff, implementation evidence, and self-test evidence are explicit workflow nodes with:

- input artifact paths
- output artifact paths
- permissions
- approval boundaries
- failure semantics
- event emission
