#!/usr/bin/env python3
"""Local artifact-first multi-agent development workflow runner."""

from __future__ import annotations

import argparse
import json
import re
import importlib.util
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MODE = "auto-until-approval"
DEFAULT_APPROVAL_ID = "approval-scope-001"
DOCS_APPROVAL_ID = "approval-docs-001"
IMAGEGEN_APPROVAL_ID = "approval-imagegen-001"
UI_REPLICATION_APPROVAL_ID = "approval-ui-replication-001"
BUSINESS_LOGIC_APPROVAL_ID = "approval-business-logic-001"
ACCEPTANCE_APPROVAL_ID = "approval-acceptance-001"
TERMINAL_APPROVAL_DECISIONS = {"approve", "reject"}

DOC_ROLE_DEFINITIONS = [
    {
        "id": "researcher-product",
        "title": "Product Researcher",
        "phase": "research_docs",
        "artifact": "artifacts/research/01-product-research.md",
        "prompt": """You are the Product Researcher for an artifact-first multi-agent development workflow.

Read `requirement.md`, `workflow.yaml`, and `permissions.yaml`.

Focus on:
- User goals, user-facing workflows, acceptance criteria, and non-goals.
- Product risks, scope boundaries, open questions, and docs required before implementation.
- Evidence from local artifacts or authoritative sources when available.

Write a complete Markdown artifact with findings, recommended PRD inputs, rejected assumptions, and confidence.
""",
    },
    {
        "id": "researcher-architecture",
        "title": "Architecture Researcher",
        "phase": "research_docs",
        "artifact": "artifacts/research/02-architecture-research.md",
        "prompt": """You are the Architecture Researcher for an artifact-first multi-agent development workflow.

Read `requirement.md`, `workflow.yaml`, and `permissions.yaml`.

Focus on:
- Architecture constraints, repo integration assumptions, data flow, APIs, dependencies, and implementation sequencing.
- What must be verified in the target repo before code changes.
- Technical risks and tests required before implementation.

Write a complete Markdown artifact with findings, recommended technical-design inputs, rejected options, and confidence.
""",
    },
    {
        "id": "researcher-risk",
        "title": "Risk Researcher",
        "phase": "research_docs",
        "artifact": "artifacts/research/03-risk-research.md",
        "prompt": """You are the Risk Researcher for an artifact-first multi-agent development workflow.

Read `requirement.md`, `workflow.yaml`, and `permissions.yaml`.

Focus on:
- Security, privacy, permissions, prompt injection, supply chain, concurrency, rollback, testing, and approval boundaries.
- Which actions must stay behind human gates.
- Missing validation or compliance evidence.

Write a complete Markdown artifact with risk findings, mitigations, decision blockers, and confidence.
""",
    },
    {
        "id": "docs-synthesizer",
        "title": "Docs Synthesizer",
        "phase": "research_docs",
        "artifact": "artifacts/research/04-docs-synthesis.md",
        "prompt": """You are the Docs Synthesizer.

Read the three researcher artifacts under `artifacts/research/` plus `requirement.md`.

Create implementation-ready drafts for:
- `docs/prd.md`
- `docs/design-brief.md`
- `docs/technical-design.md`
- `docs/task-plan.md`

Do not edit code. If you cannot write those docs directly, return complete Markdown sections that the orchestrator can copy into the docs files.
""",
    },
    {
        "id": "evidence-reviewer",
        "title": "Evidence Reviewer",
        "phase": "research_docs",
        "artifact": "artifacts/research/05-evidence-review.md",
        "prompt": """You are the Evidence Reviewer.

Audit the researcher and docs-synthesis artifacts.

Focus on:
- Unsupported claims, stale assumptions, missing repo evidence, missing official docs, contradictions, and hallucination risk.
- Which claims are safe to use before implementation.
- What must be verified before code writes, image generation, Figma use, or external system access.

Write a complete Markdown evidence audit.
""",
    },
    {
        "id": "decision-reviewer",
        "title": "Decision Reviewer",
        "phase": "research_docs",
        "artifact": "artifacts/research/06-decision-review.md",
        "prompt": """You are the Decision Reviewer.

Compare the research/docs artifacts and choose the next implementation path.

Focus on:
- Feasibility, scope control, blast radius, sequencing, approval gates, and testing.
- What should be done next and what should be deferred.
- Whether docs are ready for human approval.

Write a complete Markdown decision audit with a clear recommendation and confidence.
""",
    },
]

DOC_ARTIFACT_TO_DOC_TARGET = {
    "docs/prd.md": "PRD",
    "docs/design-brief.md": "Design Brief",
    "docs/technical-design.md": "Technical Design",
    "docs/task-plan.md": "Task Plan",
}

DESIGN_ROLE_DEFINITIONS = [
    {
        "id": "design-requirement-mapper",
        "title": "Design Requirement Mapper",
        "phase": "design_generation",
        "artifact": "artifacts/design/01-design-requirement-map.md",
        "prompt": """You are the Design Requirement Mapper.

Read `requirement.md`, `docs/prd.md`, `docs/design-brief.md`, `docs/technical-design.md`, and `docs/task-plan.md`.

Focus on:
- Screens, user states, empty/error/loading states, and responsive/device requirements.
- Data that must be visible in each screen and interactions that must be represented in design.
- Non-goals and scope boundaries that should not appear in the generated UI.

Write a complete Markdown artifact with screen inventory, state matrix, design constraints, and unresolved questions.
""",
    },
    {
        "id": "imagegen-prompt-engineer",
        "title": "Imagegen Prompt Engineer",
        "phase": "design_generation",
        "artifact": "artifacts/design/02-imagegen-prompt-plan.md",
        "prompt": """You are the Imagegen Prompt Engineer.

Read the design docs, `config/imagegen.json`, and `artifacts/design/01-design-requirement-map.md`.

Focus on:
- Provider-neutral image generation prompts for UI mockups.
- Aspect ratios, screen sizes, visual style, negative prompts, reference-image needs, and batch naming.
- Which prompts are safe to run automatically and which require human review.

Do not call image generation APIs. Write a complete Markdown prompt plan.
""",
    },
    {
        "id": "visual-qa-reviewer",
        "title": "Visual QA Reviewer",
        "phase": "design_generation",
        "artifact": "artifacts/design/03-visual-qa-plan.md",
        "prompt": """You are the Visual QA Reviewer.

Read the design requirement map and imagegen prompt plan.

Focus on:
- Criteria for accepting generated UI mockups.
- Risks around text legibility, hallucinated UI controls, brand drift, inaccessible contrast, and unsupported workflows.
- Evidence required before UI replication starts.

Write a complete Markdown review checklist and decision recommendation.
""",
    },
]

UI_REPLICATION_ROLE_DEFINITIONS = [
    {
        "id": "ui-source-auditor",
        "title": "UI Source Auditor",
        "phase": "ui_replication",
        "artifact": "artifacts/implementation/01-ui-source-audit.md",
        "prompt": """You are the UI Source Auditor.

Read `requirement.md`, docs under `docs/`, design artifacts under `artifacts/design/`, and any generated images under `artifacts/design/generated/`.

Focus on:
- Which design sources are available, missing, stale, or unsafe to use.
- What can be implemented from artifacts alone and what requires human clarification.
- Risks around hallucinated UI, missing states, unresolved visual direction, and inaccessible designs.

Do not edit product code. Write a complete Markdown source audit.
""",
    },
    {
        "id": "ui-replication-planner",
        "title": "UI Replication Planner",
        "phase": "ui_replication",
        "artifact": "artifacts/implementation/02-ui-replication-plan.md",
        "prompt": """You are the UI Replication Planner.

Read `docs/technical-design.md`, `docs/design-brief.md`, and the UI source audit.

Focus on:
- Mapping screens and visual states to target files, components, routes, widgets, styles, and assets.
- Implementation order, reusable component boundaries, and fallback behavior when images are missing.
- What must stay behind code-write, dependency-install, or visual-baseline approval gates.

Do not edit product code. Write an implementation-ready UI replication plan.
""",
    },
    {
        "id": "ui-validation-planner",
        "title": "UI Validation Planner",
        "phase": "ui_replication",
        "artifact": "artifacts/validation/01-ui-validation-plan.md",
        "prompt": """You are the UI Validation Planner.

Read the UI source audit and UI replication plan.

Focus on:
- Functional checks, screenshot checks, accessibility checks, responsive viewports, and visual diff policy.
- Which validations can run automatically and which require human visual approval.
- Required evidence before moving into business logic or code-writing execution.

Do not run tests or update baselines. Write a complete validation plan.
""",
    },
]

BUSINESS_LOGIC_ROLE_DEFINITIONS = [
    {
        "id": "logic-contract-mapper",
        "title": "Logic Contract Mapper",
        "phase": "business_logic",
        "artifact": "artifacts/implementation/03-logic-contract-map.md",
        "prompt": """You are the Logic Contract Mapper.

Read `requirement.md`, docs under `docs/`, UI replication artifacts under `artifacts/implementation/`, and validation artifacts under `artifacts/validation/`.

Focus on:
- Business rules, domain entities, state transitions, API/data contracts, and edge cases.
- Which behavior belongs in UI state, service/domain logic, persistence, or integration boundaries.
- Ambiguities that must be resolved before implementation.

Do not edit product code. Write a complete Markdown logic contract map.
""",
    },
    {
        "id": "logic-implementation-planner",
        "title": "Logic Implementation Planner",
        "phase": "business_logic",
        "artifact": "artifacts/implementation/04-logic-implementation-plan.md",
        "prompt": """You are the Logic Implementation Planner.

Read `docs/technical-design.md`, `docs/task-plan.md`, and the logic contract map.

Focus on:
- Target files/modules, data flow, interfaces, persistence, error handling, and sequencing.
- Migration, dependency, and external integration risks.
- A scoped implementation plan that can be executed only after approval.

Do not edit product code. Write an implementation-ready business logic plan.
""",
    },
    {
        "id": "logic-test-planner",
        "title": "Logic Test Planner",
        "phase": "business_logic",
        "artifact": "artifacts/validation/02-logic-test-plan.md",
        "prompt": """You are the Logic Test Planner.

Read the logic contract map and implementation plan.

Focus on:
- Unit, integration, contract, regression, and acceptance tests.
- Fixtures, mocks, environment assumptions, failure cases, and manual verification.
- Evidence required before final acceptance.

Do not run tests or change assertions. Write a complete logic test plan.
""",
    },
]

ACCEPTANCE_ROLE_DEFINITIONS = [
    {
        "id": "acceptance-matrix-author",
        "title": "Acceptance Matrix Author",
        "phase": "acceptance",
        "artifact": "artifacts/acceptance/01-acceptance-matrix.md",
        "prompt": """You are the Acceptance Matrix Author.

Read `requirement.md`, docs under `docs/`, implementation plans under `artifacts/implementation/`, and validation plans under `artifacts/validation/`.

Focus on:
- Requirement-to-evidence traceability.
- Acceptance criteria, expected evidence, owners, blockers, and manual review points.
- Gaps that prevent final acceptance.

Do not edit product code or mark work complete without evidence. Write a complete acceptance matrix.
""",
    },
    {
        "id": "evidence-completeness-reviewer",
        "title": "Evidence Completeness Reviewer",
        "phase": "acceptance",
        "artifact": "artifacts/acceptance/02-evidence-completeness-review.md",
        "prompt": """You are the Evidence Completeness Reviewer.

Audit the workflow artifacts, plans, approvals, and event ledger.

Focus on:
- Missing evidence, unsupported completion claims, failed/partial nodes, unresolved approvals, and test gaps.
- Whether the workflow can be accepted as complete or must return to an earlier phase.
- Residual risks that must be carried forward.

Do not edit product code. Write a complete evidence review.
""",
    },
    {
        "id": "final-acceptance-reporter",
        "title": "Final Acceptance Reporter",
        "phase": "acceptance",
        "artifact": "artifacts/acceptance/03-final-acceptance-report.md",
        "prompt": """You are the Final Acceptance Reporter.

Read the acceptance matrix and evidence completeness review.

Focus on:
- Final status recommendation, accepted scope, rejected/deferred scope, known risks, and next release/workflow steps.
- A concise summary suitable for human sign-off.
- Clear recommendation: approve, reject, or return to a previous phase.

Do not edit product code. Write a final acceptance report.
""",
    },
]

