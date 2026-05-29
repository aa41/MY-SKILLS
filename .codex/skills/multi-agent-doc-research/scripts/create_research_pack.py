#!/usr/bin/env python3
"""Generate a 3+2+1 multi-agent research prompt pack."""

from __future__ import annotations

import argparse
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path


ROLE_DEFINITIONS = [
    {
        "id": "researcher-a",
        "title": "Researcher A - Product and Domain Documentation",
        "phase": "research",
        "prompt": """
You are Researcher A in a 3+2+1 multi-agent research workflow.

Investigate the requirement from a product, user workflow, and domain documentation lens.

Requirement:
{requirement}

Focus on:
- User-facing behavior and acceptance criteria.
- Official product/domain documentation and authoritative references.
- Workflow constraints, terminology, compliance or policy requirements.
- What the implementation must preserve for users.

Return:
- Findings with source links or local file references.
- Recommended approach from this lens.
- Rejected alternatives.
- Assumptions and unanswered questions.
- Confidence: high, medium, or low.
""",
    },
    {
        "id": "researcher-b",
        "title": "Researcher B - Architecture and Implementation",
        "phase": "research",
        "prompt": """
You are Researcher B in a 3+2+1 multi-agent research workflow.

Investigate the requirement from an architecture, implementation, and integration lens.

Requirement:
{requirement}

Focus on:
- APIs, libraries, frameworks, repo integration points, and existing patterns.
- Data flow, interfaces, migration path, compatibility, and maintainability.
- Implementation effort and sequencing.
- Tradeoffs between viable technical approaches.

Return:
- Findings with source links or local file references.
- Recommended implementation approach.
- Rejected alternatives.
- Tests or validation required.
- Confidence: high, medium, or low.
""",
    },
    {
        "id": "researcher-c",
        "title": "Researcher C - Risks and Edge Cases",
        "phase": "research",
        "prompt": """
You are Researcher C in a 3+2+1 multi-agent research workflow.

Investigate the requirement from a risk, edge-case, and failure-mode lens.

Requirement:
{requirement}

Focus on:
- Security, privacy, permissions, data loss, and abuse cases.
- Performance, reliability, concurrency, scale, and rollback risks.
- Version compatibility, platform constraints, and operational concerns.
- Missing tests, monitoring, documentation, and rollout safeguards.

Return:
- Findings with source links or local file references.
- Highest-risk parts of the requirement.
- Recommended mitigations.
- Decision blockers, if any.
- Confidence: high, medium, or low.
""",
    },
    {
        "id": "reviewer-a",
        "title": "Reviewer A - Evidence Audit",
        "phase": "review",
        "prompt": """
You are Reviewer A in a 3+2+1 multi-agent research workflow.

Audit the three researcher outputs for evidence quality. Do not rubber-stamp them.

Requirement:
{requirement}

Researcher outputs:
{research_outputs}

Focus on:
- Unsupported claims, weak sources, stale information, and hallucination risk.
- Contradictions between researchers.
- Missing primary sources or missing repo evidence.
- Assumptions that must be verified before implementation.

Return:
- Evidence quality assessment for each researcher.
- Contradictions and gaps.
- Claims that need verification.
- Which findings are safe to use in the final decision.
- Confidence: high, medium, or low.
""",
    },
    {
        "id": "reviewer-b",
        "title": "Reviewer B - Decision Audit",
        "phase": "review",
        "prompt": """
You are Reviewer B in a 3+2+1 multi-agent research workflow.

Compare the three researcher outputs and recommend the best plan. Do not average opinions.

Requirement:
{requirement}

Researcher outputs:
{research_outputs}

Focus on:
- Feasibility, scope control, cost, implementation sequence, and blast radius.
- Which approach best satisfies the requirement with the least unnecessary complexity.
- What should be deferred or rejected.
- What validation is required before and after implementation.

Return:
- Ranked options.
- Recommended option and decision boundary.
- Rejected options with reasons.
- Implementation sequence.
- Confidence: high, medium, or low.
""",
    },
    {
        "id": "synthesizer",
        "title": "Final Synthesizer - Decision and Plan",
        "phase": "synthesis",
        "prompt": """
You are the final synthesizer in a 3+2+1 multi-agent research workflow.

Make the final decision using the original requirement and the two reviewer outputs.

Requirement:
{requirement}

Reviewer outputs:
{review_outputs}

Return the final answer with these sections:
- Decision: the recommended plan.
- Why: evidence and tradeoffs that justify it.
- Rejected Options: alternatives and why they lost.
- Implementation Plan: ordered steps with likely files, APIs, or docs to touch.
- Risks: unresolved assumptions, missing sources, and validation required.
- Confidence: high, medium, or low, with one sentence explaining why.
""",
    },
]

ARTIFACT_FILES = {
    "researcher-a": "artifacts/01-researcher-a-product-domain.md",
    "researcher-b": "artifacts/02-researcher-b-architecture-implementation.md",
    "researcher-c": "artifacts/03-researcher-c-risk-edge-cases.md",
    "reviewer-a": "artifacts/04-reviewer-a-evidence-audit.md",
    "reviewer-b": "artifacts/05-reviewer-b-decision-audit.md",
    "synthesizer": "artifacts/06-final-synthesis.md",
}

LANGUAGE_INSTRUCTION = """
Language:
- Write the final role output in Chinese by default.
- Use another language only if the user explicitly requests it.
- Keep source titles, API names, code identifiers, commands, file paths, and direct technical terms in their original language when that is clearer.
"""


