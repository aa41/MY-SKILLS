Status: success

# Final Synthesizer - Decision and Plan

- Role ID: `synthesizer`
- Phase: `synthesis`
- Status: `success`
- Requirement: `../requirement.md`
- Prompt: `../prompts/synthesizer.md`
- Produced: `2026-05-28T20:32:00+08:00`

## Output

## Decision

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

## Why

证据审计认为三个独立 researcher 在原则层高度一致：artifact-first、显式阶段、专业 subagent/skill、最小权限、关键节点 human gate、可恢复/可审计状态机。决策审计认为最可落地的是 Researcher B 的架构主线，但必须吸收 Researcher C 的安全边界，并用 Researcher A 的产品阶段与用户可见 artifact 补齐工作流体验。

关键取舍：

- **不把 LangGraph 写死为最终编排层。** 它是强候选，但证据只足以支持 prototype 评估，不足以证明它优于轻量 runner、OpenAI Agents SDK orchestration 或 Temporal-first。
- **不把 gpt-image-2 生成图当 UI 规格。** 图片模型只用于候选视觉方向；最终实现依据必须是 UX spec、design tokens、组件映射、Figma/结构化设计上下文或人工确认。
- **不允许同一 agent 闭环自证完成。** 开发、测试、验收必须分离；测试失败、断言降低、baseline 更新需要独立审查或人工批准。
- **先小闭环，后平台化。** 第一版聚焦 research -> docs -> decision gate，避免一开始进入多租户平台、可视化 DAG、skill 市场、自动生产发布等高成本范围。

## Rejected Options

- **单一 mega-agent 从需求直接到生产发布**：不可审计、难恢复、权限边界模糊、失败难定位，也不支持多个独立 skill/subagent 的可控叠加。
- **只靠 CrewAI/AutoGen 式对话协作**：可用于局部研究/评审，但不足以承载工程阶段状态、checkpoint、审批、恢复和 artifact traceability。
- **一开始直接上 Temporal 全平台**：durable execution 很强，但当前阶段应先验证 workflow contract、artifact schema、审批边界和本地执行闭环。
- **只用图片模型生成 UI 后按图写代码**：bitmap 缺少组件层级、tokens、交互状态、响应式规则和业务异常状态，必须转为结构化规格。
- **无约束动态加载 skill/MCP**：供应链、权限漂移、prompt injection 和 tool poisoning 风险过高，必须 manifest、pin、lock、sandbox、approval、audit 一起做。

## Implementation Plan

### Phase 0: Workflow Spec

产出：

- `.agent-workflows/dev/<run-id>/workflow.yaml`
- `state.schema.json`
- `event.schema.json`
- `artifact-contract.md`
- `approval-policy.md`
- `skill-manifest.schema.json`
- `permissions.yaml`

目标：先锁定阶段、状态、artifact、审批、权限、事件和失败恢复语义。目录结构是 proposal，可调整；建议保留 `.agent-workflows/research/<run-id>/` 给调研，`.agent-workflows/dev/<run-id>/` 给开发工作流。

### Phase 1: Local Runner MVP

实现命令：

```bash
workflow run --requirement requirement.md --mode auto-until-approval
workflow status --run-id <id>
workflow resume --run-id <id> --approval <approval-id> --decision approve
```

最低能力：

- 创建 run directory。
- 写入 `requirement.md`、`index.md`、`state.json`、`events.jsonl`。
- 支持 `pending/running/waiting_for_approval/success/failed/partial/cancelled`。
- 支持失败恢复、重复执行幂等、approval artifact。
- 不做真实业务代码自动修改、不做外部系统写入、不做 Temporal。

### Phase 2: Research / Docs Workflow

跑通低风险完整闭环：

1. intake normalizer 生成 `requirement.md`。
2. 3 researcher 并行输出 raw artifacts。
3. 2 reviewer 做 evidence audit 和 decision audit。
4. synthesizer 生成 `prd.md`、`design-brief.md`、`technical-design.md`、`task-plan.md`。
5. human gate 冻结需求和技术方案。

### Phase 3: Skill / Subagent Registry

实现：

- 扫描本地 skills/subagents。
- 生成 `skills.lock`、`subagents.lock`、`model-versions.lock`。
- 校验 manifest、权限、side effects、输入输出路径。
- MCP server allowlist。
- tool call 参数 schema 校验、日志脱敏、approval gate。

### Phase 4: UI Generation / Replication Loop

流程：

1. 从 `prd.md` 和 `design-brief.md` 生成 `image-prompts.md`。
2. 使用 gpt-image-2 或替代图像模型生成 2-4 个候选 UI mockup。
3. 保存 prompt、model、snapshot/version、参数、输入 artifact hash、输出图片。
4. 人工选择或要求 revision。
5. 生成 `ux-spec.md`、`design-tokens.md`、组件映射。
6. UI replicator 按现有组件库/tokens/routing/state 实现。
7. Playwright 多 viewport 截图、visual diff、a11y 验证。
8. baseline 更新必须人工审批。

### Phase 5: Business Logic / QA / Acceptance

实现：

- task-plan 驱动代码变更。
- 单 writer 原则或文件级 lock。
- unit/integration/contract/e2e/visual/a11y 测试。
- reviewer/security/QA agent 独立审查。
- `acceptance.md` 建立需求项到代码、测试、截图、日志、人工验收的映射。

### Phase 6: Production Hardening

仅在前面验证通过后考虑：

- Temporal durable execution。
- GitHub/Linear/Jira 深度同步。
- 企业权限、审计、密钥治理。
- 多租户 Web UI。
- 组织级 skill registry 或 marketplace。

## Risks

必须在实施前验证：

- 目标 repo 的语言、框架、测试体系、CI/CD、design system、权限模型、issue/PR 流程。
- 当前 Codex Skills/Subagents 的实际目录、sandbox、approval、并行和 artifact 写入能力。
- gpt-image-2 或替代图像模型的当前官方 API、可用性、价格、速率限制、数据保留和组织权限。
- Figma MCP / Dev Mode 的账号权限、plan、文件访问、variables/tokens/code connect 支持。
- MCP server transport、auth、tool confirmation、权限隔离和审计行为。
- LangGraph 的版本、API 稳定性、checkpoint backend、interrupt/resume 行为和 license。
- 组织对私有 repo、客户数据、设计素材、商标、日志保留、模型供应商的合规要求。
- 视觉差异阈值、viewport、a11y baseline、人工验收签名格式和 traceability matrix 字段。

默认风险控制：

- prompt injection 与不可信上下文隔离。
- least privilege 和 default deny。
- secrets、客户数据、完整源码、完整 prompt、原始图片默认不进 tracing/log。
- skill/subagent/MCP 版本 pin、lock、SBOM/license/provenance。
- CI/CD 凭证最小权限，禁止自动生产发布。
- 测试和验收独立于开发 agent。

## Confidence

Confidence: **medium-high**

原则层面证据强，三组 researcher 与两组 reviewer 结论一致；具体框架、API、目录、schema 和目标环境能力仍需通过 prototype 与官方最新文档验证。