IMAGEGEN_CONFIG_MODULE_PATH = Path(__file__).with_name("imagegen_config.py")
DRAW_UI_ASK_SCRIPT = Path(__file__).resolve().parents[1] / "integrations" / "draw-ui" / "scripts" / "ask_draw.sh"
DRAW_UI_VERIFY_SCRIPT = (
    Path(__file__).resolve().parents[1] / "integrations" / "draw-ui" / "scripts" / "verify_html_mockup.sh"
)
DRAW_UI_COMPARE_SCRIPT = (
    Path(__file__).resolve().parents[1] / "integrations" / "draw-ui" / "scripts" / "compare_mockup.py"
)
DRAW_UI_HTML_REFERENCE = (
    Path(__file__).resolve().parents[1] / "integrations" / "draw-ui" / "references" / "html-reconstruction.md"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "workflow") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or fallback


def read_requirement(args: argparse.Namespace) -> str:
    if args.requirement and args.file:
        raise SystemExit("Use either --requirement or --file, not both.")
    if args.file:
        return Path(args.file).read_text(encoding="utf-8").strip()
    if args.requirement:
        return args.requirement.strip()
    raise SystemExit("Provide --requirement or --file.")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_text_arg(*, file: str | None, content: str | None, label: str) -> str:
    if file and content:
        raise SystemExit(f"Use either --{label}-file or --{label}, not both.")
    if file:
        return Path(file).read_text(encoding="utf-8")
    return content or ""


def display_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def load_imagegen_config_module() -> Any:
    spec = importlib.util.spec_from_file_location("imagegen_config", IMAGEGEN_CONFIG_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load imagegen config module: {IMAGEGEN_CONFIG_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def append_event(run_dir: Path, event_type: str, **fields: Any) -> None:
    event = {"ts": utc_now(), "type": event_type, **fields}
    events_path = run_dir / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def load_state(run_dir: Path) -> dict[str, Any]:
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise SystemExit(f"Missing state file: {state_path}")
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    write_text(run_dir / "state.json", json.dumps(state, ensure_ascii=False, indent=2))


def initial_state(run_id: str, mode: str, requirement_path: str) -> dict[str, Any]:
    now = utc_now()
    return {
        "run_id": run_id,
        "created_at": now,
        "updated_at": now,
        "status": "waiting_for_approval",
        "current_phase": "scope_approval",
        "mode": mode,
        "requirement_path": requirement_path,
        "workflow_path": "workflow.yaml",
        "permissions_path": "permissions.yaml",
        "events_path": "events.jsonl",
        "nodes": {
            "intake": {
                "status": "success",
                "artifact": requirement_path,
                "started_at": now,
                "finished_at": now,
            },
            "scope_approval": {
                "status": "waiting_for_approval",
                "artifact": f"approvals/{DEFAULT_APPROVAL_ID}.md",
                "started_at": now,
                "finished_at": None,
            },
        },
        "approvals": [
            {
                "id": DEFAULT_APPROVAL_ID,
                "phase": "scope_approval",
                "status": "pending",
                "artifact": f"approvals/{DEFAULT_APPROVAL_ID}.md",
                "created_at": now,
                "decided_at": None,
                "decision": None,
            }
        ],
        "artifacts": {
            "docs": [
                "docs/prd.md",
                "docs/design-brief.md",
                "docs/technical-design.md",
                "docs/task-plan.md",
                "docs/acceptance.md",
            ],
            "config": [
                "config/imagegen.json",
                "schemas/imagegen.schema.json",
            ],
            "manifests": [
                "manifests/skills.lock",
                "manifests/subagents.lock",
                "manifests/model-versions.lock",
            ],
        },
        "confidence": None,
    }


def workflow_yaml(run_id: str, mode: str) -> str:
    return f"""# Multi-agent development workflow proposal.
run_id: {run_id}
mode: {mode}
version: 0.1.0
phases:
  - id: intake
    default_automation: automatic
    outputs:
      - requirement.md
  - id: scope_approval
    default_automation: human_gate
    outputs:
      - approvals/{DEFAULT_APPROVAL_ID}.md
  - id: research_docs
    default_automation: automatic_until_gate
    outputs:
      - docs/prd.md
      - docs/design-brief.md
      - docs/technical-design.md
      - docs/task-plan.md
  - id: design_generation
    default_automation: approval_required_for_sensitive_inputs
    outputs:
      - artifacts/design/
  - id: ui_replication
    default_automation: approval_required_before_code_write
    outputs:
      - artifacts/implementation/
      - artifacts/validation/
  - id: business_logic
    default_automation: approval_required_before_code_write
    outputs:
      - artifacts/implementation/
      - artifacts/validation/
  - id: acceptance
    default_automation: human_gate
    outputs:
      - docs/acceptance.md
approval_boundaries:
  - scope_change
  - code_write
  - dependency_install
  - external_write
  - sensitive_image_upload
  - secrets_access
  - production_data_access
  - visual_baseline_update
  - deployment
  - final_acceptance
"""


def permissions_yaml() -> str:
    return """# Default-deny permission policy for workflow nodes.
defaults:
  filesystem: read-only
  network: none
  shell: none
  secrets: none
  external_write: false
roles:
  researcher:
    filesystem: read-only
  reviewer:
    filesystem: read-only
  designer:
    filesystem: artifact-write
    approval_required_for:
      - sensitive_image_upload
      - external_write
  implementer:
    filesystem: workspace-write
    approval_required_for:
      - code_write
      - dependency_install
      - migration
      - external_write
  tester:
    filesystem: workspace-write
    approval_required_for:
      - visual_baseline_update
      - lowering_assertions
  releaser:
    approval_required_for:
      - deployment
      - production_data_access
      - external_write
"""


def state_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MultiAgentWorkflowState",
        "type": "object",
        "required": ["run_id", "status", "current_phase", "mode", "approvals"],
        "properties": {
            "run_id": {"type": "string"},
            "created_at": {"type": "string"},
            "updated_at": {"type": "string"},
            "status": {
                "enum": [
                    "initialized",
                    "waiting_for_approval",
                    "ready",
                    "running",
                    "partial",
                    "failed",
                    "completed",
                    "cancelled",
                ]
            },
            "current_phase": {"type": "string"},
            "mode": {"type": "string"},
            "requirement_path": {"type": "string"},
            "nodes": {"type": "object"},
            "approvals": {"type": "array"},
        },
    }


def event_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MultiAgentWorkflowEvent",
        "type": "object",
        "required": ["ts", "type"],
        "properties": {
            "ts": {"type": "string"},
            "type": {"type": "string"},
            "node": {"type": "string"},
            "artifact": {"type": "string"},
            "status": {"type": "string"},
        },
        "additionalProperties": True,
    }


def skill_manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "SkillManifest",
        "type": "object",
        "required": ["name", "version", "source", "permissions", "inputs", "outputs"],
        "properties": {
            "name": {"type": "string"},
            "version": {"type": "string"},
            "source": {"type": "string"},
            "pinned_ref": {"type": "string"},
            "owner": {"type": "string"},
            "trust_level": {"type": "string"},
            "permissions": {"type": "object"},
            "side_effects": {"type": "array", "items": {"type": "string"}},
            "inputs": {"type": "array"},
            "outputs": {"type": "array"},
            "approval_required_for": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": True,
    }


def role_by_id(role_id: str) -> dict[str, str]:
    for role in DOC_ROLE_DEFINITIONS:
        if role["id"] == role_id:
            return role
    raise SystemExit(f"Unknown role id: {role_id}")


def design_role_by_id(role_id: str) -> dict[str, str]:
    for role in DESIGN_ROLE_DEFINITIONS:
        if role["id"] == role_id:
            return role
    raise SystemExit(f"Unknown design role id: {role_id}")


def ui_replication_role_by_id(role_id: str) -> dict[str, str]:
    for role in UI_REPLICATION_ROLE_DEFINITIONS:
        if role["id"] == role_id:
            return role
    raise SystemExit(f"Unknown UI replication role id: {role_id}")


def business_logic_role_by_id(role_id: str) -> dict[str, str]:
    for role in BUSINESS_LOGIC_ROLE_DEFINITIONS:
        if role["id"] == role_id:
            return role
    raise SystemExit(f"Unknown business logic role id: {role_id}")


def acceptance_role_by_id(role_id: str) -> dict[str, str]:
    for role in ACCEPTANCE_ROLE_DEFINITIONS:
        if role["id"] == role_id:
            return role
    raise SystemExit(f"Unknown acceptance role id: {role_id}")


def artifact_header(role: dict[str, str]) -> str:
    return f"""# {role['title']}

- Role ID: `{role['id']}`
- Phase: `{role['phase']}`
- Status: `pending`
- Requirement: `../../requirement.md`
- Prompt: `../../prompts/{role['id']}.md`
- Produced: `pending`

## Output

Pending.
"""


def role_prompt(role: dict[str, str]) -> str:
    return f"""{role['prompt'].strip()}

Artifact persistence:
- Write your final output as complete Markdown suitable for `{role['artifact']}`.
- Start with `Status: success`, `Status: partial`, or `Status: failed`.
- Preserve assumptions, source links, local file references, contradictions, and unresolved questions.
- Keep implementation code unchanged.
"""


def design_role_prompt(role: dict[str, str]) -> str:
    return f"""{role['prompt'].strip()}

Artifact persistence:
- Write your final output as complete Markdown suitable for `{role['artifact']}`.
- Start with `Status: success`, `Status: partial`, or `Status: failed`.
- Do not call external image generation APIs.
- Do not upload images or sensitive materials.
- Preserve assumptions, prompt text, rejected variants, required approvals, and unresolved questions.
"""


def ui_replication_role_prompt(role: dict[str, str]) -> str:
    return f"""{role['prompt'].strip()}

Artifact persistence:
- Write your final output as complete Markdown suitable for `{role['artifact']}`.
- Start with `Status: success`, `Status: partial`, or `Status: failed`.
- Do not edit product code.
- Do not install dependencies.
- Do not update screenshots, baselines, deployments, or external systems.
- Preserve assumptions, target file candidates, approval boundaries, evidence requirements, and unresolved questions.
"""


def business_logic_role_prompt(role: dict[str, str]) -> str:
    return f"""{role['prompt'].strip()}

Artifact persistence:
- Write your final output as complete Markdown suitable for `{role['artifact']}`.
- Start with `Status: success`, `Status: partial`, or `Status: failed`.
- Do not edit product code.
- Do not install dependencies, run migrations, call external systems, or change tests.
- Preserve assumptions, business rules, target file candidates, approval boundaries, evidence requirements, and unresolved questions.
"""


def acceptance_role_prompt(role: dict[str, str]) -> str:
    return f"""{role['prompt'].strip()}

Artifact persistence:
- Write your final output as complete Markdown suitable for `{role['artifact']}`.
- Start with `Status: success`, `Status: partial`, or `Status: failed`.
- Do not edit product code, mutate tests, update baselines, deploy, or write external systems.
- Preserve evidence links, unresolved risks, rejected assumptions, and final sign-off recommendation.
"""


def infer_artifact_status(text: str) -> str:
    if not text.strip():
        return "missing"
    match = re.search(r"(?:^|\n)(?:[-*]\s*)?Status:\s*`?([A-Za-z_-]+)`?", text, re.I)
    if match:
        return match.group(1).strip().lower()
    if "Pending." in text and len(text.strip()) < 500:
        return "pending"
    return "success"


def placeholder_doc(title: str, purpose: str) -> str:
    return f"""# {title}

Status: pending

## Purpose

{purpose}

## Inputs

Pending.

## Output

Pending.

## Evidence

Pending.

## Next

Pending.
"""


def approval_doc(approval_id: str, requirement: str) -> str:
    return f"""# Scope Approval

- Approval ID: `{approval_id}`
- Phase: `scope_approval`
- Status: `pending`
- Created: `{utc_now()}`

## Request

Approve the workflow scope before executing agent-driven development phases.

## Requirement

{requirement}

## Decision

Pending.

## Comment

Pending.
"""


