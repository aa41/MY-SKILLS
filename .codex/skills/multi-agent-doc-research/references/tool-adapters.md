# Tool Adapters

Use this reference only when adapting the workflow to a specific agent host.

## Codex

Use `multi_agent_v1.spawn_agent` only when the user explicitly requested subagents, delegation, or parallel agent work. For this skill, that requirement is usually satisfied by requests such as "agent-team", "启动 3 个 agent", "parallel agents", or "3+2+1 agents".

Recommended sequence:

1. Create the run directory with `create_research_pack.py --run-dir ...`.
2. Spawn three research agents at once.
3. Work locally on normalization, source list, repo inspection, and run index upkeep while they run.
4. Wait for all researchers only when reviewer prompts need their outputs.
5. Save each researcher final message verbatim to its artifact path before spawning reviewers.
6. Spawn two reviewers at once with raw researcher artifact contents.
7. Save each reviewer final message verbatim to its artifact path before synthesis.
8. Use a final synthesizer subagent only for substantial decisions; otherwise synthesize locally.
9. Save final synthesis, run `update_research_run.py --run-dir ... --status completed`, then close agents.

Run `update_research_run.py --run-dir ...` after each phase if the user or another model may inspect progress before the full run completes.

Use `agent_type: explorer` for read-only codebase/document investigation. Use `agent_type: worker` only if an agent must edit files, which is not part of the default research workflow.

## Claude Code

Use the Task tool when available. Give each Task a role-specific prompt from `create_research_pack.py`.

If Task is unavailable, run separate Claude Code sessions:

- Session 1-3: independent research prompts.
- Session 4-5: review prompts with the original requirement and all research outputs.
- Session 6: synthesis prompt with the original requirement and both review outputs.

After every Task/session, paste or write the result into the expected artifact file before starting any dependent session. Treat the artifact directory, not the conversation, as the source of truth.

After saving artifacts, run `update_research_run.py --run-dir ...` from the skill directory or by absolute path.

## Cursor

Use separate Agent or Composer sessions. Keep the context clean:

- Researchers receive only the original requirement, repo context, and their role prompt.
- Reviewers receive the original requirement and all three researcher outputs.
- The synthesizer receives the original requirement and both reviewer outputs.

Save each Agent/Composer result to the run directory immediately. If Cursor sessions cannot write into the target repo, copy their final output into the artifact files before moving to the next phase.

After copying outputs, run `update_research_run.py --run-dir ...` so `index.md` remains current.

## Manual Runner

When no subagent feature exists, generate Markdown:

```bash
python3 scripts/create_research_pack.py --requirement "..." --output research-pack.md
```

Run the prompts in order, then paste outputs into the next phase placeholders.

When running manually, keep this handoff order:

1. Fill `artifacts/01-*` through `03-*` from the researcher outputs.
2. Paste those three artifact contents into reviewer prompts.
3. Fill `artifacts/04-*` and `05-*` from reviewer outputs.
4. Paste those two artifact contents into the synthesizer prompt.
5. Fill `artifacts/06-final-synthesis.md`.
6. Run `update_research_run.py --run-dir ... --status completed` to update `index.md` and `state.json`.