def normalize_block(value: str) -> str:
    return textwrap.dedent(value).strip()


def artifact_instruction(role_id: str, run_dir: str | None) -> str:
    path = ARTIFACT_FILES[role_id]
    if run_dir:
        path = str(Path(run_dir) / path)
    return normalize_block(
        f"""
        Artifact persistence:
        - Write your final role output as complete Markdown suitable for `{path}`.
        - If your host can write files directly, save the output to `{path}`.
        - If your host cannot write files, return the complete artifact content so the orchestrator can save it verbatim.
        - Start with a short status line: `Status: success`, `Status: partial`, or `Status: failed`.
        - Preserve source links, local file references, assumptions, contradictions, and unresolved questions.
        - Follow the language instruction above.
        """
    )


def build_prompts(requirement: str, run_dir: str | None = None) -> list[dict[str, str]]:
    prompts = []
    for role in ROLE_DEFINITIONS:
        prompt = normalize_block(role["prompt"]).format(
            requirement=requirement.strip(),
            research_outputs="[Paste the three researcher outputs here.]",
            review_outputs="[Paste the two reviewer outputs here.]",
        )
        prompt = (
            f"{prompt}\n\n"
            f"{normalize_block(LANGUAGE_INSTRUCTION)}\n\n"
            f"{artifact_instruction(role['id'], run_dir)}"
        )
        prompts.append(
            {
                "id": role["id"],
                "title": role["title"],
                "phase": role["phase"],
                "prompt": prompt,
                "artifact": ARTIFACT_FILES[role["id"]],
            }
        )
    return prompts


def to_markdown(prompts: list[dict[str, str]]) -> str:
    lines = ["# Multi-Agent Research Prompt Pack", ""]
    for item in prompts:
        lines.extend(
            [
                f"## {item['title']}",
                "",
                f"- Role ID: `{item['id']}`",
                f"- Phase: `{item['phase']}`",
                f"- Artifact: `{item['artifact']}`",
                "",
                "```text",
                item["prompt"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def artifact_header(item: dict[str, str]) -> str:
    return "\n".join(
        [
            f"# {item['title']}",
            "",
            f"- Role ID: `{item['id']}`",
            f"- Phase: `{item['phase']}`",
            "- Status: `pending`",
            "- Requirement: `../requirement.md`",
            f"- Prompt: `../prompts/{item['id']}.md`",
            "- Produced: `pending`",
            "",
            "## Output",
            "",
            "Pending.",
            "",
        ]
    )


def scaffold_run_dir(run_dir: Path, requirement: str, prompts: list[dict[str, str]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompts").mkdir(exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)

    (run_dir / "requirement.md").write_text(requirement.strip() + "\n", encoding="utf-8")
    pack = to_markdown(prompts)
    (run_dir / "research-pack.md").write_text(pack + "\n", encoding="utf-8")

    for item in prompts:
        (run_dir / "prompts" / f"{item['id']}.md").write_text(
            item["prompt"] + "\n", encoding="utf-8"
        )
        artifact_path = run_dir / item["artifact"]
        if not artifact_path.exists():
            artifact_path.write_text(artifact_header(item), encoding="utf-8")

    state = {
        "run_id": run_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "initialized",
        "requirement_path": "requirement.md",
        "research_pack_path": "research-pack.md",
        "roles": [
            {
                "id": item["id"],
                "phase": item["phase"],
                "status": "pending",
                "prompt_path": f"prompts/{item['id']}.md",
                "artifact_path": item["artifact"],
            }
            for item in prompts
        ],
        "final_confidence": None,
    }
    (run_dir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    index_lines = [
        f"# Multi-Agent Research Run: {run_dir.name}",
        "",
        "## Requirement",
        "",
        "- [requirement.md](requirement.md)",
        "",
        "## Status",
        "",
        "- Run status: `initialized`",
        "- Final decision: `pending`",
        "- Final confidence: `pending`",
        "",
        "## Role Artifacts",
        "",
    ]
    for item in prompts:
        index_lines.append(f"- `{item['id']}`: [{item['artifact']}]({item['artifact']})")
    index_lines.extend(
        [
            "",
            "## Source Links Checked",
            "",
            "Pending.",
            "",
            "## Open Questions",
            "",
            "Pending.",
            "",
        ]
    )
    (run_dir / "index.md").write_text("\n".join(index_lines), encoding="utf-8")
    (run_dir / "logs" / "agent-runs.md").write_text(
        "# Agent Runs\n\nPending.\n", encoding="utf-8"
    )


def read_requirement(args: argparse.Namespace) -> str:
    if args.requirement and args.file:
        raise SystemExit("Use either --requirement or --file, not both.")
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.requirement:
        return args.requirement
    raise SystemExit("Provide --requirement or --file.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate role prompts for a 3+2+1 agent research workflow."
    )
    parser.add_argument("--requirement", help="Feature request or research question.")
    parser.add_argument("--file", help="Path to a text/markdown requirement file.")
    parser.add_argument("--output", help="Write output to this path instead of stdout.")
    parser.add_argument(
        "--run-dir",
        help="Create a local artifact run directory with prompts, placeholders, index, and state.",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    requirement = read_requirement(args)
    prompts = build_prompts(requirement, args.run_dir)
    if args.format == "json":
        output = json.dumps({"prompts": prompts}, ensure_ascii=False, indent=2)
    else:
        output = to_markdown(prompts)

    if args.run_dir:
        scaffold_run_dir(Path(args.run_dir), requirement, prompts)

    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