def docs_approval_doc(approval_id: str) -> str:
    return f"""# Docs Approval

- Approval ID: `{approval_id}`
- Phase: `docs_approval`
- Status: `pending`
- Created: `{utc_now()}`

## Request

Approve the research/docs phase before moving into design generation, UI replication, or code-writing planning.

## Required Artifacts

- `artifacts/research/01-product-research.md`
- `artifacts/research/02-architecture-research.md`
- `artifacts/research/03-risk-research.md`
- `artifacts/research/04-docs-synthesis.md`
- `artifacts/research/05-evidence-review.md`
- `artifacts/research/06-decision-review.md`
- `docs/prd.md`
- `docs/design-brief.md`
- `docs/technical-design.md`
- `docs/task-plan.md`

## Decision

Pending.

## Comment

Pending.
"""


def imagegen_approval_doc(approval_id: str, active_provider: str) -> str:
    return f"""# Image Generation Approval

- Approval ID: `{approval_id}`
- Phase: `imagegen_approval`
- Status: `pending`
- Created: `{utc_now()}`

## Request

Approve external image generation calls for the design generation phase.

## Active Provider

`{active_provider}`

## Required Artifacts

- `config/imagegen.json`
- `artifacts/design/imagegen-resolved.json`
- `artifacts/design/imagegen-dry-run-plan.json`
- `artifacts/design/01-design-requirement-map.md`
- `artifacts/design/02-imagegen-prompt-plan.md`
- `artifacts/design/03-visual-qa-plan.md`

## Approval Boundaries

- `external_network`
- `paid_model_call`
- `sensitive_image_upload`
- `external_write`

## Decision

Pending.

## Comment

Pending.
"""


def ui_replication_approval_doc(approval_id: str) -> str:
    return f"""# UI Replication Approval

- Approval ID: `{approval_id}`
- Phase: `ui_replication_approval`
- Status: `pending`
- Created: `{utc_now()}`

## Request

Approve moving from UI replication planning into code-writing execution.

## Required Artifacts

- `artifacts/implementation/01-ui-source-audit.md`
- `artifacts/implementation/02-ui-replication-plan.md`
- `artifacts/implementation/ui-replication-dry-run-plan.json`
- `artifacts/validation/01-ui-validation-plan.md`

## Approval Boundaries

- `code_write`
- `dependency_install`
- `visual_baseline_update`
- `external_write`

## Decision

Pending.

## Comment

Pending.
"""


def business_logic_approval_doc(approval_id: str) -> str:
    return f"""# Business Logic Approval

- Approval ID: `{approval_id}`
- Phase: `business_logic_approval`
- Status: `pending`
- Created: `{utc_now()}`

## Request

Approve moving from business logic planning into implementation/testing execution.

## Required Artifacts

- `artifacts/implementation/03-logic-contract-map.md`
- `artifacts/implementation/04-logic-implementation-plan.md`
- `artifacts/implementation/business-logic-dry-run-plan.json`
- `artifacts/validation/02-logic-test-plan.md`

## Approval Boundaries

- `code_write`
- `dependency_install`
- `migration`
- `external_write`
- `production_data_access`
- `lowering_assertions`

## Decision

Pending.

## Comment

Pending.
"""


def acceptance_approval_doc(approval_id: str) -> str:
    return f"""# Final Acceptance Approval

- Approval ID: `{approval_id}`
- Phase: `final_acceptance`
- Status: `pending`
- Created: `{utc_now()}`

## Request

Approve final workflow acceptance and mark the run complete.

## Required Artifacts

- `docs/acceptance.md`
- `artifacts/acceptance/01-acceptance-matrix.md`
- `artifacts/acceptance/02-evidence-completeness-review.md`
- `artifacts/acceptance/03-final-acceptance-report.md`
- `artifacts/acceptance/acceptance-dry-run-plan.json`
- `events.jsonl`

## Approval Boundaries

- `final_acceptance`
- `deployment`
- `external_write`
- `production_data_access`

## Decision

Pending.

## Comment

Pending.
"""


def update_approval_doc(path: Path, decision: str, comment: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    now = utc_now()
    status = "approved" if decision == "approve" else "rejected"
    text = re.sub(r"- Status: `[^`]+`", f"- Status: `{status}`", text, count=1)
    if "## Decision" in text:
        before = text.split("## Decision", 1)[0].rstrip()
        text = (
            f"{before}\n\n"
            "## Decision\n\n"
            f"- Status: `{status}`\n"
            f"- Decision: `{decision}`\n"
            f"- Decided: `{now}`\n\n"
            "## Comment\n\n"
            f"{comment or 'No comment.'}\n"
        )
    else:
        text = (
            f"# Approval {path.stem}\n\n"
            "## Decision\n\n"
            f"- Status: `{status}`\n"
            f"- Decision: `{decision}`\n"
            f"- Decided: `{now}`\n\n"
            "## Comment\n\n"
            f"{comment or 'No comment.'}\n"
        )
    write_text(path, text)


def write_index(run_dir: Path, state: dict[str, Any]) -> None:
    approvals = state.get("approvals", [])
    lines = [
        f"# Multi-Agent Dev Workflow: {state['run_id']}",
        "",
        "## Status",
        "",
        f"- Run status: `{state['status']}`",
        f"- Current phase: `{state['current_phase']}`",
        f"- Mode: `{state['mode']}`",
        "",
        "## Requirement",
        "",
        f"- [{state['requirement_path']}]({state['requirement_path']})",
        "",
        "## Approvals",
        "",
    ]
    if approvals:
        for approval in approvals:
            lines.append(
                f"- `{approval['id']}`: `{approval['status']}` - "
                f"[{approval['artifact']}]({approval['artifact']})"
            )
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Core Artifacts",
            "",
            "- [workflow.yaml](workflow.yaml)",
            "- [state.json](state.json)",
            "- [events.jsonl](events.jsonl)",
            "- [permissions.yaml](permissions.yaml)",
            "- [config/imagegen.json](config/imagegen.json)",
            "- [schemas/imagegen.schema.json](schemas/imagegen.schema.json)",
            "- [docs/prd.md](docs/prd.md)",
            "- [docs/design-brief.md](docs/design-brief.md)",
            "- [docs/technical-design.md](docs/technical-design.md)",
            "- [docs/task-plan.md](docs/task-plan.md)",
            "- [docs/acceptance.md](docs/acceptance.md)",
            "- [artifacts/design/imagegen-resolved.json](artifacts/design/imagegen-resolved.json)",
            "- [artifacts/design/imagegen-dry-run-plan.json](artifacts/design/imagegen-dry-run-plan.json)",
            "",
            "## Research / Docs Roles",
            "",
        ]
    )
    role_nodes = state.get("nodes", {})
    for role in DOC_ROLE_DEFINITIONS:
        node = role_nodes.get(role["id"], {})
        status = node.get("status", "not_started")
        artifact = role["artifact"]
        lines.append(f"- `{role['id']}`: `{status}` - [{artifact}]({artifact})")

    lines.extend(["", "## Design Generation Roles", ""])
    for role in DESIGN_ROLE_DEFINITIONS:
        node = role_nodes.get(role["id"], {})
        status = node.get("status", "not_started")
        artifact = role["artifact"]
        lines.append(f"- `{role['id']}`: `{status}` - [{artifact}]({artifact})")

    lines.extend(["", "## UI Replication Roles", ""])
    for role in UI_REPLICATION_ROLE_DEFINITIONS:
        node = role_nodes.get(role["id"], {})
        status = node.get("status", "not_started")
        artifact = role["artifact"]
        lines.append(f"- `{role['id']}`: `{status}` - [{artifact}]({artifact})")

    lines.extend(["", "## Business Logic Roles", ""])
    for role in BUSINESS_LOGIC_ROLE_DEFINITIONS:
        node = role_nodes.get(role["id"], {})
        status = node.get("status", "not_started")
        artifact = role["artifact"]
        lines.append(f"- `{role['id']}`: `{status}` - [{artifact}]({artifact})")

    lines.extend(["", "## Acceptance Roles", ""])
    for role in ACCEPTANCE_ROLE_DEFINITIONS:
        node = role_nodes.get(role["id"], {})
        status = node.get("status", "not_started")
        artifact = role["artifact"]
        lines.append(f"- `{role['id']}`: `{status}` - [{artifact}]({artifact})")

    lines.extend(
        [
            "",
            "## Future-Agent Handoff",
            "",
            "Read in order:",
            "",
            "1. `requirement.md`",
            "2. `workflow.yaml`",
            "3. `state.json`",
            "4. Pending approval artifacts under `approvals/`",
            "5. Docs under `docs/`",
            "",
        ]
    )
    write_text(run_dir / "index.md", "\n".join(lines))


def create_lockfile(title: str) -> str:
    return f"""# {title}

Status: empty

No entries registered yet.
"""


def create_run(args: argparse.Namespace) -> Path:
    requirement = read_requirement(args)
    project_root = Path(args.project_root).resolve()
    run_id = args.run_id
    if not run_id:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_id = f"{stamp}-{slugify(args.slug or requirement)}"
    run_dir = project_root / ".agent-workflows" / "dev" / run_id
    if run_dir.exists() and not args.force:
        raise SystemExit(f"Run directory already exists: {run_dir}")

    for directory in (
        "schemas",
        "config",
        "docs",
        "approvals",
        "artifacts/research",
        "artifacts/design",
        "artifacts/design/generated",
        "artifacts/implementation",
        "artifacts/validation",
        "artifacts/acceptance",
        "manifests",
        "logs",
    ):
        (run_dir / directory).mkdir(parents=True, exist_ok=True)

    state = initial_state(run_id, args.mode, "requirement.md")

    write_text(run_dir / "requirement.md", "# Requirement\n\n" + requirement)
    write_text(run_dir / "workflow.yaml", workflow_yaml(run_id, args.mode))
    write_text(run_dir / "permissions.yaml", permissions_yaml())
    write_text(run_dir / "schemas/state.schema.json", json.dumps(state_schema(), indent=2))
    write_text(run_dir / "schemas/event.schema.json", json.dumps(event_schema(), indent=2))
    write_text(
        run_dir / "schemas/skill-manifest.schema.json",
        json.dumps(skill_manifest_schema(), indent=2),
    )
    imagegen_config = load_imagegen_config_module()
    resolved_imagegen_config, imagegen_layers = imagegen_config.resolve_config(
        imagegen_config.default_layer_paths(project_root=project_root, run_dir=None)
    )
    write_text(
        run_dir / "config/imagegen.json",
        json.dumps(resolved_imagegen_config, ensure_ascii=False, indent=2),
    )
    write_text(
        run_dir / "schemas/imagegen.schema.json",
        json.dumps(imagegen_config.schema(), ensure_ascii=False, indent=2),
    )
    write_text(run_dir / "docs/prd.md", placeholder_doc("PRD", "Product requirements document."))
    write_text(
        run_dir / "docs/design-brief.md",
        placeholder_doc("Design Brief", "UX, interaction, visual direction, and design constraints."),
    )
    write_text(
        run_dir / "docs/technical-design.md",
        placeholder_doc("Technical Design", "Architecture, data flow, interfaces, and test strategy."),
    )
    write_text(
        run_dir / "docs/task-plan.md",
        placeholder_doc("Task Plan", "Ordered development tasks, dependencies, and owner agents."),
    )
    write_text(
        run_dir / "docs/acceptance.md",
        placeholder_doc("Acceptance Matrix", "Requirement-to-evidence traceability matrix."),
    )
    write_text(
        run_dir / f"approvals/{DEFAULT_APPROVAL_ID}.md",
        approval_doc(DEFAULT_APPROVAL_ID, requirement),
    )
    write_text(run_dir / "manifests/skills.lock", create_lockfile("Skills Lock"))
    write_text(run_dir / "manifests/subagents.lock", create_lockfile("Subagents Lock"))
    write_text(run_dir / "manifests/model-versions.lock", create_lockfile("Model Versions Lock"))
    write_text(run_dir / "logs/tool-calls.jsonl", "")
    write_text(run_dir / "logs/agent-runs.md", "# Agent Runs\n\nPending.")
    write_text(run_dir / "logs/errors.md", "# Errors\n\nNone.")
    save_state(run_dir, state)
    append_event(run_dir, "run_created", run_id=run_id, mode=args.mode)
    append_event(run_dir, "artifact_written", artifact="requirement.md")
    append_event(
        run_dir,
        "artifact_written",
        artifact="config/imagegen.json",
        resolved_from=[str(path) for path in imagegen_layers],
    )
    append_event(run_dir, "approval_requested", approval_id=DEFAULT_APPROVAL_ID)
    write_index(run_dir, state)
    return run_dir


