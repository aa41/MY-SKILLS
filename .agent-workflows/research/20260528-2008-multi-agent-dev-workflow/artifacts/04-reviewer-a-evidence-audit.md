Status: success

# Reviewer A - Evidence Audit

- Role ID: `reviewer-a`
- Phase: `review`
- Status: `success`
- Requirement: `../requirement.md`
- Prompt: `../prompts/reviewer-a.md`
- Produced: `2026-05-28T20:25:10+08:00`

## Output

## 审计结论

三份 researcher artifact 的总体方向一致：**artifact-first、显式阶段、专业 subagent/skill、最小权限、关键节点人工 gate、可恢复/可审计状态机**。这些原则有较强证据基础，可进入 final synthesis。

但不能 rubber-stamp 的部分也很明显：Researcher B 对 **LangGraph 作为“最稳妥核心编排层”** 的结论强于其证据；A/B 对 OpenAI Codex Skills/Subagents、`gpt-image-2`、Figma MCP、LangGraph 等动态产品能力的引用需要在实施前重新核对官方文档；三者都缺少目标 repo 证据、现有工具链证据、账号/权限/预算/合规证据。因此最终方案应把“推荐原则”与“待验证技术选型”分开。

最终证据置信度：**medium-high**。原则层面 high；具体框架/API/目录/schema 层面 medium。

## 1. Researcher A 证据质量

Researcher A 的产品/领域结论证据质量较好。其核心来源多为官方或权威文档：OpenAI Agents SDK、OpenAI Agents SDK Human-in-the-loop、MCP Intro/Tools specification、Codex Skills/Subagents、Figma Dev Mode、Playwright visual comparisons、ISO/IEC/IEEE 29148、arc42、GitHub Projects/branch protection。

可安全使用的发现：artifact-first 而不是黑盒全自动 agent；Manager Orchestrator + specialist subagents + tools/skills；需求确认、设计稿选择、技术方案确认、写入/删除/外部发布/视觉 baseline/最终验收设为人工 gate；UI 图片生成稿不能直接等同于实现规格；Playwright 可用于 UI 复刻验证但需固定环境和审查 baseline；ISO 29148、arc42 可作为文档结构参考。

证据弱点：A 的 artifact 结构、验收标准、状态名是合理设计建议，不是引用来源直接规定；`gpt-image-2` 能力、参数、价格、区域、数据保留等动态信息实施前必须重新查官方文档；Figma/GitHub 能力取决于账号 plan、权限和工具链；A 的 confidence 对 schema/API 层偏高。

## 2. Researcher B 证据质量

Researcher B 的架构分层清晰，引用包括 LangGraph HITL/reference、OpenAI building agents、OpenAI Agents SDK tracing、Codex Skills/Subagents、MCP architecture/spec、Figma MCP、Temporal、Playwright。

可安全使用的发现：显式 workflow state machine 必要；每个节点读写明确 artifact 并产生 state/events；human approval 应建模为可恢复状态/事件；UI 复刻应读取 repo 组件库/tokens/routing/state，再用 Playwright/visual/a11y 验证；Temporal 适合作为后续 durable execution 候选；测试矩阵覆盖 workflow、artifact、skill/MCP、UI、业务逻辑是合理的。

证据弱点：LangGraph 作为最终核心编排层的证据不足，只能作为候选或 MVP prototype；OpenAI Agents SDK/Codex subagents 与 LangGraph 互操作是架构推断；Codex skill 路径需核实；schema、状态名、目录结构都是 proposal，缺少 prototype 证据。

## 3. Researcher C 证据质量

Researcher C 的风险识别较强，来源包括 OWASP LLM Top 10、OWASP MCP Top 10、OpenAI Agents SDK Guardrails、OpenSSF Scorecard、SLSA、OpenAI data controls、OpenAI Agents SDK Tracing、GitHub Actions Security、U.S. Copyright Office AI Copyrightability Report。

