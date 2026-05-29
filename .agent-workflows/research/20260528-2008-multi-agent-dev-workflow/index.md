# Multi-Agent Research Run: 20260528-2008-multi-agent-dev-workflow

## Requirement

- [requirement.md](requirement.md)

## Status

- Run status: `completed`
- Final confidence: `high`

## Final Decision

推荐方案是：**先设计并实现一个框架无关的 artifact-first workflow contract 与本地 runner，再把 LangGraph、OpenAI Agents SDK、Codex subagents、MCP、Figma、gpt-image-2、Playwright 等能力作为可插拔执行/工具适配器逐步接入。**

最终架构采用四层：

1. **Workflow Orchestrator**
   - 第一版：repo-local runner + 明确状态机 + `state.json` / `events.jsonl` / approval artifacts。
   - 第二版：用 LangGraph 或等价图编排框架 prototype 验证 checkpoint、parallel branches、interrupt/resume。
   - 生产化阶段：只有在跨天运行、多用户并发、可靠重试、任务队列、审计后台成为硬需求后，再评估 Temporal。

2. **Agent Execution Layer**
   - Codex subagents、OpenAI Agents SDK、Claude/Cursor/manual runner 都作为执行适配器。
   - researcher/reviewer 默认 read-only；designer 只能写设计 artifact；implementer 才允许 workspace-write；tester 可运行测试但不能降低断言或自行更新 visual baseline。

3. **Skill/MCP Plugin Layer**
   - skill/subagent/MCP server 必须通过 manifest 和 lockfile 接入。
   - 每个能力声明 `name`、`version`、`source`、`pinned_ref`、`inputs`、`outputs`、`permissions`、`side_effects`、`approval_required_for`。
   - 默认 deny；网络、外部写 API、secrets、部署、baseline 更新、生产数据访问都必须审批。

4. **Artifact Ledger**
   - artifact 是事实源，chat history 不是事实源。
   - 每个节点必须读入明确 artifact，写出明确 artifact，更新 machine-readable state，并追加不可变 event。
   - 最终验收依赖 `acceptance.md` 中的需求项到证据 traceability matrix。

## Role Artifacts

- `researcher-a` (research): `success`, confidence `high` - [artifacts/01-researcher-a-product-domain.md](artifacts/01-researcher-a-product-domain.md)
- `researcher-b` (research): `success`, confidence `n/a` - [artifacts/02-researcher-b-architecture-implementation.md](artifacts/02-researcher-b-architecture-implementation.md)
- `researcher-c` (research): `success`, confidence `high` - [artifacts/03-researcher-c-risk-edge-cases.md](artifacts/03-researcher-c-risk-edge-cases.md)
- `reviewer-a` (review): `success`, confidence `high` - [artifacts/04-reviewer-a-evidence-audit.md](artifacts/04-reviewer-a-evidence-audit.md)
- `reviewer-b` (review): `success`, confidence `n/a` - [artifacts/05-reviewer-b-decision-audit.md](artifacts/05-reviewer-b-decision-audit.md)
- `synthesizer` (synthesis): `success`, confidence `high` - [artifacts/06-final-synthesis.md](artifacts/06-final-synthesis.md)

## Source Links Checked

- https://arc42.org/overview
- https://autogenhub.github.io/autogen/docs/Use-Cases/agent_chat/
- https://developers.openai.com/api/docs/guides/image-generation
- https://developers.openai.com/api/docs/guides/your-data
- https://developers.openai.com/api/docs/models/gpt-image-2
- https://developers.openai.com/codex/skills
- https://developers.openai.com/codex/skills/
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/tracks/building-agents/
- https://docs.crewai.com/en/concepts/flows
- https://docs.github.com/en/actions/reference/security
- https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- https://docs.langchain.com/oss/python/langgraph/use-time-travel
- https://docs.temporal.io/
- https://github.com/ossf/scorecard
- https://help.figma.com/hc/en-us/articles/15023124644247-Guide-to-Dev-Mode
- https://help.figma.com/hc/en-us/articles/39216419318551-Get-started-with-the-Figma-MCP-server
- https://langchain-5e9cc07a.mintlify.app/oss/python/langgraph/persistence
- https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/wait-user-input/
- https://langchain-ai.github.io/langgraph/reference/
- https://modelcontextprotocol.io/docs/getting-started/intro
- https://modelcontextprotocol.io/docs/learn/architecture
- https://modelcontextprotocol.io/specification/2025-06-18
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- https://openai.github.io/openai-agents-js/guides/guardrails/
- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/human_in_the_loop/
- https://openai.github.io/openai-agents-python/tracing/
- https://owasp.org/www-project-mcp-top-10/
- https://owasp.org/www-project-top-10-for-large-language-model-applications/
- https://platform.openai.com/docs/guides/image-generation
- https://playwright.dev/docs/screenshots
- https://playwright.dev/docs/test-snapshots
- https://pydantic.dev/docs/ai/integrations/durable_execution/overview/
- https://slsa.dev/spec/latest/
- https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-2-Copyrightability-Report.pdf
- https://www.iso.org/standard/72089.html

## Open Questions

Pending.

## Future-Agent Handoff

Read these files first, in order:

1. `requirement.md`
2. `index.md`
3. `artifacts/06-final-synthesis.md`
4. Reviewer artifacts if evidence or decision quality needs auditing
5. Researcher artifacts if source detail or dissenting views are needed
