---
name: multi-agent-doc-research
description: Multi-agent document and implementation research workflow for feature requests, technical proposals, architecture decisions, dependency choices, and product requirement investigation. Use when the user asks for an agent-team style process, parallel agents, 3 research agents plus 2 reviewers plus 1 final synthesizer, independent document research, comparing implementation plans, validating competing proposals, or producing a final recommended approach from multiple agent findings. Supports Codex subagents, Claude Code task agents, Cursor agents, and manual prompt-pack execution.
---

# Multi-Agent Doc Research

## Overview

Use a 3+2+1 agent workflow to investigate the same user requirement from independent angles, critique the findings, and produce one final decision. Prefer native subagent/task tools when available; otherwise generate a prompt pack and run each role manually in Codex, Claude Code, Cursor, or another agent runner.

This skill is artifact-first. Every researcher output, reviewer output, synthesis output, prompt pack, and decision record must be written to a local run directory so the user and future agents can recover context without depending on chat history.

Default research language is Chinese. Unless the user explicitly requests another language, write researcher outputs, reviewer outputs, final synthesis, `index.md` summaries, and final user-facing answers in Chinese. Keep source titles, API names, code identifiers, file paths, and direct technical terms in their original language when that is clearer.

When updating this skill, modify the source skill directory first. Treat copied or installed skill directories as deployment targets, not sources of truth. After changing source files, sync the whole skill directory into the local runtime location if needed.

## Quick Start

1. Restate the requirement in one paragraph, including constraints, target repo, success criteria, and sources that must be checked.
2. Create a run directory before launching agents. Prefer `.agent-workflows/research/<YYYYMMDD-HHMM>-<short-slug>/` inside the target repo. If the current directory is not a repo, use a user-approved local directory.
3. Run `scripts/create_research_pack.py` with `--run-dir` when reusable prompts and artifact scaffolding are useful:

```bash
python3 /path/to/multi-agent-doc-research/scripts/create_research_pack.py \
  --requirement "USER REQUIREMENT HERE" \
  --run-dir .agent-workflows/research/20260528-1400-feature-x \
  --output /tmp/research-pack.md
```

4. Launch three research agents in parallel using the three researcher prompts.
5. Save each researcher result verbatim to the run directory before launching reviewers.
6. Launch two reviewer agents in parallel after all researcher outputs are saved.
7. Save each reviewer result verbatim to the run directory before synthesis.
8. Launch one final synthesizer agent, or synthesize locally, using only the original requirement and the two reviewer outputs.
9. Save the final synthesis and update the run index before returning the final answer:

```bash
python3 /path/to/multi-agent-doc-research/scripts/update_research_run.py \
  --run-dir .agent-workflows/research/20260528-1400-feature-x \
  --status completed
```

10. Return a final answer with the chosen approach, rejected alternatives, evidence quality, risks, next implementation steps, and the local run directory path.

## Artifact Requirements

Use this directory layout for each run:

```text
.agent-workflows/
  research/
    <run-id>/
      index.md
      requirement.md
      research-pack.md
      state.json
      prompts/
        researcher-a.md
        researcher-b.md
        researcher-c.md
        reviewer-a.md
        reviewer-b.md
        synthesizer.md
      artifacts/
        01-researcher-a-product-domain.md
        02-researcher-b-architecture-implementation.md
        03-researcher-c-risk-edge-cases.md
        04-reviewer-a-evidence-audit.md
        05-reviewer-b-decision-audit.md
        06-final-synthesis.md
      logs/
        agent-runs.md
```

Artifact rules:

- Save raw role outputs verbatim. Do not overwrite a raw artifact with a summary.
- If a role fails or times out, create its artifact anyway and mark `Status: failed` or `Status: timed_out`, including the error and the missing evidence.
- Keep `index.md` current. It must list the original requirement, run status, role artifacts, source links checked, final decision, and open questions.
- Keep `state.json` machine-readable. It must track `run_id`, `requirement_path`, role statuses, artifact paths, timestamps when available, and final confidence.
- Keep prompts under `prompts/` so future models can reproduce or critique the run.
- Use relative links in `index.md` so the directory remains portable.
- If the agent host cannot write files directly, the orchestrating agent must write the subagent's final message into the correct artifact file immediately after receiving it.
- Run `scripts/update_research_run.py --run-dir <run-dir>` after saving each phase's artifacts. This refreshes `index.md` and `state.json` for user review and future-agent handoff.
- Do not mark a run `completed` unless all required role artifacts are present, the synthesizer artifact has a successful status, and `index.md` / `state.json` were regenerated from artifacts after synthesis.

