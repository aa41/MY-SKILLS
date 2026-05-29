Status: success

# Researcher B - Architecture and Implementation

- Role ID: `researcher-b`
- Phase: `research`
- Status: `success`
- Requirement: `../requirement.md`
- Prompt: `../prompts/researcher-b.md`
- Produced: `2026-05-28T20:12:08+08:00`

## Output

## 结论摘要

推荐采用 **“显式 workflow 状态机 + agent 执行层 + skill/MCP 插件层 + artifact-first 仓库结构”** 的架构。

最稳妥的技术路线是：

1. **LangGraph 作为核心编排层**：负责阶段图、状态、checkpoint、并行 researcher/reviewer、human interrupt、resume。
2. **OpenAI Agents SDK 或 Codex subagents 作为 agent 执行层**：负责单个角色的模型调用、工具调用、handoff、guardrails、tracing。
3. **MCP + repo-local skills 作为能力接入层**：统一接入 Figma、Linear/GitHub、图像生成、测试、文档生成、自研脚本。
4. **Artifact ledger 作为事实源**：所有需求、调研、设计、UI 稿、实现计划、补丁、测试报告、审批记录都落盘，状态文件只保存索引和当前状态。
5. **人工介入通过状态机 interrupt/approval 节点表达**：不是靠聊天上下文临时判断，而是以可恢复、可审计的 `approval_request` / `approval_decision` artifact 表达。

该方案兼顾全自动执行和关键节点人工审批，且能逐步落地：先实现 artifact 结构和本地 CLI runner，再替换为 LangGraph/Temporal 等可恢复执行后端。

## 关键发现

### 可编排 Agent 框架比较

- **LangGraph**：显式 StateGraph、checkpoint、subgraph、human-in-the-loop interrupt、resume、并行分支。首选编排层。来源：<https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/wait-user-input/>
- **OpenAI Agents SDK**：Agent、handoff、guardrail、session、tracing 抽象完整，适合作为执行层。来源：<https://developers.openai.com/tracks/building-agents/>
- **Codex Subagents**：适合本地/IDE 执行适配器，并行代码库调研/实现/评审。来源：<https://developers.openai.com/codex/subagents>
- **Temporal**：适合第二阶段生产化 durable execution，LLM 非确定性需放 Activity。来源：<https://docs.temporal.io/>
- **CrewAI Flows**：适合作为局部 skill/crew，不建议做核心编排层。来源：<https://docs.crewai.com/en/concepts/flows>
- **AutoGen**：适合研究/评审型子流程，不建议做主状态机。来源：<https://autogenhub.github.io/autogen/docs/Use-Cases/agent_chat/>
- **Pydantic AI + durable integrations**：Python 类型严格团队可考虑。来源：<https://pydantic.dev/docs/ai/integrations/durable_execution/overview/>

推荐分层：Workflow Orchestrator = LangGraph initially, Temporal later if needed；Agent Runtime = OpenAI Agents SDK / Codex subagents；Tool & Skill Interface = MCP + local skills + deterministic scripts；Artifact Store = repo-local markdown/json/assets；Validation = unit/e2e/visual/a11y/security tests。

## 推荐架构

组件：Graph engine、Agent execution adapter、Skill registry、Artifact store、State store。

数据流：User requirement -> requirement.md -> research pack/prompts -> parallel research artifacts -> review artifacts -> synthesis -> PRD/UX/tech design -> UI generation prompt -> generated mockups -> human design approval -> implementation plan -> code changes -> self-test -> visual comparison -> acceptance checklist -> final approval/release handoff。

核心原则：agent 的聊天输出不是事实源，artifact 才是事实源。每个节点必须读入明确 artifact，写出明确 artifact，并更新 machine-readable state。

## Artifact / State 结构

推荐目录：`.agent-workflows/runs/<run-id>/`，包含 `index.md`、`requirement.md`、`state.json`、`events.jsonl`、`workflow.yaml`、`prompts/`、`artifacts/research`、`artifacts/docs`、`artifacts/design`、`artifacts/implementation`、`artifacts/validation`、`artifacts/acceptance`、`logs/`。

`state.json` 需要包含 `run_id`、`requirement_path`、`status`、`current_phase`、`mode`、`nodes`、`approvals`、`sources`、`confidence`。

`events.jsonl` 记录不可变事件，例如 `node_started`、`artifact_written`、`node_completed`。

## Skill / Subagent / MCP 接入

Codex skill 推荐以 `.agents/skills/<skill>/SKILL.md` 为入口，附带 scripts/references/assets。每个 skill 声明 inputs、outputs、requires、approval_boundaries。

Codex subagent 推荐定义 researcher、designer、implementer、tester、reviewer。researcher/reviewer 默认 read-only；implementer 才允许 workspace write；designer 调用 image/Figma 前先 artifact 化；tester 可运行测试但更新 visual baseline 必须人工审批。

