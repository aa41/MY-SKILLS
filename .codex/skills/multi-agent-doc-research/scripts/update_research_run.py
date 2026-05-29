#!/usr/bin/env python3
"""Update index.md and state.json for a multi-agent research run."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROLE_ARTIFACTS = [
    {
        "id": "researcher-a",
        "phase": "research",
        "path": "artifacts/01-researcher-a-product-domain.md",
    },
    {
        "id": "researcher-b",
        "phase": "research",
        "path": "artifacts/02-researcher-b-architecture-implementation.md",
    },
    {
        "id": "researcher-c",
        "phase": "research",
        "path": "artifacts/03-researcher-c-risk-edge-cases.md",
    },
    {
        "id": "reviewer-a",
        "phase": "review",
        "path": "artifacts/04-reviewer-a-evidence-audit.md",
    },
    {
        "id": "reviewer-b",
        "phase": "review",
        "path": "artifacts/05-reviewer-b-decision-audit.md",
    },
    {
        "id": "synthesizer",
        "phase": "synthesis",
        "path": "artifacts/06-final-synthesis.md",
    },
]

TERMINAL_SUCCESS = {"success"}
URL_RE = re.compile(r"https?://[^\s)>\]]+")
STATUS_RE = re.compile(r"(?:^|\n)(?:[-*]\s*)?Status:\s*`?([A-Za-z_-]+)`?", re.I)
CONFIDENCE_RE = re.compile(
    r"(?:^|\n)(?:[-*]\s*)?(?:Confidence|置信度)[:：]\s*`?([^`\n]+)`?", re.I
)
HEADING_RE = re.compile(r"^(#{1,6}\s+.+|\*\*[^*\n]+\*\*)\s*$", re.M)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def infer_status(text: str) -> str:
    if not text.strip():
        return "missing"
    match = STATUS_RE.search(text)
    if match:
        return match.group(1).strip().lower()
    if "Pending." in text and len(text.strip()) < 400:
        return "pending"
    return "success"


def infer_confidence(text: str) -> str | None:
    matches = CONFIDENCE_RE.findall(text)
    if matches:
        return matches[-1].strip().strip(".")
    section = extract_section(text, ("confidence", "置信度"), max_chars=80)
    if not section:
        return None
    for line in section.splitlines():
        normalized = line.strip().strip("-*` .")
        if normalized:
            return normalized
    return None


def normalize_confidence(value: str | None) -> str | None:
    if not value:
        return None
    lower = value.lower()
    if "high" in lower or "高" in lower:
        return "high"
    if "medium" in lower or "中" in lower:
        return "medium"
    if "low" in lower or "低" in lower:
        return "low"
    return value.strip().strip(".")[:80]


def collect_urls(texts: list[str]) -> list[str]:
    urls: set[str] = set()
    for text in texts:
        for url in URL_RE.findall(text):
            cleaned = url.rstrip(".,;`'\"\\")
            if cleaned:
                urls.add(cleaned)
    return sorted(urls)


def extract_section(text: str, names: tuple[str, ...], max_chars: int = 1200) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        normalized = line.strip().strip("#").strip("*").strip().lower()
        if normalized in names:
            collected: list[str] = []
            for next_line in lines[index + 1 :]:
                if HEADING_RE.match(next_line.strip()) and collected:
                    break
                collected.append(next_line)
            value = "\n".join(collected).strip()
            if value:
                return value[:max_chars].rstrip()
    return ""


def extract_final_decision(final_text: str) -> str:
    if infer_status(final_text) in {"missing", "pending"}:
        return "Pending."
    decision = extract_section(
        final_text, ("decision", "最终决策", "推荐结论"), max_chars=4000
    )
    if decision:
        return decision
    for line in final_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "Pending." in stripped:
            continue
        if stripped.startswith("- ") and any(
            key in stripped for key in ("Role ID:", "Phase:", "Status:", "Requirement:", "Prompt:", "Produced:")
        ):
            continue
        if stripped:
            return stripped[:1200]
    return "Pending."


def extract_open_questions(texts: list[str]) -> list[str]:
    questions: list[str] = []
    seen: set[str] = set()
    section_names = (
        "open questions",
        "unresolved questions",
        "unanswered questions",
        "assumptions and unanswered questions",
        "不确定项",
        "未解决问题",
        "待确认问题",
        "需人工确认",
    )
    for text in texts:
        section = extract_section(text, section_names, max_chars=800)
        if section:
            for line in section.splitlines():
                stripped = line.strip()
                stripped = stripped.lstrip("-*").strip()
                key = re.sub(r"\s+", " ", stripped).strip().lower()
                if stripped and key not in seen:
                    seen.add(key)
                    questions.append(stripped)
    return questions[:20]


def summarize_block(value: str, max_chars: int = 1800) -> str:
    if len(value) <= max_chars:
        return value
    cutoff = value.rfind("\n\n", 0, max_chars)
    if cutoff < 400:
        cutoff = value.rfind("\n", 0, max_chars)
    if cutoff < 400:
        cutoff = max_chars
    return value[:cutoff].rstrip() + "\n\n[Truncated in index; read `artifacts/06-final-synthesis.md` for the full decision.]"


def infer_run_status(artifacts: list[dict], explicit_status: str | None) -> str:
    statuses = {item["status"] for item in artifacts}
    all_success = statuses <= TERMINAL_SUCCESS
    if explicit_status == "completed" and not all_success:
        return "partial" if "failed" in statuses else "in_progress"
    if explicit_status:
        return explicit_status
    if all_success:
        return "completed"
    if "failed" in statuses:
        return "partial"
    if "pending" in statuses or "missing" in statuses:
        return "in_progress"
    return "partial"


def has_completed_synthesis(final_text: str) -> bool:
    if infer_status(final_text) not in TERMINAL_SUCCESS:
        return False
    decision = extract_final_decision(final_text)
    return bool(decision.strip() and decision.strip() != "Pending.")


def load_state(run_dir: Path) -> dict:
    state_path = run_dir / "state.json"
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(run_dir: Path, state: dict) -> None:
    (run_dir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def update_run(run_dir: Path, explicit_status: str | None = None) -> dict:
    state = load_state(run_dir)
    artifacts = []
    artifact_texts = []
    final_text = ""

    for role in ROLE_ARTIFACTS:
        path = run_dir / role["path"]
        text = read_text(path)
        artifact_texts.append(text)
        if role["id"] == "synthesizer":
            final_text = text
        artifacts.append(
            {
                "id": role["id"],
                "phase": role["phase"],
                "status": infer_status(text),
                "prompt_path": f"prompts/{role['id']}.md",
                "artifact_path": role["path"],
                "confidence": normalize_confidence(infer_confidence(text)),
            }
        )

    urls = collect_urls(artifact_texts)
    final_decision = summarize_block(extract_final_decision(final_text))
    final_confidence = normalize_confidence(infer_confidence(final_text))
    open_questions = extract_open_questions(artifact_texts)
    run_status = infer_run_status(artifacts, explicit_status)
    if run_status == "completed" and not has_completed_synthesis(final_text):
        run_status = "in_progress"

    state.update(
        {
            "run_id": state.get("run_id") or run_dir.name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": run_status,
            "requirement_path": state.get("requirement_path", "requirement.md"),
            "research_pack_path": state.get("research_pack_path", "research-pack.md"),
            "roles": artifacts,
            "source_links": urls,
            "final_decision_summary": final_decision,
            "final_confidence": final_confidence,
            "open_questions": open_questions,
        }
    )
    write_state(run_dir, state)
    write_index(run_dir, state)
    return state


def write_index(run_dir: Path, state: dict) -> None:
    lines = [
        f"# Multi-Agent Research Run: {state['run_id']}",
        "",
        "## Requirement",
        "",
        "- [requirement.md](requirement.md)",
        "",
        "## Status",
        "",
        f"- Run status: `{state.get('status', 'unknown')}`",
        f"- Final confidence: `{state.get('final_confidence') or 'pending'}`",
        "",
        "## Final Decision",
        "",
        state.get("final_decision_summary") or "Pending.",
        "",
        "## Role Artifacts",
        "",
    ]
    for role in state.get("roles", []):
        confidence = role.get("confidence") or "n/a"
        lines.append(
            f"- `{role['id']}` ({role['phase']}): `{role['status']}`, "
            f"confidence `{confidence}` - [{role['artifact_path']}]({role['artifact_path']})"
        )

    lines.extend(["", "## Source Links Checked", ""])
    source_links = state.get("source_links") or []
    if source_links:
        lines.extend(f"- {url}" for url in source_links)
    else:
        lines.append("Pending.")

    lines.extend(["", "## Open Questions", ""])
    open_questions = state.get("open_questions") or []
    if open_questions:
        lines.extend(f"- {item}" for item in open_questions)
    else:
        lines.append("Pending.")

    lines.extend(
        [
            "",
            "## Future-Agent Handoff",
            "",
            "Read these files first, in order:",
            "",
            "1. `requirement.md`",
            "2. `index.md`",
            "3. `artifacts/06-final-synthesis.md`",
            "4. Reviewer artifacts if evidence or decision quality needs auditing",
            "5. Researcher artifacts if source detail or dissenting views are needed",
            "",
        ]
    )
    (run_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh index.md and state.json for a multi-agent research run."
    )
    parser.add_argument("--run-dir", required=True, help="Research run directory.")
    parser.add_argument(
        "--status",
        choices=("initialized", "in_progress", "completed", "partial", "blocked"),
        help="Override inferred run status.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = update_run(Path(args.run_dir), args.status)
    print(
        f"Updated {args.run_dir}: status={state['status']}, "
        f"confidence={state.get('final_confidence') or 'pending'}"
    )


if __name__ == "__main__":
    main()