可安全使用的发现：prompt injection、excessive agency、supply chain、tool poisoning、over-permission、audit/logging gaps 是核心风险；tool/skill/subagent 必须有 manifest、权限边界、版本 pin、来源、owner、side effects、approval requirements；tracing/checkpoint/logs 默认不应记录 secrets、客户数据、完整源码、完整 prompt 或原始图片；CI/CD 凭证最小权限；自测和验收不能由同一开发 agent 闭环完成；上传真实客户素材、用户头像、商标、竞品页面、商业机密截图到图像模型前必须有人类授权判断。

证据弱点：部分注入来源是安全经验推断；OWASP MCP Top 10 需确认版本成熟度；临时/迁移域名的 LangGraph 链接不应用作 final 关键证据；ZDR/MAM/DPA 等需按目标账号合同核验；AI-assisted provenance 需具体化为 artifact hash、model/version metadata、approval log、source links。

## 4. 矛盾与不一致

Orchestrator 选型：A 倾向 Manager Orchestrator，B 明确推荐 LangGraph，C 不选择具体框架。final 应先定义框架无关 contract，MVP 可用轻量 runner 或 LangGraph prototype，验证后再定框架。

Artifact 目录结构：A/B/C 不一致。建议 final 区分 `.agent-workflows/research/<run-id>/` 与 `.agent-workflows/dev/<run-id>/`，并声明是 proposal。

Skill/subagent 入口：A/B/C 互补，但 exact filesystem layout、manifest 字段、lockfile 格式需按本地/目标 host 验证。

自动化边界：采用 C 的风险优先边界作为默认安全基线，再允许项目级配置放宽。

UI 链路：三者兼容。最终应采用“图片模型只生成候选视觉方向；最终实现依据必须是结构化 UX spec、tokens、组件映射和验收截图；敏感素材上传需要人工批准”。

## 5. 实施前必须验证

目标 repo 技术栈、测试体系、CI/CD、design system、权限模型、issue/PR 工作流；OpenAI `gpt-image-2` 可用性/API/参数/价格/rate limit/数据保留；Codex Skills/Subagents 当前机制；MCP server/transport/auth/tool confirmation；LangGraph 版本/API/checkpoint/interrupt/resume；Figma 权限和 plan；GitHub/Linear/Jira 设置；安全合规和日志保留；图像版权授权；视觉差异阈值、viewport、a11y baseline、验收签名格式、traceability matrix 字段。

## 6. Final Decision 可安全采用的发现

- artifact-first。
- 显式 workflow/state machine。
- 角色分工。
- 插件化 skill/subagent/MCP 接入，声明 inputs/outputs/permissions/side effects/approval boundaries，支持 pin/lock。
- 默认最小权限。
- 支持全自动与人工 gate 混合。
- UI 链路：生成候选图 -> 人工选择 -> 结构化设计规格/tokens -> UI 复刻 -> Playwright/visual/a11y -> 人工验收。
- 测试与验收独立于开发 agent。
- 风险覆盖 prompt injection、tool poisoning、over-permission、supply chain、日志隐私、并发写入、CI/CD 凭证、视觉 baseline 漂移。

## 7. 不应直接采用或需降级表述

不应写成“LangGraph 是最终核心编排层”；不应直接采用具体目录结构/schema 字段为最终标准；不应把 `gpt-image-2` 动态能力写成静态事实；不应假设 Figma/GitHub/Playwright baseline 在目标环境中已经可用；不应假设 manifest 足以保证开源 skill 安全；不应把 ISO/arc42 扩展为具体文件名强制标准。

## 8. 推荐证据权重

高权重：C 的风险边界、A 的产品阶段/gate、B 的 artifact/state machine 思路。
中高权重：MCP/skill/subagent 插件化、Playwright visual validation、Figma handoff、GitHub branch protection/Projects。
中权重：LangGraph/Temporal/CrewAI/AutoGen/Pydantic AI 框架比较。
低权重：具体目录名、具体 schema 字段、具体 skill 路径、具体状态枚举、未验证模型/API 参数。

## 9. Final Confidence

Confidence: **medium-high**

理由：三份 artifact 对工作流原则和风险控制形成强一致性，并且多数核心依据来自官方或行业一手来源；但具体实施技术选型、动态 API 能力、本地 Codex/skill/subagent 机制、目标 repo 约束和合规条件尚未验证。