MCP 作为外部工具互操作边界，推荐 Figma MCP、GitHub/Linear/Jira MCP、Playwright MCP、本地 image skill、Internal docs MCP。来源：<https://modelcontextprotocol.io/docs/learn/architecture>

## 自动化与人工介入边界

推荐状态机：created -> intake_normalized -> research_running -> research_review -> docs_draft -> docs_approval_pending -> ui_prompting -> ui_generation_running -> design_approval_pending -> implementation_planning -> code_write_pending_approval -> implementation_running -> self_test_running -> visual_review_pending -> acceptance_pending -> completed。

必须人工介入：需求确认、PRD/技术方案、UI 设计稿选择、写代码前可配置审批、更新 visual baseline、外部系统写操作、最终验收。

## UI 生成与复刻集成

`gpt-image-2` 适合从 PRD/UX spec 生成 2-4 个候选 screen mockup。每张图保存 prompt、model、snapshot、参数、输入 artifact hash。人工选择后通过 Figma MCP 或人工设计工具转为可编辑设计稿，并输出 `ux-spec.md` 和 `design-tokens.md`；不要只保留 PNG。

复刻 UI 推荐链路：Figma MCP 获取结构化设计上下文 -> repo 读取现有组件库/tokens/routing/state -> 生成实现计划 -> 实现 -> Playwright viewport 截图 -> 与 mockup/Figma export 做视觉差异分析 -> 自动修正 1-3 轮 -> 人工确认 baseline。

Playwright 官方支持 screenshot 和 visual comparisons。来源：<https://playwright.dev/docs/test-snapshots>、<https://playwright.dev/docs/screenshots>。Storybook/Chromatic 可补充组件级视觉测试。

## 推荐实施路径

Phase 0：方案和 artifact schema。
Phase 1：本地 workflow runner，支持 `workflow run/resume/status`。
Phase 2：LangGraph 编排。
Phase 3：Skill/MCP registry。
Phase 4：UI 生成和复刻闭环。
Phase 5：生产化 durable execution，必要时引入 Temporal。

## 被拒绝或不优先的替代方案

拒绝单一 mega-agent；不优先只用 CrewAI/AutoGen 对话；不优先一开始直接上 Temporal；拒绝只用图片模型生成 UI 后直接按图写代码；拒绝把 skill 做成自由文本提示集合。

## 测试与验证要求

Workflow 层：状态迁移、resume、failure、idempotency、并行一致性。
Artifact 层：JSON schema、链接、source audit、provenance。
Skill/MCP 层：skill discovery、MCP discovery、permission、sandbox。
UI 复刻层：Playwright smoke/screenshot diff、Storybook visual、响应式 viewport、a11y、baseline approval。
业务逻辑层：unit、integration、contract、mock external services、regression、acceptance checklist。

## 风险

风险包括多 agent 矛盾结论、自动写代码越界、UI 图像稿不可实现、visual diff flaky、skill 数量膨胀、MCP 权限过大、LangGraph 到 Temporal 迁移成本、模型/API 变化。缓解依赖 artifact-first、approval、sandbox、Figma/design tokens、固定渲染环境、skill 显式绑定、MCP allowlist、activity-like 节点契约、model adapter。

## 来源

- LangGraph human-in-the-loop interrupts: <https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/wait-user-input/>
- LangGraph reference / durable execution: <https://langchain-ai.github.io/langgraph/reference/>
- OpenAI building agents / Agents SDK orchestration: <https://developers.openai.com/tracks/building-agents/>
- OpenAI Agents SDK tracing: <https://openai.github.io/openai-agents-python/tracing/>
- OpenAI Codex skills: <https://developers.openai.com/codex/skills/>
- OpenAI Codex subagents: <https://developers.openai.com/codex/subagents>
- OpenAI GPT Image 2 model page: <https://developers.openai.com/api/docs/models/gpt-image-2>
- OpenAI image generation guide: <https://platform.openai.com/docs/guides/image-generation>
- MCP architecture: <https://modelcontextprotocol.io/docs/learn/architecture>
- MCP specification: <https://modelcontextprotocol.io/specification/2025-06-18>
- Figma MCP getting started: <https://help.figma.com/hc/en-us/articles/39216419318551-Get-started-with-the-Figma-MCP-server>
- Temporal docs: <https://docs.temporal.io/>
- CrewAI Flows: <https://docs.crewai.com/en/concepts/flows>
- AutoGen multi-agent conversation: <https://autogenhub.github.io/autogen/docs/Use-Cases/agent_chat/>
- Pydantic AI durable execution overview: <https://pydantic.dev/docs/ai/integrations/durable_execution/overview/>
- Playwright visual comparisons: <https://playwright.dev/docs/test-snapshots>

## Confidence

**high**

理由：核心建议基于官方文档中明确存在的能力。仍需在目标 repo 中验证具体技术栈、现有测试体系、权限模型和可用 MCP/image model 配额。