Each Markdown artifact should start with this header:

```markdown
# <Role Title>

- Role ID: `<role-id>`
- Phase: `<research|review|synthesis>`
- Status: `<success|failed|timed_out|partial>`
- Requirement: `../requirement.md`
- Prompt: `../prompts/<role-id>.md`
- Produced: `<ISO-8601 timestamp if available>`

## Output
```

After the header, include the role's complete output.

## Agent Roles

Use these roles exactly unless the user specifies a different structure.

- `researcher-a`: Product/domain documentation lens. Find user-facing requirements, workflow implications, authoritative docs, and constraints.
- `researcher-b`: Architecture/implementation lens. Find APIs, libraries, repo integration points, migration path, effort, and technical tradeoffs.
- `researcher-c`: Risk/edge-case lens. Find security, privacy, performance, maintainability, compatibility, failure modes, and testing requirements.
- `reviewer-a`: Evidence audit. Check source quality, missing citations, contradictions, unverified claims, and hallucination risk across all three research outputs.
- `reviewer-b`: Decision audit. Compare feasibility, scope, cost, implementation sequencing, and choose the strongest proposal with explicit reasoning.
- `synthesizer`: Final decision. Combine the two reviewer outputs into one recommendation and implementation plan.

## Native Subagent Workflow

When the host supports subagents, delegate only the bounded role prompts. Keep orchestration local.

For Codex with `multi_agent_v1`:

1. Create the run directory and prompt files first. Do this before spawning any subagent.
2. Spawn `researcher-a`, `researcher-b`, and `researcher-c` in parallel. Pass the same normalized requirement, the role-specific prompt, and the expected artifact path.
3. Wait for all three. Save each completed output to its artifact path before starting reviewers. If one agent fails or times out, create a failure artifact and continue with the available outputs while marking the gap.
4. Spawn `reviewer-a` and `reviewer-b` in parallel. Give them the original requirement and the raw researcher artifact contents. Do not give them your preferred answer.
5. Wait for both reviewers. Save each reviewer output to its artifact path before synthesis.
6. Spawn `synthesizer` with the original requirement and raw reviewer artifact contents, or synthesize locally if that is faster.
7. Save `artifacts/06-final-synthesis.md`, update `index.md`, update `state.json`, then close subagents.

For Claude Code:

- Use the Task tool for each role when available.
- Save each Task result to the run directory before launching dependent Tasks.
- If the Task tool is unavailable, run separate Claude Code sessions with the generated prompts and paste collected outputs into the next phase. Save each output file before continuing.

For Cursor:

- Use separate Agent/Composer sessions for the three researcher prompts, then two review sessions, then one synthesis session.
- Keep each session scoped to its role. Do not let reviewers inspect hidden orchestration notes or preferred conclusions.
- Save each session result into the expected artifact file before launching the next phase.

## Output Contract

Final output should be concise and decision-oriented:

- `Decision`: the recommended plan.
- `Why`: evidence and tradeoffs that justify it.
- `Rejected Options`: alternatives and why they lost.
- `Implementation Plan`: ordered steps with likely files, APIs, or docs to touch.
- `Risks`: unresolved assumptions, missing sources, and validation required.
- `Confidence`: high, medium, or low, with one sentence explaining why.

## Quality Rules

- Prefer primary sources: official docs, repo files, standards, API references, design docs, issue trackers, and source code.
- Browse or fetch current docs when facts are likely to have changed, such as APIs, pricing, model names, dependency versions, regulations, or product behavior.
- Separate evidence from inference. Label assumptions clearly.
- Do not average opinions. The final recommendation must choose a plan and explain the decision boundary.
- If the requirement is underspecified, continue with reasonable assumptions and list them unless the missing detail would make research misleading.
- Avoid leaking one researcher's output to another researcher. Independence is the point of the first phase.
- Do not rely on chat history as the source of truth. The run directory is the source of truth after a role completes.
- Do not summarize away failed or contradictory evidence. Preserve the raw output and let reviewers/synthesizer adjudicate it.
- Before the final response, verify that `index.md`, `state.json`, and `artifacts/06-final-synthesis.md` exist and reflect the current run.
- Prefer Chinese for all generated research/review/synthesis content unless the user explicitly asks for another language. Preserve English for source names, commands, identifiers, and quoted API terms when needed.

## Resources

- `scripts/create_research_pack.py`: generates Markdown or JSON role prompts for the 3+2+1 workflow.
- `scripts/update_research_run.py`: refreshes `index.md` and `state.json` from saved role artifacts.
- `references/tool-adapters.md`: host-specific notes for Codex, Claude Code, Cursor, and manual execution.
