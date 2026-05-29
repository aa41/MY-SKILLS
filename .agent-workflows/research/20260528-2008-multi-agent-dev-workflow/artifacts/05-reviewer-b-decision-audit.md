Status: success

# Reviewer B - Decision Audit

- Role ID: `reviewer-b`
- Phase: `review`
- Status: `success`
- Requirement: `../requirement.md`
- Prompt: `../prompts/reviewer-b.md`
- Produced: `2026-05-28T20:26:00+08:00`

## Output

## 决策结论

推荐采用 **Researcher B 的“显式 workflow 状态机 + agent 执行层 + skill/MCP 插件层 + artifact-first 仓库结构”作为主方案**，并强制吸收 Researcher C 的权限、安全、锁定、审计和独立验收约束；Researcher A 的产品化阶段和用户可见 artifact 作为流程定义与交付体验参考。

不建议把三份方案平均合并。最可落地路线是：

> **先做 repo-local artifact-first workflow runner 和 schema，再引入 LangGraph 状态机；OpenAI Agents/Codex subagents 只作为执行适配器；skill/MCP 通过 manifest/lock/permission 接入；Temporal、完整平台化 UI、企业级插件市场延后。**

该方案满足需求覆盖范围，同时把初始 blast radius 控制在本地运行目录、文档产物、显式审批和可回滚状态机内。

## Ranked Options

### 1. 推荐：B 主线 + C 风险边界 + A 产物体验

内容：本地 workflow runner、artifact/state/events schema、阶段状态机、skill/subagent registry、审批 gate、UI 生成/复刻闭环、QA/acceptance traceability。

胜出原因：可实施性最高；范围可控；状态机 interrupt/approval 明确支持全自动与人工介入；blast radius 小；C 的 least privilege、locks、provenance、non-self-verifying QA 可直接成为 schema 和 gate；A 的阶段和用户可见 artifact 补齐交付体验。

### 2. 次选：A 的 artifact-first phased workflow

优点：用户流程完整。缺点：架构执行细节不足。适合作为 UX/PRD 模板，不作为主工程架构。

### 3. 风险优先：C 的 gated automation 安全框架

优点：指出真正高风险点。缺点：不是完整实现架构。适合作为强制约束和验收门槛，不作为主开发路线。

## Recommended Option

采用四层架构：

1. Workflow Orchestrator：初期 repo-local CLI/runner + 明确状态机；中期 LangGraph 负责 checkpoint、parallel branches、interrupt/resume；后期只有需要长时间运行、跨服务恢复、企业级 SLA 时再评估 Temporal。
2. Agent Execution Layer：Codex subagents / OpenAI Agents SDK 作为角色执行器。每个 agent 只读写约定 artifact。researcher/reviewer 默认只读；implementer 才允许 workspace write；tester 可运行测试但不能自行降低断言或更新 baseline。
3. Skill/MCP Plugin Layer：skill/subagent/MCP 全部通过 manifest 注册，必须有 `name/version/source/pinned_ref/permissions/inputs/outputs/side_effects/approval_required_for`，使用 `skills.lock`、`subagents.lock`、`model-versions.lock` 固定版本与来源。
4. Artifact Ledger：artifact 是事实源，chat history 不是事实源。`state.json` 只保存状态、索引、hash、当前阶段和审批引用；`events.jsonl` 保存不可变事件；每个阶段有输入 artifact、输出 artifact、验证结果和审批记录。

## Decision Boundary

适用于：可逐步实现的多 agent 开发 workflow；覆盖需求、文档、UI 设计稿、UI 复刻、业务开发、自测验收；需要同时支持全自动和人工 gate；允许先做本地 runner；skill/subagent 来源混合。

不适用于：期望一次性完全无人值守从一句话到生产发布；第一版直接要求多租户、企业权限、长期 durable execution；不愿维护 artifact/schema/approval 约束。

## Rejected Options

拒绝单一 mega-agent；拒绝一开始直接上 Temporal；拒绝只用 CrewAI/AutoGen 对话式协作；拒绝只用图片模型生成 UI 后按图写代码；拒绝无约束动态加载 skill/MCP。

## Implementation Sequence

Phase 0：方案冻结与 schema，产出 `workflow.yaml`、`state.schema.json`、`event.schema.json`、`artifact-contract.md`、`approval-policy.md`、`skill-manifest.schema.json`、`permissions.yaml`。

Phase 1：本地 artifact-first runner MVP，支持 `workflow run/status/resume`、创建 run dir、写入 `requirement.md`/`state.json`/`events.jsonl`/`index.md`、状态迁移、失败恢复、approval artifact。不做真实业务代码自动修改、大规模外部写入、Temporal。

Phase 2：research/docs workflow，并行 researcher、reviewer 决策审计、synthesizer 生成 PRD/design brief/technical design/task plan、source/provenance、scope gate、docs approval gate。

Phase 3：skill/subagent registry，加载 manifest、生成 locks、权限判断、MCP allowlist、tool 参数 schema 校验和日志脱敏。

Phase 4：UI 生成与复刻闭环，从 PRD/design brief 生成 2-4 个 UI mockup，保存 prompt/model/参数/hash/图片，人工选择，生成 `ux-spec.md`、`design-tokens.md`、组件映射，Playwright 多 viewport 验证，baseline 人工审批。

Phase 5：业务逻辑开发与 QA/acceptance，task-plan 驱动代码变更，单 writer 或文件 lock，unit/integration/e2e/visual/a11y，非实现 agent review，`acceptance.md` 建立需求到证据 traceability matrix。

Phase 6：生产化增强，考虑 Temporal、GitHub/Linear/Jira 深度集成、企业权限审计、密钥治理、多租户 Web UI、skill marketplace/组织 registry。

## Required Validation

实现前必须验证目标 repo 技术栈、测试框架、包管理器、UI 框架；是否允许 agent 写代码、安装依赖、访问私有 repo、访问外部网络；`gpt-image-2` 或替代图像模型可用性、价格、速率限制、数据保留；是否需要 Figma MCP；组织合规要求。

MVP 后必须验证状态迁移、artifact schema、approval gate、skill 权限、并发一致性、UI 多 viewport/visual/a11y、QA 独立性、日志脱敏。

## Scope Control

第一版不要做：多租户平台、可视化 DAG 编辑器、skill 市场、自动生产发布、自动数据库迁移执行、长周期 Temporal 集群、完整 Figma 双向同步、模型自主权限升级。

第一版必须做：本地 run directory、artifact contract、状态机和 resume、approval artifact、skill manifest/lock、最小 research -> docs -> decision gate 闭环、风险和权限默认 deny。

## Confidence

**high**

三份 researcher artifact 在大方向上相互一致：artifact-first、显式阶段、skill/subagent 可插拔、人工 gate、UI 生成需审查、QA 需独立。最佳落地路径不是扩大范围，而是以 Researcher B 的架构为主线，吸收 Researcher C 的硬约束，并用 Researcher A 的阶段和交付物定义用户可见流程。