def print_status(run_dir: Path) -> None:
    state = load_state(run_dir)
    approvals = state.get("approvals", [])
    print(f"Run: {state['run_id']}")
    print(f"Status: {state['status']}")
    print(f"Current phase: {state['current_phase']}")
    print(f"Mode: {state['mode']}")
    if approvals:
        print("Approvals:")
        for approval in approvals:
            print(f"- {approval['id']}: {approval['status']} ({approval['artifact']})")


def start_docs_phase(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    if state["status"] not in {"ready", "running", "partial"} and not args.force:
        raise SystemExit(
            f"Run must be ready/running/partial before start-docs; current status is {state['status']}."
        )

    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    nodes = state.setdefault("nodes", {})
    now = utc_now()

    for role in DOC_ROLE_DEFINITIONS:
        write_text(prompts_dir / f"{role['id']}.md", role_prompt(role))
        artifact_path = run_dir / role["artifact"]
        if not artifact_path.exists() or args.force:
            write_text(artifact_path, artifact_header(role))
        nodes[role["id"]] = {
            "status": "pending",
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "started_at": None,
            "finished_at": None,
        }
        append_event(run_dir, "role_prompt_created", role_id=role["id"], artifact=role["artifact"])

    state["status"] = "running"
    state["current_phase"] = "research_docs"
    state.setdefault("artifacts", {})["research_docs"] = [role["artifact"] for role in DOC_ROLE_DEFINITIONS]
    state["docs_phase_started_at"] = state.get("docs_phase_started_at") or now
    save_state(run_dir, state)
    append_event(run_dir, "phase_started", phase="research_docs")
    write_index(run_dir, state)


def maybe_create_docs_approval(run_dir: Path, state: dict[str, Any]) -> None:
    role_statuses = [
        state.get("nodes", {}).get(role["id"], {}).get("status")
        for role in DOC_ROLE_DEFINITIONS
    ]
    if not role_statuses or any(status != "success" for status in role_statuses):
        return
    approvals = state.setdefault("approvals", [])
    existing = next((item for item in approvals if item.get("id") == DOCS_APPROVAL_ID), None)
    if existing:
        return

    artifact = f"approvals/{DOCS_APPROVAL_ID}.md"
    approvals.append(
        {
            "id": DOCS_APPROVAL_ID,
            "phase": "docs_approval",
            "status": "pending",
            "artifact": artifact,
            "created_at": utc_now(),
            "decided_at": None,
            "decision": None,
        }
    )
    state.setdefault("nodes", {})["docs_approval"] = {
        "status": "waiting_for_approval",
        "artifact": artifact,
        "started_at": utc_now(),
        "finished_at": None,
    }
    state["status"] = "waiting_for_approval"
    state["current_phase"] = "docs_approval"
    write_text(run_dir / artifact, docs_approval_doc(DOCS_APPROVAL_ID))
    append_event(run_dir, "approval_requested", approval_id=DOCS_APPROVAL_ID)


def active_provider_from_config(config: dict[str, Any]) -> dict[str, Any]:
    active_provider = config.get("active_provider")
    providers = config.get("providers", [])
    for provider in providers:
        if isinstance(provider, dict) and provider.get("id") == active_provider:
            return provider
    raise SystemExit(f"Active imagegen provider not found: {active_provider}")


def provider_from_config(config: dict[str, Any], provider_id: str) -> dict[str, Any]:
    for provider in config.get("providers", []):
        if isinstance(provider, dict) and provider.get("id") == provider_id:
            return provider
    raise SystemExit(f"Imagegen provider not found: {provider_id}")


def approval_status(state: dict[str, Any], approval_id: str) -> str | None:
    for approval in state.get("approvals", []):
        if approval.get("id") == approval_id:
            return approval.get("status")
    return None


def draw_ui_provider_from_config(config: dict[str, Any]) -> dict[str, Any] | None:
    providers = [provider for provider in config.get("providers", []) if isinstance(provider, dict)]
    active_provider = config.get("active_provider")
    for provider in providers:
        if provider.get("id") == active_provider and provider.get("type") in {"openai-compatible", "custom-http"}:
            return provider
    for provider in providers:
        if provider.get("type") in {"openai-compatible", "custom-http"} and provider.get("enabled"):
            return provider
    return None


def imagegen_dry_run_plan(config: dict[str, Any]) -> dict[str, Any]:
    provider = active_provider_from_config(config)
    draw_ui_provider = draw_ui_provider_from_config(config)
    return {
        "version": "0.1.0",
        "created_at": utc_now(),
        "mode": "dry-run",
        "status": "pending_approval",
        "active_provider": provider.get("id"),
        "provider_type": provider.get("type"),
        "model": provider.get("model"),
        "base_url": provider.get("base_url"),
        "api_key_env": provider.get("api_key_env"),
        "approval_required_for": provider.get("approval_required_for", []),
        "draw_ui_integration": {
            "source": "multi-agent-dev-workflow/integrations/draw-ui",
            "integration_mode": "internal-capability",
            "supported_provider_types": [
                "openai-compatible",
                "custom-http",
            ],
            "provider_id": draw_ui_provider.get("id") if draw_ui_provider else None,
            "provider_enabled": draw_ui_provider.get("enabled") if draw_ui_provider else False,
            "api_key_env": draw_ui_provider.get("api_key_env") if draw_ui_provider else None,
            "workflow_command": [
                "python3",
                "multi-agent-dev-workflow/scripts/workflow_runner.py",
                "generate-ui-image",
                "--run-dir",
                ".agent-workflows/dev/<run-id>",
                "--provider",
                str(draw_ui_provider.get("id") if draw_ui_provider else "<image-provider-id>"),
                "--type",
                "wide",
                "--name",
                "primary-ui",
                "--prompt",
                "<prompt from artifacts/design/02-imagegen-prompt-plan.md>",
                "--output",
                "artifacts/design/generated/primary-ui.png",
            ],
            "internal_script_command": [
                "multi-agent-dev-workflow/integrations/draw-ui/scripts/ask_draw.sh",
                "--imagegen-config",
                "config/imagegen.json",
                "--provider",
                str(draw_ui_provider.get("id") if draw_ui_provider else "<image-provider-id>"),
                "--type",
                "wide",
                "--name",
                "primary-ui",
                "--prompt",
                "<prompt from artifacts/design/02-imagegen-prompt-plan.md>",
                "--output",
                "artifacts/design/generated/primary-ui.png",
            ],
            "html_reconstruction_reference": "multi-agent-dev-workflow/integrations/draw-ui/references/html-reconstruction.md",
            "verification_script": "multi-agent-dev-workflow/integrations/draw-ui/scripts/verify_html_mockup.sh",
        },
        "planned_outputs": [
            "artifacts/design/generated/primary-ui.png",
            "artifacts/design/generated/alternate-ui.png",
            "artifacts/design/generated/state-coverage.png",
            "artifacts/design/generated/*.png.json",
        ],
        "input_artifacts": [
            "docs/prd.md",
            "docs/design-brief.md",
            "docs/technical-design.md",
            "artifacts/design/01-design-requirement-map.md",
            "artifacts/design/02-imagegen-prompt-plan.md",
        ],
        "execution_note": "No image generation API calls have been made. This plan only records intended provider, inputs, outputs, and approvals.",
    }


def update_model_lock_for_imagegen(run_dir: Path, config: dict[str, Any]) -> None:
    provider = active_provider_from_config(config)
    text = f"""# Model Versions Lock

Status: partial

## Image Generation

- Provider ID: `{provider.get('id')}`
- Provider type: `{provider.get('type')}`
- Model: `{provider.get('model')}`
- Base URL: `{provider.get('base_url')}`
- API key env: `{provider.get('api_key_env')}`
- Locked at: `{utc_now()}`

Secret values are not stored in this file.
"""
    write_text(run_dir / "manifests/model-versions.lock", text)


def start_design_phase(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    if state["status"] not in {"ready", "running", "partial"} and not args.force:
        raise SystemExit(
            f"Run must be ready/running/partial before start-design; current status is {state['status']}."
        )
    if state["current_phase"] != "design_generation" and not args.force:
        raise SystemExit(
            f"Run must be in design_generation before start-design; current phase is {state['current_phase']}."
        )

    imagegen_config = load_imagegen_config_module()
    config_path = run_dir / "config/imagegen.json"
    config = imagegen_config.read_json(config_path)
    warnings = imagegen_config.validate_config(config)
    provider = active_provider_from_config(config)
    if not provider.get("enabled") and not args.allow_disabled_provider:
        raise SystemExit(
            f"Active imagegen provider is disabled: {provider.get('id')}. "
            "Enable it or pass --allow-disabled-provider for dry-run planning."
        )

    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    nodes = state.setdefault("nodes", {})
    now = utc_now()

    for role in DESIGN_ROLE_DEFINITIONS:
        write_text(prompts_dir / f"{role['id']}.md", design_role_prompt(role))
        artifact_path = run_dir / role["artifact"]
        if not artifact_path.exists() or args.force:
            write_text(artifact_path, artifact_header(role))
        nodes[role["id"]] = {
            "status": "pending",
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "started_at": None,
            "finished_at": None,
        }
        append_event(run_dir, "design_prompt_created", role_id=role["id"], artifact=role["artifact"])

    resolved_artifact = "artifacts/design/imagegen-resolved.json"
    dry_run_artifact = "artifacts/design/imagegen-dry-run-plan.json"
    write_text(run_dir / resolved_artifact, json.dumps(config, ensure_ascii=False, indent=2))
    write_text(run_dir / dry_run_artifact, json.dumps(imagegen_dry_run_plan(config), ensure_ascii=False, indent=2))
    update_model_lock_for_imagegen(run_dir, config)

    nodes["imagegen_dry_run"] = {
        "status": "success",
        "artifact": dry_run_artifact,
        "config": "config/imagegen.json",
        "started_at": now,
        "finished_at": utc_now(),
        "warnings": warnings,
    }
    state["status"] = "running"
    state["current_phase"] = "design_generation"
    state.setdefault("artifacts", {})["design_generation"] = [
        *(role["artifact"] for role in DESIGN_ROLE_DEFINITIONS),
        resolved_artifact,
        dry_run_artifact,
    ]
    state["design_phase_started_at"] = state.get("design_phase_started_at") or now
    save_state(run_dir, state)
    append_event(run_dir, "phase_started", phase="design_generation")
    append_event(run_dir, "artifact_written", artifact=resolved_artifact)
    append_event(run_dir, "artifact_written", artifact=dry_run_artifact, mode="dry-run")
    for warning in warnings:
        append_event(run_dir, "imagegen_config_warning", warning=warning)
    write_index(run_dir, state)


def maybe_create_imagegen_approval(run_dir: Path, state: dict[str, Any]) -> None:
    role_statuses = [
        state.get("nodes", {}).get(role["id"], {}).get("status")
        for role in DESIGN_ROLE_DEFINITIONS
    ]
    if not role_statuses or any(status != "success" for status in role_statuses):
        return
    if state.get("nodes", {}).get("imagegen_dry_run", {}).get("status") != "success":
        return
    approvals = state.setdefault("approvals", [])
    existing = next((item for item in approvals if item.get("id") == IMAGEGEN_APPROVAL_ID), None)
    if existing:
        return

    imagegen_config = load_imagegen_config_module()
    config = imagegen_config.read_json(run_dir / "config/imagegen.json")
    provider = active_provider_from_config(config)
    artifact = f"approvals/{IMAGEGEN_APPROVAL_ID}.md"
    approvals.append(
        {
            "id": IMAGEGEN_APPROVAL_ID,
            "phase": "imagegen_approval",
            "status": "pending",
            "artifact": artifact,
            "created_at": utc_now(),
            "decided_at": None,
            "decision": None,
        }
    )
    state.setdefault("nodes", {})["imagegen_approval"] = {
        "status": "waiting_for_approval",
        "artifact": artifact,
        "started_at": utc_now(),
        "finished_at": None,
    }
    state["status"] = "waiting_for_approval"
    state["current_phase"] = "imagegen_approval"
    write_text(run_dir / artifact, imagegen_approval_doc(IMAGEGEN_APPROVAL_ID, str(provider.get("id"))))
    append_event(run_dir, "approval_requested", approval_id=IMAGEGEN_APPROVAL_ID)


def ui_replication_dry_run_plan() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "created_at": utc_now(),
        "mode": "dry-run",
        "status": "pending_approval",
        "planned_inputs": [
            "docs/prd.md",
            "docs/design-brief.md",
            "docs/technical-design.md",
            "artifacts/design/01-design-requirement-map.md",
            "artifacts/design/02-imagegen-prompt-plan.md",
            "artifacts/design/03-visual-qa-plan.md",
            "artifacts/design/generated/",
        ],
        "planned_outputs": [
            "artifacts/implementation/01-ui-source-audit.md",
            "artifacts/implementation/02-ui-replication-plan.md",
            "artifacts/implementation/html/",
            "artifacts/implementation/flutter/",
            "artifacts/implementation/android/",
            "artifacts/implementation/ios/",
            "artifacts/validation/01-ui-validation-plan.md",
        ],
        "draw_ui_integration": {
            "source": "multi-agent-dev-workflow/integrations/draw-ui",
            "integration_mode": "internal-capability",
            "current_capability": "image-to-html reconstruction and screenshot comparison",
            "workflow_commands": [
                [
                    "python3",
                    "multi-agent-dev-workflow/scripts/workflow_runner.py",
                    "replicate-ui-html",
                    "--run-dir",
                    ".agent-workflows/dev/<run-id>",
                    "--reference",
                    "artifacts/design/generated/primary-ui.png",
                    "--name",
                    "primary-ui",
                    "--html-file",
                    "<reconstructed-html-file>",
                ],
                [
                    "python3",
                    "multi-agent-dev-workflow/scripts/workflow_runner.py",
                    "verify-ui-html",
                    "--run-dir",
                    ".agent-workflows/dev/<run-id>",
                    "--html",
                    "artifacts/implementation/html/primary-ui.html",
                    "--reference",
                    "artifacts/design/generated/primary-ui.png",
                    "--out-dir",
                    "artifacts/validation/ui-html/primary-ui",
                ],
            ],
            "target_replication_paths": [
                "html",
                "flutter",
                "android",
                "ios",
            ],
            "html_reference": "multi-agent-dev-workflow/integrations/draw-ui/references/html-reconstruction.md",
            "html_verify_script": "multi-agent-dev-workflow/integrations/draw-ui/scripts/verify_html_mockup.sh",
            "pixel_compare_script": "multi-agent-dev-workflow/integrations/draw-ui/scripts/compare_mockup.py",
            "future_adapters": [
                "html-to-flutter",
                "html-to-android",
                "html-to-ios",
            ],
        },
        "approval_required_for": [
            "code_write",
            "dependency_install",
            "visual_baseline_update",
            "external_write",
        ],
        "execution_note": "No product code has been edited. This plan only records intended UI replication inputs, outputs, validations, and approvals.",
    }


def start_ui_replication_phase(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    if state["status"] not in {"ready", "running", "partial"} and not args.force:
        raise SystemExit(
            f"Run must be ready/running/partial before start-ui-replication; current status is {state['status']}."
        )
    if state["current_phase"] != "ui_replication" and not args.force:
        raise SystemExit(
            f"Run must be in ui_replication before start-ui-replication; current phase is {state['current_phase']}."
        )

    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for directory in (
        "artifacts/implementation/html",
        "artifacts/implementation/flutter",
        "artifacts/implementation/android",
        "artifacts/implementation/ios",
    ):
        (run_dir / directory).mkdir(parents=True, exist_ok=True)
    nodes = state.setdefault("nodes", {})
    now = utc_now()

    for role in UI_REPLICATION_ROLE_DEFINITIONS:
        write_text(prompts_dir / f"{role['id']}.md", ui_replication_role_prompt(role))
        artifact_path = run_dir / role["artifact"]
        if not artifact_path.exists() or args.force:
            write_text(artifact_path, artifact_header(role))
        nodes[role["id"]] = {
            "status": "pending",
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "started_at": None,
            "finished_at": None,
        }
        append_event(run_dir, "ui_replication_prompt_created", role_id=role["id"], artifact=role["artifact"])

    dry_run_artifact = "artifacts/implementation/ui-replication-dry-run-plan.json"
    write_text(run_dir / dry_run_artifact, json.dumps(ui_replication_dry_run_plan(), ensure_ascii=False, indent=2))
    nodes["ui_replication_dry_run"] = {
        "status": "success",
        "artifact": dry_run_artifact,
        "started_at": now,
        "finished_at": utc_now(),
    }
    state["status"] = "running"
    state["current_phase"] = "ui_replication"
    state.setdefault("artifacts", {})["ui_replication"] = [
        *(role["artifact"] for role in UI_REPLICATION_ROLE_DEFINITIONS),
        dry_run_artifact,
    ]
    state["ui_replication_phase_started_at"] = state.get("ui_replication_phase_started_at") or now
    save_state(run_dir, state)
    append_event(run_dir, "phase_started", phase="ui_replication")
    append_event(run_dir, "artifact_written", artifact=dry_run_artifact, mode="dry-run")
    write_index(run_dir, state)


def maybe_create_ui_replication_approval(run_dir: Path, state: dict[str, Any]) -> None:
    role_statuses = [
        state.get("nodes", {}).get(role["id"], {}).get("status")
        for role in UI_REPLICATION_ROLE_DEFINITIONS
    ]
    if not role_statuses or any(status != "success" for status in role_statuses):
        return
    if state.get("nodes", {}).get("ui_replication_dry_run", {}).get("status") != "success":
        return
    approvals = state.setdefault("approvals", [])
    existing = next((item for item in approvals if item.get("id") == UI_REPLICATION_APPROVAL_ID), None)
    if existing:
        return

    artifact = f"approvals/{UI_REPLICATION_APPROVAL_ID}.md"
    approvals.append(
        {
            "id": UI_REPLICATION_APPROVAL_ID,
            "phase": "ui_replication_approval",
            "status": "pending",
            "artifact": artifact,
            "created_at": utc_now(),
            "decided_at": None,
            "decision": None,
        }
    )
    state.setdefault("nodes", {})["ui_replication_approval"] = {
        "status": "waiting_for_approval",
        "artifact": artifact,
        "started_at": utc_now(),
        "finished_at": None,
    }
    state["status"] = "waiting_for_approval"
    state["current_phase"] = "ui_replication_approval"
    write_text(run_dir / artifact, ui_replication_approval_doc(UI_REPLICATION_APPROVAL_ID))
    append_event(run_dir, "approval_requested", approval_id=UI_REPLICATION_APPROVAL_ID)


def business_logic_dry_run_plan() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "created_at": utc_now(),
        "mode": "dry-run",
        "status": "pending_approval",
        "planned_inputs": [
            "docs/prd.md",
            "docs/technical-design.md",
            "docs/task-plan.md",
            "artifacts/implementation/02-ui-replication-plan.md",
            "artifacts/validation/01-ui-validation-plan.md",
        ],
        "planned_outputs": [
            "artifacts/implementation/03-logic-contract-map.md",
            "artifacts/implementation/04-logic-implementation-plan.md",
            "artifacts/validation/02-logic-test-plan.md",
        ],
        "approval_required_for": [
            "code_write",
            "dependency_install",
            "migration",
            "external_write",
            "production_data_access",
            "lowering_assertions",
        ],
        "execution_note": "No product code, tests, dependencies, migrations, or external systems have been changed. This plan only records intended business logic implementation and validation work.",
    }


def start_business_logic_phase(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    if state["status"] not in {"ready", "running", "partial"} and not args.force:
        raise SystemExit(
            f"Run must be ready/running/partial before start-business-logic; current status is {state['status']}."
        )
    if state["current_phase"] != "business_logic" and not args.force:
        raise SystemExit(
            f"Run must be in business_logic before start-business-logic; current phase is {state['current_phase']}."
        )

    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    nodes = state.setdefault("nodes", {})
    now = utc_now()

    for role in BUSINESS_LOGIC_ROLE_DEFINITIONS:
        write_text(prompts_dir / f"{role['id']}.md", business_logic_role_prompt(role))
        artifact_path = run_dir / role["artifact"]
        if not artifact_path.exists() or args.force:
            write_text(artifact_path, artifact_header(role))
        nodes[role["id"]] = {
            "status": "pending",
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "started_at": None,
            "finished_at": None,
        }
        append_event(run_dir, "business_logic_prompt_created", role_id=role["id"], artifact=role["artifact"])

    dry_run_artifact = "artifacts/implementation/business-logic-dry-run-plan.json"
    write_text(run_dir / dry_run_artifact, json.dumps(business_logic_dry_run_plan(), ensure_ascii=False, indent=2))
    nodes["business_logic_dry_run"] = {
        "status": "success",
        "artifact": dry_run_artifact,
        "started_at": now,
        "finished_at": utc_now(),
    }
    state["status"] = "running"
    state["current_phase"] = "business_logic"
    state.setdefault("artifacts", {})["business_logic"] = [
        *(role["artifact"] for role in BUSINESS_LOGIC_ROLE_DEFINITIONS),
        dry_run_artifact,
    ]
    state["business_logic_phase_started_at"] = state.get("business_logic_phase_started_at") or now
    save_state(run_dir, state)
    append_event(run_dir, "phase_started", phase="business_logic")
    append_event(run_dir, "artifact_written", artifact=dry_run_artifact, mode="dry-run")
    write_index(run_dir, state)


def maybe_create_business_logic_approval(run_dir: Path, state: dict[str, Any]) -> None:
    role_statuses = [
        state.get("nodes", {}).get(role["id"], {}).get("status")
        for role in BUSINESS_LOGIC_ROLE_DEFINITIONS
    ]
    if not role_statuses or any(status != "success" for status in role_statuses):
        return
    if state.get("nodes", {}).get("business_logic_dry_run", {}).get("status") != "success":
        return
    approvals = state.setdefault("approvals", [])
    existing = next((item for item in approvals if item.get("id") == BUSINESS_LOGIC_APPROVAL_ID), None)
    if existing:
        return

    artifact = f"approvals/{BUSINESS_LOGIC_APPROVAL_ID}.md"
    approvals.append(
        {
            "id": BUSINESS_LOGIC_APPROVAL_ID,
            "phase": "business_logic_approval",
            "status": "pending",
            "artifact": artifact,
            "created_at": utc_now(),
            "decided_at": None,
            "decision": None,
        }
    )
    state.setdefault("nodes", {})["business_logic_approval"] = {
        "status": "waiting_for_approval",
        "artifact": artifact,
        "started_at": utc_now(),
        "finished_at": None,
    }
    state["status"] = "waiting_for_approval"
    state["current_phase"] = "business_logic_approval"
    write_text(run_dir / artifact, business_logic_approval_doc(BUSINESS_LOGIC_APPROVAL_ID))
    append_event(run_dir, "approval_requested", approval_id=BUSINESS_LOGIC_APPROVAL_ID)


def acceptance_dry_run_plan() -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "created_at": utc_now(),
        "mode": "dry-run",
        "status": "pending_final_acceptance",
        "planned_inputs": [
            "requirement.md",
            "docs/prd.md",
            "docs/acceptance.md",
            "artifacts/implementation/",
            "artifacts/validation/",
            "events.jsonl",
            "approvals/",
        ],
        "planned_outputs": [
            "artifacts/acceptance/01-acceptance-matrix.md",
            "artifacts/acceptance/02-evidence-completeness-review.md",
            "artifacts/acceptance/03-final-acceptance-report.md",
            "docs/acceptance.md",
        ],
        "approval_required_for": [
            "final_acceptance",
            "deployment",
            "external_write",
            "production_data_access",
        ],
        "execution_note": "No deployment, external write, production data access, or product code change has occurred. This plan only records final acceptance evidence and sign-off requirements.",
    }


def start_acceptance_phase(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    if state["status"] not in {"ready", "running", "partial"} and not args.force:
        raise SystemExit(
            f"Run must be ready/running/partial before start-acceptance; current status is {state['status']}."
        )
    if state["current_phase"] != "acceptance" and not args.force:
        raise SystemExit(
            f"Run must be in acceptance before start-acceptance; current phase is {state['current_phase']}."
        )

    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    nodes = state.setdefault("nodes", {})
    now = utc_now()

    for role in ACCEPTANCE_ROLE_DEFINITIONS:
        write_text(prompts_dir / f"{role['id']}.md", acceptance_role_prompt(role))
        artifact_path = run_dir / role["artifact"]
        if not artifact_path.exists() or args.force:
            write_text(artifact_path, artifact_header(role))
        nodes[role["id"]] = {
            "status": "pending",
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "started_at": None,
            "finished_at": None,
        }
        append_event(run_dir, "acceptance_prompt_created", role_id=role["id"], artifact=role["artifact"])

    dry_run_artifact = "artifacts/acceptance/acceptance-dry-run-plan.json"
    write_text(run_dir / dry_run_artifact, json.dumps(acceptance_dry_run_plan(), ensure_ascii=False, indent=2))
    nodes["acceptance_dry_run"] = {
        "status": "success",
        "artifact": dry_run_artifact,
        "started_at": now,
        "finished_at": utc_now(),
    }
    state["status"] = "running"
    state["current_phase"] = "acceptance"
    state.setdefault("artifacts", {})["acceptance"] = [
        *(role["artifact"] for role in ACCEPTANCE_ROLE_DEFINITIONS),
        dry_run_artifact,
        "docs/acceptance.md",
    ]
    state["acceptance_phase_started_at"] = state.get("acceptance_phase_started_at") or now
    save_state(run_dir, state)
    append_event(run_dir, "phase_started", phase="acceptance")
    append_event(run_dir, "artifact_written", artifact=dry_run_artifact, mode="dry-run")
    write_index(run_dir, state)


def maybe_create_acceptance_approval(run_dir: Path, state: dict[str, Any]) -> None:
    role_statuses = [
        state.get("nodes", {}).get(role["id"], {}).get("status")
        for role in ACCEPTANCE_ROLE_DEFINITIONS
    ]
    if not role_statuses or any(status != "success" for status in role_statuses):
        return
    if state.get("nodes", {}).get("acceptance_dry_run", {}).get("status") != "success":
        return
    approvals = state.setdefault("approvals", [])
    existing = next((item for item in approvals if item.get("id") == ACCEPTANCE_APPROVAL_ID), None)
    if existing:
        return

    artifact = f"approvals/{ACCEPTANCE_APPROVAL_ID}.md"
    approvals.append(
        {
            "id": ACCEPTANCE_APPROVAL_ID,
            "phase": "final_acceptance",
            "status": "pending",
            "artifact": artifact,
            "created_at": utc_now(),
            "decided_at": None,
            "decision": None,
        }
    )
    state.setdefault("nodes", {})["final_acceptance"] = {
        "status": "waiting_for_approval",
        "artifact": artifact,
        "started_at": utc_now(),
        "finished_at": None,
    }
    state["status"] = "waiting_for_approval"
    state["current_phase"] = "final_acceptance"
    write_text(run_dir / artifact, acceptance_approval_doc(ACCEPTANCE_APPROVAL_ID))
    append_event(run_dir, "approval_requested", approval_id=ACCEPTANCE_APPROVAL_ID)


def record_role_output(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    role = role_by_id(args.role)
    output_path = Path(args.file) if args.file else None
    output = output_path.read_text(encoding="utf-8") if output_path else args.content
    if not output:
        raise SystemExit("Provide --file or --content.")

    status = args.status or infer_artifact_status(output)
    if status not in {"success", "partial", "failed", "timed_out"}:
        raise SystemExit("--status must be success, partial, failed, or timed_out.")

    artifact_text = output.rstrip()
    if not re.search(r"(?:^|\n)(?:[-*]\s*)?Status:\s*`?[A-Za-z_-]+`?", artifact_text, re.I):
        artifact_text = f"Status: {status}\n\n{artifact_text}"
    write_text(run_dir / role["artifact"], artifact_text)

    node = state.setdefault("nodes", {}).setdefault(role["id"], {})
    node.update(
        {
            "status": status,
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "finished_at": utc_now(),
        }
    )
    if not node.get("started_at"):
        node["started_at"] = node["finished_at"]

    if status == "failed":
        state["status"] = "partial"
    elif state["status"] not in {"waiting_for_approval", "cancelled"}:
        state["status"] = "running"
    state["current_phase"] = "research_docs"

    append_event(run_dir, "role_output_recorded", role_id=role["id"], status=status, artifact=role["artifact"])
    maybe_create_docs_approval(run_dir, state)
    save_state(run_dir, state)
    write_index(run_dir, state)


def record_design_output(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    role = design_role_by_id(args.role)
    output_path = Path(args.file) if args.file else None
    output = output_path.read_text(encoding="utf-8") if output_path else args.content
    if not output:
        raise SystemExit("Provide --file or --content.")

    status = args.status or infer_artifact_status(output)
    if status not in {"success", "partial", "failed", "timed_out"}:
        raise SystemExit("--status must be success, partial, failed, or timed_out.")

    artifact_text = output.rstrip()
    if not re.search(r"(?:^|\n)(?:[-*]\s*)?Status:\s*`?[A-Za-z_-]+`?", artifact_text, re.I):
        artifact_text = f"Status: {status}\n\n{artifact_text}"
    write_text(run_dir / role["artifact"], artifact_text)

    node = state.setdefault("nodes", {}).setdefault(role["id"], {})
    node.update(
        {
            "status": status,
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "finished_at": utc_now(),
        }
    )
    if not node.get("started_at"):
        node["started_at"] = node["finished_at"]

    if status == "failed":
        state["status"] = "partial"
    elif state["status"] not in {"waiting_for_approval", "cancelled"}:
        state["status"] = "running"
    state["current_phase"] = "design_generation"

    append_event(
        run_dir,
        "design_output_recorded",
        role_id=role["id"],
        status=status,
        artifact=role["artifact"],
    )
    maybe_create_imagegen_approval(run_dir, state)
    save_state(run_dir, state)
    write_index(run_dir, state)


def record_ui_replication_output(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    role = ui_replication_role_by_id(args.role)
    output_path = Path(args.file) if args.file else None
    output = output_path.read_text(encoding="utf-8") if output_path else args.content
    if not output:
        raise SystemExit("Provide --file or --content.")

    status = args.status or infer_artifact_status(output)
    if status not in {"success", "partial", "failed", "timed_out"}:
        raise SystemExit("--status must be success, partial, failed, or timed_out.")

    artifact_text = output.rstrip()
    if not re.search(r"(?:^|\n)(?:[-*]\s*)?Status:\s*`?[A-Za-z_-]+`?", artifact_text, re.I):
        artifact_text = f"Status: {status}\n\n{artifact_text}"
    write_text(run_dir / role["artifact"], artifact_text)

    node = state.setdefault("nodes", {}).setdefault(role["id"], {})
    node.update(
        {
            "status": status,
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "finished_at": utc_now(),
        }
    )
    if not node.get("started_at"):
        node["started_at"] = node["finished_at"]

    if status == "failed":
        state["status"] = "partial"
    elif state["status"] not in {"waiting_for_approval", "cancelled"}:
        state["status"] = "running"
    state["current_phase"] = "ui_replication"

    append_event(
        run_dir,
        "ui_replication_output_recorded",
        role_id=role["id"],
        status=status,
        artifact=role["artifact"],
    )
    maybe_create_ui_replication_approval(run_dir, state)
    save_state(run_dir, state)
    write_index(run_dir, state)


def record_business_logic_output(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    role = business_logic_role_by_id(args.role)
    output_path = Path(args.file) if args.file else None
    output = output_path.read_text(encoding="utf-8") if output_path else args.content
    if not output:
        raise SystemExit("Provide --file or --content.")

    status = args.status or infer_artifact_status(output)
    if status not in {"success", "partial", "failed", "timed_out"}:
        raise SystemExit("--status must be success, partial, failed, or timed_out.")

    artifact_text = output.rstrip()
    if not re.search(r"(?:^|\n)(?:[-*]\s*)?Status:\s*`?[A-Za-z_-]+`?", artifact_text, re.I):
        artifact_text = f"Status: {status}\n\n{artifact_text}"
    write_text(run_dir / role["artifact"], artifact_text)

    node = state.setdefault("nodes", {}).setdefault(role["id"], {})
    node.update(
        {
            "status": status,
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "finished_at": utc_now(),
        }
    )
    if not node.get("started_at"):
        node["started_at"] = node["finished_at"]

    if status == "failed":
        state["status"] = "partial"
    elif state["status"] not in {"waiting_for_approval", "cancelled"}:
        state["status"] = "running"
    state["current_phase"] = "business_logic"

    append_event(
        run_dir,
        "business_logic_output_recorded",
        role_id=role["id"],
        status=status,
        artifact=role["artifact"],
    )
    maybe_create_business_logic_approval(run_dir, state)
    save_state(run_dir, state)
    write_index(run_dir, state)


def record_acceptance_output(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    state = load_state(run_dir)
    role = acceptance_role_by_id(args.role)
    output_path = Path(args.file) if args.file else None
    output = output_path.read_text(encoding="utf-8") if output_path else args.content
    if not output:
        raise SystemExit("Provide --file or --content.")

    status = args.status or infer_artifact_status(output)
    if status not in {"success", "partial", "failed", "timed_out"}:
        raise SystemExit("--status must be success, partial, failed, or timed_out.")

    artifact_text = output.rstrip()
    if not re.search(r"(?:^|\n)(?:[-*]\s*)?Status:\s*`?[A-Za-z_-]+`?", artifact_text, re.I):
        artifact_text = f"Status: {status}\n\n{artifact_text}"
    write_text(run_dir / role["artifact"], artifact_text)

    if role["id"] == "acceptance-matrix-author":
        write_text(run_dir / "docs/acceptance.md", artifact_text)

    node = state.setdefault("nodes", {}).setdefault(role["id"], {})
    node.update(
        {
            "status": status,
            "artifact": role["artifact"],
            "prompt": f"prompts/{role['id']}.md",
            "finished_at": utc_now(),
        }
    )
    if not node.get("started_at"):
        node["started_at"] = node["finished_at"]

    if status == "failed":
        state["status"] = "partial"
    elif state["status"] not in {"waiting_for_approval", "cancelled"}:
        state["status"] = "running"
    state["current_phase"] = "acceptance"

    append_event(
        run_dir,
        "acceptance_output_recorded",
        role_id=role["id"],
        status=status,
        artifact=role["artifact"],
    )
    if role["id"] == "acceptance-matrix-author":
        append_event(run_dir, "artifact_written", artifact="docs/acceptance.md")
    maybe_create_acceptance_approval(run_dir, state)
    save_state(run_dir, state)
    write_index(run_dir, state)


def generate_ui_image(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    state = load_state(run_dir)
    if approval_status(state, IMAGEGEN_APPROVAL_ID) != "approved" and not args.force:
        raise SystemExit(
            f"Image generation requires approved {IMAGEGEN_APPROVAL_ID}. "
            "Use --force only for local mock/smoke runs."
        )

    imagegen_config = load_imagegen_config_module()
    config_path = run_dir / "config/imagegen.json"
    config = imagegen_config.read_json(config_path)
    imagegen_config.validate_config(config)

    provider = provider_from_config(config, args.provider) if args.provider else active_provider_from_config(config)
    provider_type = provider.get("type")
    if provider_type not in {"openai-compatible", "custom-http"}:
        raise SystemExit(
            "The internal draw-ui executor supports only openai-compatible or custom-http providers. "
            f"Provider {provider.get('id')!r} is {provider_type!r}."
        )
    if not provider.get("enabled") and not args.allow_disabled_provider:
        raise SystemExit(
            f"Imagegen provider is disabled: {provider.get('id')}. "
            "Enable it or pass --allow-disabled-provider for a controlled test."
        )

    api_key_env = str(provider.get("api_key_env") or "")
    if not os.getenv(api_key_env, "").strip() and not args.skip_env_check:
        raise SystemExit(
            f"Missing environment variable {api_key_env}. "
            "The workflow stores only env var names, not raw API keys."
        )

    output = Path(args.output) if args.output else Path("artifacts/design/generated/primary-ui.png")
    output_path = output if output.is_absolute() else run_dir / output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        str(DRAW_UI_ASK_SCRIPT),
        "--imagegen-config",
        str(config_path),
        "--provider",
        str(provider.get("id")),
        "--type",
        args.type,
        "--name",
        args.name,
        "--prompt",
        args.prompt,
        "--output",
        str(output_path),
    ]
    if args.frame:
        command.extend(["--frame", args.frame])
    for ref in args.ref or []:
        command.extend(["--ref", ref])

    now = utc_now()
    node = state.setdefault("nodes", {}).setdefault("draw_ui_image_generation", {})
    node.update(
        {
            "status": "running",
            "artifact": display_path(output_path, run_dir),
            "provider": provider.get("id"),
            "started_at": now,
            "finished_at": None,
        }
    )
    save_state(run_dir, state)
    append_event(
        run_dir,
        "draw_ui_image_generation_started",
        provider_id=provider.get("id"),
        provider_type=provider_type,
        output=str(output_path),
    )

    try:
        completed = subprocess.run(command, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        node["status"] = "failed"
        node["finished_at"] = utc_now()
        node["error"] = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        state["status"] = "partial"
        save_state(run_dir, state)
        append_event(
            run_dir,
            "draw_ui_image_generation_failed",
            provider_id=provider.get("id"),
            output=str(output_path),
            returncode=exc.returncode,
        )
        raise SystemExit(node["error"]) from exc

    metadata_path = output_path.with_suffix(output_path.suffix + ".json")
    rel_output = display_path(output_path, run_dir)
    rel_metadata = display_path(metadata_path, run_dir)
    node.update(
        {
            "status": "success",
            "artifact": rel_output,
            "metadata": rel_metadata,
            "finished_at": utc_now(),
        }
    )
    state.setdefault("artifacts", {}).setdefault("design_generation_outputs", []).append(rel_output)
    if state["status"] not in {"waiting_for_approval", "cancelled", "completed"}:
        state["status"] = "running"
    save_state(run_dir, state)
    append_event(
        run_dir,
        "draw_ui_image_generation_completed",
        provider_id=provider.get("id"),
        output=rel_output,
        metadata=rel_metadata,
    )
    append_event(run_dir, "artifact_written", artifact=rel_output)
    if metadata_path.exists():
        append_event(run_dir, "artifact_written", artifact=rel_metadata)
    write_index(run_dir, state)
    print(completed.stdout.strip())


def html_replication_prompt(*, reference: str, output: str, name: str, notes: str) -> str:
    notes_block = notes.strip() or "No extra notes."
    return f"""# HTML UI Replication Prompt

Status: pending

## Objective

Reconstruct the reference UI mockup or screenshot as production-quality HTML/CSS.

## Inputs

- Reference image: `{reference}`
- Target HTML: `{output}`
- Draw UI reconstruction guide: `{display_path(DRAW_UI_HTML_REFERENCE, Path.cwd())}`

## Requirements

- Build layout, text, controls, cards, tables, and ordinary icons with HTML/CSS/SVG.
- Use generated or prepared image assets only for complex visuals that are impractical to code directly.
- Preserve responsive constraints, viewport framing, text legibility, and visual hierarchy.
- Do not edit product code outside the workflow artifact directory unless a later approval explicitly permits it.
- After HTML is produced, run `verify-ui-html` against the same reference.

## Notes

{notes_block}

## Expected Output

Write complete HTML to `{output}`. Keep local asset paths relative to the HTML file.
"""


def replicate_ui_html(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    state = load_state(run_dir)
    if state.get("current_phase") not in {"ui_replication", "ui_replication_approval", "business_logic"} and not args.force:
        raise SystemExit(
            "HTML replication should run during or after ui_replication planning. "
            f"Current phase is {state.get('current_phase')!r}; use --force for controlled local tests."
        )

    reference_path = resolve_path(args.reference, run_dir)
    if not reference_path.exists():
        raise SystemExit(f"Reference image not found: {reference_path}")

    name = slugify(args.name or reference_path.stem, fallback="ui-html")
    output_arg = args.output or f"artifacts/implementation/html/{name}.html"
    output_path = resolve_path(output_arg, run_dir)
    prompt_path = resolve_path(args.prompt_output or f"artifacts/implementation/html/{name}.replication-prompt.md", run_dir)
    manifest_path = resolve_path(args.manifest_output or f"artifacts/implementation/html/{name}.replication.json", run_dir)

    html = read_text_arg(file=args.html_file, content=args.html, label="html")
    notes = read_text_arg(file=args.notes_file, content=args.notes, label="notes")

    prompt = html_replication_prompt(
        reference=display_path(reference_path, run_dir),
        output=display_path(output_path, run_dir),
        name=name,
        notes=notes,
    )
    write_text(prompt_path, prompt)

    status = "pending_html"
    if html:
        write_text(output_path, html)
        status = "success"
    elif args.require_html:
        raise SystemExit("Provide --html-file or --html when --require-html is set.")

    manifest = {
        "version": "0.1.0",
        "created_at": utc_now(),
        "name": name,
        "status": status,
        "reference": display_path(reference_path, run_dir),
        "html": display_path(output_path, run_dir),
        "prompt": display_path(prompt_path, run_dir),
        "guide": display_path(DRAW_UI_HTML_REFERENCE, Path.cwd()),
        "notes": notes,
        "execution_note": (
            "HTML artifact was recorded from provided content."
            if html
            else "No HTML artifact was provided. Prompt package is ready for a human or subagent."
        ),
    }
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))

    node = state.setdefault("nodes", {}).setdefault("draw_ui_html_replication", {})
    node.update(
        {
            "status": status,
            "artifact": display_path(output_path, run_dir) if html else display_path(prompt_path, run_dir),
            "manifest": display_path(manifest_path, run_dir),
            "reference": display_path(reference_path, run_dir),
            "finished_at": utc_now(),
        }
    )
    if not node.get("started_at"):
        node["started_at"] = node["finished_at"]
    state.setdefault("artifacts", {}).setdefault("ui_replication_outputs", []).append(display_path(manifest_path, run_dir))
    if html:
        state.setdefault("artifacts", {}).setdefault("ui_replication_outputs", []).append(display_path(output_path, run_dir))
    if state["status"] not in {"waiting_for_approval", "cancelled", "completed"}:
        state["status"] = "running" if html else "partial"
    save_state(run_dir, state)
    append_event(
        run_dir,
        "draw_ui_html_replication_recorded",
        status=status,
        reference=display_path(reference_path, run_dir),
        html=display_path(output_path, run_dir) if html else None,
        manifest=display_path(manifest_path, run_dir),
    )
    append_event(run_dir, "artifact_written", artifact=display_path(prompt_path, run_dir))
    append_event(run_dir, "artifact_written", artifact=display_path(manifest_path, run_dir))
    if html:
        append_event(run_dir, "artifact_written", artifact=display_path(output_path, run_dir))
    write_index(run_dir, state)
    print(f"replication_status={status}")
    print(f"manifest={manifest_path}")
    if html:
        print(f"html={output_path}")


def verify_ui_html(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    state = load_state(run_dir)
    html_path = resolve_path(args.html, run_dir)
    reference_path = resolve_path(args.reference, run_dir)
    if not html_path.exists():
        raise SystemExit(f"HTML file not found: {html_path}")
    if not reference_path.exists():
        raise SystemExit(f"Reference image not found: {reference_path}")

    name = slugify(args.name or html_path.stem, fallback="ui-html")
    out_dir = resolve_path(args.out_dir or f"artifacts/validation/ui-html/{name}", run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    node = state.setdefault("nodes", {}).setdefault("draw_ui_html_verification", {})
    node.update(
        {
            "status": "running",
            "artifact": display_path(out_dir, run_dir),
            "html": display_path(html_path, run_dir),
            "reference": display_path(reference_path, run_dir),
            "started_at": utc_now(),
            "finished_at": None,
        }
    )
    save_state(run_dir, state)
    append_event(
        run_dir,
        "draw_ui_html_verification_started",
        html=display_path(html_path, run_dir),
        reference=display_path(reference_path, run_dir),
        out_dir=display_path(out_dir, run_dir),
    )

    if args.candidate_screenshot:
        candidate_path = resolve_path(args.candidate_screenshot, run_dir)
        if not candidate_path.exists():
            raise SystemExit(f"Candidate screenshot not found: {candidate_path}")
        command = [
            "python3",
            str(DRAW_UI_COMPARE_SCRIPT),
            "--reference",
            str(reference_path),
            "--candidate",
            str(candidate_path),
            "--out-dir",
            str(out_dir),
            "--prefix",
            args.prefix,
        ]
        for clip in args.clip or []:
            command.extend(["--clip", clip])
    else:
        if not shutil.which("agent-browser"):
            raise SystemExit(
                "agent-browser is required for browser screenshot verification. "
                "Install it or pass --candidate-screenshot to compare an existing screenshot."
            )
        command = [
            str(DRAW_UI_VERIFY_SCRIPT),
            "--html",
            str(html_path),
            "--reference",
            str(reference_path),
            "--out-dir",
            str(out_dir),
            "--viewport",
            args.viewport,
            "--session",
            args.session,
        ]
        if args.full_page:
            command.append("--full-page")

    try:
        completed = subprocess.run(command, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        node["status"] = "failed"
        node["finished_at"] = utc_now()
        node["error"] = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        state["status"] = "partial"
        save_state(run_dir, state)
        append_event(
            run_dir,
            "draw_ui_html_verification_failed",
            html=display_path(html_path, run_dir),
            reference=display_path(reference_path, run_dir),
            returncode=exc.returncode,
        )
        raise SystemExit(node["error"]) from exc

    metrics_path = out_dir / f"{args.prefix}-metrics.json"
    manifest_path = out_dir / "verification.json"
    manifest = {
        "version": "0.1.0",
        "created_at": utc_now(),
        "status": "success",
        "html": display_path(html_path, run_dir),
        "reference": display_path(reference_path, run_dir),
        "out_dir": display_path(out_dir, run_dir),
        "metrics": display_path(metrics_path, run_dir) if metrics_path.exists() else None,
        "mode": "candidate-screenshot" if args.candidate_screenshot else "browser-screenshot",
        "command": command,
    }
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    node.update(
        {
            "status": "success",
            "artifact": display_path(manifest_path, run_dir),
            "metrics": display_path(metrics_path, run_dir) if metrics_path.exists() else None,
            "finished_at": utc_now(),
        }
    )
    state.setdefault("artifacts", {}).setdefault("validation_outputs", []).append(display_path(manifest_path, run_dir))
    if metrics_path.exists():
        state.setdefault("artifacts", {}).setdefault("validation_outputs", []).append(display_path(metrics_path, run_dir))
    if state["status"] not in {"waiting_for_approval", "cancelled", "completed"}:
        state["status"] = "running"
    save_state(run_dir, state)
    append_event(
        run_dir,
        "draw_ui_html_verification_completed",
        html=display_path(html_path, run_dir),
        reference=display_path(reference_path, run_dir),
        manifest=display_path(manifest_path, run_dir),
        metrics=display_path(metrics_path, run_dir) if metrics_path.exists() else None,
    )
    append_event(run_dir, "artifact_written", artifact=display_path(manifest_path, run_dir))
    if metrics_path.exists():
        append_event(run_dir, "artifact_written", artifact=display_path(metrics_path, run_dir))
    write_index(run_dir, state)
    print(completed.stdout.strip())
    print(f"verification={manifest_path}")


def resume_run(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    decision = args.decision.lower()
    if decision not in TERMINAL_APPROVAL_DECISIONS:
        raise SystemExit("--decision must be approve or reject.")

    state = load_state(run_dir)
    approvals = state.get("approvals", [])
    approval = next((item for item in approvals if item.get("id") == args.approval), None)
    if not approval:
        raise SystemExit(f"Unknown approval id: {args.approval}")
    if approval.get("status") != "pending" and not args.force:
        raise SystemExit(
            f"Approval {args.approval} is already {approval.get('status')}; use --force to override."
        )

    status = "approved" if decision == "approve" else "rejected"
    approval["status"] = status
    approval["decision"] = decision
    approval["decided_at"] = utc_now()

    node_key = str(approval.get("phase") or args.approval)
    node = state.setdefault("nodes", {}).setdefault(node_key, {})
    node["status"] = status
    node["finished_at"] = approval["decided_at"]

    if decision == "approve" and args.approval == DEFAULT_APPROVAL_ID:
        state["status"] = "ready"
        state["current_phase"] = "research_docs"
    elif decision == "approve" and args.approval == DOCS_APPROVAL_ID:
        state["status"] = "ready"
        state["current_phase"] = "design_generation"
    elif decision == "approve" and args.approval == IMAGEGEN_APPROVAL_ID:
        state["status"] = "ready"
        state["current_phase"] = "ui_replication"
    elif decision == "approve" and args.approval == UI_REPLICATION_APPROVAL_ID:
        state["status"] = "ready"
        state["current_phase"] = "business_logic"
    elif decision == "approve" and args.approval == BUSINESS_LOGIC_APPROVAL_ID:
        state["status"] = "ready"
        state["current_phase"] = "acceptance"
    elif decision == "approve" and args.approval == ACCEPTANCE_APPROVAL_ID:
        state["status"] = "completed"
        state["current_phase"] = "completed"
        state["completed_at"] = approval["decided_at"]
    else:
        state["status"] = "cancelled"
        state["current_phase"] = f"{approval.get('phase', 'approval')}_rejected"

    approval_path = run_dir / approval["artifact"]
    update_approval_doc(approval_path, decision, args.comment or "")
    save_state(run_dir, state)
    append_event(
        run_dir,
        "approval_decided",
        approval_id=args.approval,
        decision=decision,
        status=status,
    )
    write_index(run_dir, state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Create a local workflow run.")
    run.add_argument("--requirement", help="Requirement text.")
    run.add_argument("--file", help="Requirement markdown/text file.")
    run.add_argument("--project-root", default=".", help="Project root for .agent-workflows/dev.")
    run.add_argument("--run-id", help="Explicit run id.")
    run.add_argument("--slug", help="Slug suffix for generated run id.")
    run.add_argument("--mode", default=DEFAULT_MODE, help="Workflow mode.")
    run.add_argument("--force", action="store_true", help="Allow using an existing run directory.")

    status = subparsers.add_parser("status", help="Print workflow run status.")
    status.add_argument("--run-dir", required=True, help="Workflow run directory.")

    start_docs = subparsers.add_parser(
        "start-docs", help="Create research/docs prompts and artifact placeholders."
    )
    start_docs.add_argument("--run-dir", required=True, help="Workflow run directory.")
    start_docs.add_argument("--force", action="store_true", help="Overwrite existing prompts/artifacts.")

    start_design = subparsers.add_parser(
        "start-design", help="Create design generation prompts and imagegen dry-run artifacts."
    )
    start_design.add_argument("--run-dir", required=True, help="Workflow run directory.")
    start_design.add_argument("--force", action="store_true", help="Overwrite existing prompts/artifacts.")
    start_design.add_argument(
        "--allow-disabled-provider",
        action="store_true",
        help="Allow dry-run planning even when the active provider is disabled.",
    )

    start_ui_replication = subparsers.add_parser(
        "start-ui-replication", help="Create UI replication prompts and dry-run artifacts."
    )
    start_ui_replication.add_argument("--run-dir", required=True, help="Workflow run directory.")
    start_ui_replication.add_argument("--force", action="store_true", help="Overwrite existing prompts/artifacts.")

    start_business_logic = subparsers.add_parser(
        "start-business-logic", help="Create business logic prompts and dry-run artifacts."
    )
    start_business_logic.add_argument("--run-dir", required=True, help="Workflow run directory.")
    start_business_logic.add_argument("--force", action="store_true", help="Overwrite existing prompts/artifacts.")

    start_acceptance = subparsers.add_parser(
        "start-acceptance", help="Create final acceptance prompts and dry-run artifacts."
    )
    start_acceptance.add_argument("--run-dir", required=True, help="Workflow run directory.")
    start_acceptance.add_argument("--force", action="store_true", help="Overwrite existing prompts/artifacts.")

    record = subparsers.add_parser("record", help="Record a research/docs role output.")
    record.add_argument("--run-dir", required=True, help="Workflow run directory.")
    record.add_argument("--role", required=True, help="Role id to record.")
    record.add_argument("--file", help="Markdown file containing role output.")
    record.add_argument("--content", help="Inline Markdown role output.")
    record.add_argument("--status", help="Override inferred status.")

    record_design = subparsers.add_parser("record-design", help="Record a design generation role output.")
    record_design.add_argument("--run-dir", required=True, help="Workflow run directory.")
    record_design.add_argument("--role", required=True, help="Design role id to record.")
    record_design.add_argument("--file", help="Markdown file containing role output.")
    record_design.add_argument("--content", help="Inline Markdown role output.")
    record_design.add_argument("--status", help="Override inferred status.")

    record_ui_replication = subparsers.add_parser(
        "record-ui-replication", help="Record a UI replication role output."
    )
    record_ui_replication.add_argument("--run-dir", required=True, help="Workflow run directory.")
    record_ui_replication.add_argument("--role", required=True, help="UI replication role id to record.")
    record_ui_replication.add_argument("--file", help="Markdown file containing role output.")
    record_ui_replication.add_argument("--content", help="Inline Markdown role output.")
    record_ui_replication.add_argument("--status", help="Override inferred status.")

    record_business_logic = subparsers.add_parser(
        "record-business-logic", help="Record a business logic role output."
    )
    record_business_logic.add_argument("--run-dir", required=True, help="Workflow run directory.")
    record_business_logic.add_argument("--role", required=True, help="Business logic role id to record.")
    record_business_logic.add_argument("--file", help="Markdown file containing role output.")
    record_business_logic.add_argument("--content", help="Inline Markdown role output.")
    record_business_logic.add_argument("--status", help="Override inferred status.")

    record_acceptance = subparsers.add_parser("record-acceptance", help="Record an acceptance role output.")
    record_acceptance.add_argument("--run-dir", required=True, help="Workflow run directory.")
    record_acceptance.add_argument("--role", required=True, help="Acceptance role id to record.")
    record_acceptance.add_argument("--file", help="Markdown file containing role output.")
    record_acceptance.add_argument("--content", help="Inline Markdown role output.")
    record_acceptance.add_argument("--status", help="Override inferred status.")

    generate_ui = subparsers.add_parser(
        "generate-ui-image", help="Generate a UI image through the internal draw-ui integration."
    )
    generate_ui.add_argument("--run-dir", required=True, help="Workflow run directory.")
    generate_ui.add_argument("--prompt", required=True, help="Prompt approved for UI image generation.")
    generate_ui.add_argument("--provider", help="Provider id from run config/imagegen.json. Defaults to active provider.")
    generate_ui.add_argument("--type", default="wide", choices=["classic", "portrait", "square", "ultrawide", "wide"])
    generate_ui.add_argument("--name", default="primary-ui", help="Output name used in metadata.")
    generate_ui.add_argument("--frame", help="Reference frame image path.")
    generate_ui.add_argument("--ref", action="append", default=[], help="Additional reference image path or URL.")
    generate_ui.add_argument(
        "--output",
        default="artifacts/design/generated/primary-ui.png",
        help="Output path, relative to run dir unless absolute.",
    )
    generate_ui.add_argument(
        "--allow-disabled-provider",
        action="store_true",
        help="Allow execution with a disabled provider for controlled tests.",
    )
    generate_ui.add_argument(
        "--skip-env-check",
        action="store_true",
        help="Skip local API-key environment check and let the integration script fail if needed.",
    )
    generate_ui.add_argument(
        "--force",
        action="store_true",
        help="Bypass imagegen approval requirement for local mock/smoke runs.",
    )

    replicate_html = subparsers.add_parser(
        "replicate-ui-html", help="Record or prepare an HTML reconstruction from a UI reference image."
    )
    replicate_html.add_argument("--run-dir", required=True, help="Workflow run directory.")
    replicate_html.add_argument("--reference", required=True, help="Reference mockup/screenshot path.")
    replicate_html.add_argument("--name", help="Stable name for output artifacts.")
    replicate_html.add_argument("--output", help="HTML output path, relative to run dir unless absolute.")
    replicate_html.add_argument("--html-file", help="Existing reconstructed HTML file to record.")
    replicate_html.add_argument("--html", help="Inline reconstructed HTML content.")
    replicate_html.add_argument("--notes-file", help="Markdown notes for the reconstruction agent.")
    replicate_html.add_argument("--notes", help="Inline notes for the reconstruction agent.")
    replicate_html.add_argument("--prompt-output", help="Prompt artifact path.")
    replicate_html.add_argument("--manifest-output", help="Manifest artifact path.")
    replicate_html.add_argument(
        "--require-html",
        action="store_true",
        help="Fail unless --html-file or --html is provided.",
    )
    replicate_html.add_argument(
        "--force",
        action="store_true",
        help="Allow controlled local tests outside the ui_replication phase.",
    )

    verify_html = subparsers.add_parser(
        "verify-ui-html", help="Verify reconstructed HTML against a UI reference image."
    )
    verify_html.add_argument("--run-dir", required=True, help="Workflow run directory.")
    verify_html.add_argument("--html", required=True, help="HTML artifact path.")
    verify_html.add_argument("--reference", required=True, help="Reference mockup/screenshot path.")
    verify_html.add_argument("--name", help="Stable name for validation output.")
    verify_html.add_argument("--out-dir", help="Validation output directory.")
    verify_html.add_argument("--viewport", default="1024x1536", help="Browser viewport, for example 1024x1536.")
    verify_html.add_argument("--session", default="ui-design-verify", help="agent-browser session name.")
    verify_html.add_argument("--full-page", action="store_true", help="Capture full page when reference is full-page.")
    verify_html.add_argument(
        "--candidate-screenshot",
        help="Existing browser screenshot to compare. Bypasses agent-browser.",
    )
    verify_html.add_argument("--prefix", default="verify", help="Output filename prefix for comparison artifacts.")
    verify_html.add_argument(
        "--clip",
        action="append",
        default=[],
        help="Named crop to compare, format name:x,y,w,h. Repeatable.",
    )

    resume = subparsers.add_parser("resume", help="Record an approval decision.")
    resume.add_argument("--run-dir", required=True, help="Workflow run directory.")
    resume.add_argument("--approval", required=True, help="Approval id.")
    resume.add_argument("--decision", required=True, help="approve or reject.")
    resume.add_argument("--comment", help="Decision comment.")
    resume.add_argument("--force", action="store_true", help="Override a non-pending approval.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        run_dir = create_run(args)
        print(f"Created workflow run: {run_dir}")
        print(f"Pending approval: {DEFAULT_APPROVAL_ID}")
        return 0
    if args.command == "status":
        print_status(Path(args.run_dir))
        return 0
    if args.command == "start-docs":
        start_docs_phase(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "start-design":
        start_design_phase(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "start-ui-replication":
        start_ui_replication_phase(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "start-business-logic":
        start_business_logic_phase(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "start-acceptance":
        start_acceptance_phase(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "record":
        record_role_output(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "record-design":
        record_design_output(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "record-ui-replication":
        record_ui_replication_output(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "record-business-logic":
        record_business_logic_output(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "record-acceptance":
        record_acceptance_output(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "generate-ui-image":
        generate_ui_image(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "replicate-ui-html":
        replicate_ui_html(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "verify-ui-html":
        verify_ui_html(args)
        print_status(Path(args.run_dir))
        return 0
    if args.command == "resume":
        resume_run(args)
        print_status(Path(args.run_dir))
        return 0
    parser.error("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
