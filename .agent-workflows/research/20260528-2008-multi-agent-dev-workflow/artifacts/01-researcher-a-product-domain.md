Status: success

# Researcher A - Product and Domain Documentation

- Role ID: `researcher-a`
- Phase: `research`
- Status: `success`
- Requirement: `../requirement.md`
- Prompt: `../prompts/researcher-a.md`
- Produced: `2026-05-28T20:12:16+08:00`

## Output

## 1. 调研结论

从产品、用户流程和领域文档视角看，推荐把“多 agent 协同开发 workflow”设计成**artifact-first、阶段门禁、可插拔 skill/subagent、默认可追溯**的工作流，而不是一次性全自动“从需求到代码”的黑盒代理。

核心原因：

- OpenAI Agents SDK 将 agent 定义为带有 instructions、tools、handoffs、guardrails、structured outputs 的运行单元，并明确支持两类多 agent 模式：**Manager/agents as tools** 与 **Handoffs**。[OpenAI Agents SDK - Agents](https://openai.github.io/openai-agents-python/agents/)
- OpenAI Agents SDK 的 Human-in-the-loop 流程支持在敏感 tool call 前暂停、收集 approval/rejection，并通过 `RunState` 序列化后恢复，适合关键节点审批。[OpenAI Agents SDK - Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- MCP 是连接 AI 应用与外部系统的开放标准，可把开源或自研工具、数据源、业务系统、工作流暴露为标准工具/资源/提示；其工具规范要求客户端对敏感操作提供清晰 UI 和人工确认。[MCP Intro](https://modelcontextprotocol.io/docs/getting-started/intro), [MCP Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- Codex Skills 官方文档将 skill 定义为可复用 workflow 的 authoring format，包含 `SKILL.md`、scripts、references、assets，适合承载“UI 设计稿生成”“设计稿复刻”“验收测试”等垂直能力。[Codex Skills](https://developers.openai.com/codex/skills)
- Codex Subagents 官方文档说明 Codex 可显式运行并行专业子代理、收集结果、继承 sandbox/approval 策略，适合需求调研、方案评审、代码探索等并行阶段。[Codex Subagents](https://developers.openai.com/codex/subagents)
- UI 设计稿链路中，OpenAI Image API/Responses API 支持 `gpt-image-2` 生成和编辑图片，但官方也提示复杂 prompt 延迟、文字渲染、视觉一致性限制，因此设计稿应作为可审查输入，不应直接视为实现规格。[OpenAI Image Generation](https://developers.openai.com/api/docs/guides/image-generation)
- Figma Dev Mode 的官方定位是设计到代码的 handoff：ready-for-dev 状态、inspect、变量/样式、注释、Code Connect、资源导出等能力可作为从设计稿复刻 UI 的验收依据。[Figma Dev Mode](https://help.figma.com/hc/en-us/articles/15023124644247-Guide-to-Dev-Mode)
- 功能自测与 UI 验收可使用 Playwright 的 screenshot visual comparison，但官方提示截图受 OS、浏览器、硬件等影响，应固定环境并将 baseline 纳入版本控制。[Playwright Visual Comparisons](https://playwright.dev/docs/test-snapshots)
- 需求工程应保留需求信息项、内容、格式和生命周期过程。ISO/IEC/IEEE 29148:2018 官方摘要说明其覆盖需求工程过程、需求相关信息项和格式指南，适合作为需求文档落地的上层依据。[ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html)
- 架构文档可采用 arc42 的轻量结构，覆盖目标、约束、上下文、方案策略、运行时、决策、质量需求、风险、术语表。[arc42 Overview](https://arc42.org/overview)
- 开发进度管理可依赖 GitHub Issues/Projects/PR/Actions 的原生对象：Projects 支持 table/board/roadmap、多视图、自定义字段、自动化和状态更新；branch protection 支持 PR review、status checks、conversation resolution 等 merge gate。[GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects), [GitHub Protected Branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

## 2. 用户可见行为与验收标准

### 2.1 用户可见行为

推荐产品化成一个“开发工作流运行器”，用户每次发起一个需求后，会看到：

1. **Run workspace**
   - 自动创建独立运行目录，例如 `.agent-workflows/dev/<timestamp>-<slug>/`。
   - 所有 agent 输入、输出、设计稿、测试记录、审批记录、最终报告都落盘。

2. **阶段化进度**
   - 阶段包括：需求调研、PRD/设计/技术文档、任务拆解、UI 设计稿生成、设计稿验收、UI 复刻、业务逻辑开发、自测、验收、交付报告。
   - 每阶段有 `pending / running / blocked / approved / rejected / done` 状态。

3. **可插拔角色**
   - 用户可以叠加多个 skill/subagent，例如 `$imagegen-ui`, `$figma-restore`, `$playwright-qa`, `$security-review`。
   - 每个 skill/subagent 只写入自己的 artifact，不覆盖主计划。

4. **自动/人工混合模式**
   - 自动模式：低风险阶段可自动继续，如文档草拟、只读调研、测试运行。
   - 人工审批模式：需求范围冻结、设计稿选择、技术方案确认、文件写入、依赖安装、外部发布、验收签字需要明确 approve/reject。

5. **证据优先**
   - 每个结论必须链接到来源、代码位置、设计稿、测试截图或日志。
   - agent 推断必须标注为“推断”。

### 2.2 最小验收标准

一个合格的 workflow 运行结果至少包含：

- `requirement.md`：原始需求、用户约束、非目标、验收标准。
- `research/`：独立调研 artifact，包含来源链接。
- `prd.md`：用户场景、功能范围、优先级、验收标准。
- `design-brief.md`：信息架构、交互、视觉方向、设计 token 要求。
- `technical-design.md`：架构、数据流、接口、状态、错误处理、测试策略。
- `task-plan.md`：任务拆解、依赖、状态、负责人 agent、阻塞项。
- `ui-designs/`：生成的设计稿、prompt、模型、参数、版本。
- `implementation-log.md`：代码变更、agent 决策、人工审批记录。
- `self-test.md`：单测、集成测试、E2E、视觉对比、手动验收记录。
- `acceptance.md`：需求项到证据的 traceability matrix。
- `run-state.json`：机器可读状态，支持恢复、审计、失败重试。

## 3. 推荐工作流

推荐采用 **Manager Orchestrator + Specialist Subagents + Skill/MCP Tools + Human Approval Gates**。

阶段定义：Intake -> Research -> PRD -> Design Brief -> UI Concept -> Technical Design -> Task Planning -> UI Implementation -> Business Logic -> Self-test -> Acceptance。

关键 artifact 结构建议：`.agent-workflows/dev/<run-id>/` 下包含 `index.md`、`run-state.json`、`requirement.md`、`prompts/`、`research/`、`docs/`、`approvals/`、`ui-designs/`、`implementation/`、`tests/`、`reviews/`、`logs/`。

## 4. Skill/Subagent 接入方式

根据 Codex Skills 官方文档，skill 适合承载可复用流程，目录可包含 `SKILL.md`、scripts、references、assets。推荐每个 skill 暴露 name、description、trigger、input/output contract、allowed tools、approval needs、failure behavior、examples。

Subagent 适合定义 researcher、designer、implementer、tester、reviewer。调研、审查、代码探索并行；设计稿生成可并行多方向但人工选择；业务逻辑默认串行或小批次并行；QA 可并行 unit/e2e/visual/security。

MCP 适合标准化接入 GitHub、Figma、Browser/Playwright、Image generation、Internal tools。必须保留敏感写操作的人类确认。

## 5. 自动化与人工介入边界

可默认自动化：只读 repo 探索、官方文档检索、文档初稿、多方案草拟、低风险测试运行、非破坏性截图、artifact 索引更新。

必须人工审批：需求范围冻结、设计稿最终选择、技术方案采用、新增生产依赖、数据库迁移、权限/计费/认证逻辑变更、大量文件写入或删除、外部系统写操作、更新视觉 baseline、最终验收。

## 6. 风险与拒绝方案

主要风险包括黑盒自动开发偏离用户意图、多 agent 上下文污染、skill 叠加冲突、图像模型设计不可实现、gpt-image-2 文本和一致性限制、视觉测试不稳定、审批疲劳、敏感数据泄露、进度状态失真、追溯缺失。

拒绝方案：单一超级 agent、完全人工驱动、只用 GitHub Actions、只用 Figma/设计稿作为唯一规格、巨型 MCP server。

## 7. 推荐落地计划

Phase 1 定义 workflow spec、`run-state.json` schema、artifact 模板、阶段状态机、role catalog、skill manifest。
Phase 2 实现 research/docs MVP。
Phase 3 接入 UI design loop。
Phase 4 接入 implementation loop。
Phase 5 接入 QA/acceptance loop。

## 8. 假设与未决问题

假设目标用户是开发团队或高级个人开发者，代码仓库使用 Git/GitHub 或可映射类似 issue/PR/checks 模型，UI 可从图片、Figma、设计系统 token 之一进入实现流程。

未决问题：最终运行器实现为 Codex skill、独立 CLI、GitHub App 还是 MCP server；是否支持 Linear/Jira；设计稿是否必须落 Figma；审批身份签名是否满足企业审计；是否支持多模型供应商；视觉复刻可接受误差如何定义。

## 9. 置信度

Confidence: high

原因：关键结论由 OpenAI Agents SDK、Codex Skills/Subagents、MCP、GitHub、Figma、Playwright、ISO/arc42 等官方或权威文档支撑；实现层面的精确 schema 和 CLI 行为需后续由 architecture researcher 深挖。
