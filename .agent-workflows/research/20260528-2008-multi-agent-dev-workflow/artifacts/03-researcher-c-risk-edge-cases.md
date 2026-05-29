Status: success

# Researcher C - Risks and Edge Cases

- Role ID: `researcher-c`
- Phase: `research`
- Status: `success`
- Requirement: `../requirement.md`
- Prompt: `../prompts/researcher-c.md`
- Produced: `2026-05-28T20:11:35+08:00`

## Output

### 独立调研结论

多 agent 开发 workflow 最大风险不在“能否自动完成任务”，而在于：agent 被提示注入劫持后仍持有真实工具权限、skill/subagent 供应链被污染、并发写入造成数据/代码丢失、UI 图像生成引入版权/隐私风险，以及自测/验收由同一类模型闭环导致误报。推荐采用“artifact-first + least privilege + checkpoint + gated automation”的工作流：所有阶段产物落盘、所有工具调用可审计、所有高影响动作需审批、所有自动测试必须由非生成方验证。

### 关键发现

1. **agent 失控/越权是最高优先级风险。** OWASP LLM Top 10 明确列出 Prompt Injection、Sensitive Information Disclosure、Supply Chain、Improper Output Handling、Excessive Agency 等风险；OWASP MCP Top 10 进一步指出 Token Mismanagement、Privilege Escalation via Scope Creep、Tool Poisoning、Command Injection、Lack of Audit and Telemetry、Context Over-Sharing 都会在 MCP/agent 工具层放大。来源：[OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)、[OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/)

2. **Prompt injection 不能只靠 prompt 约束解决。** 间接注入可能来自网页、issue、PR、PDF、Figma/设计稿 OCR 文本、截图、代码注释、依赖 README、测试失败日志。缓解方向：模型输出视为不可信建议；工具层做 allowlist、参数 schema 校验、路径边界、命令拦截、审批；不要允许 LLM 直接拼 shell/API 请求。来源：[OpenAI Agents SDK Guardrails](https://openai.github.io/openai-agents-js/guides/guardrails/)

3. **skill/subagent 插件化会引入供应链与权限漂移。** 每个 skill/subagent 本质上是可执行策略、提示词、脚本、工具权限和依赖的组合。推荐要求 manifest：`name`、`version`、`source`、`commit/hash`、`permissions`、`network`、`filesystem`、`secrets`、`side_effects`、`owner`、`review_status`。开源 skill 进入系统前做 OpenSSF Scorecard、license、SBOM、固定版本/commit、SLSA provenance 检查。来源：[OpenSSF Scorecard](https://github.com/ossf/scorecard)、[SLSA spec v1.2](https://slsa.dev/spec/latest/)

4. **隐私和日志风险会被 tracing/checkpoint 放大。** API/agent tracing、tool calls、handoffs、guardrails、abuse monitoring logs 都可能包含敏感信息。workflow audit log 应记录决策、工具名、参数摘要、artifact hash、审批人、时间戳、结果码；默认不记录 secrets、完整源码、客户数据、图片原图、完整 prompt。来源：[OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)、[OpenAI Agents SDK Tracing](https://openai.github.io/openai-agents-python/tracing/)

5. **gpt-image-2/UI 设计稿生成存在版权、隐私、模型兼容风险。** `gpt-image-2` 支持 text/image 输入与 image 输出，适合图像生成和编辑，但不应当承担结构化 UI spec 的职责。UI 设计稿不能上传客户隐私、真实用户头像、未授权商标/竞品页面、商业机密截图。来源：[OpenAI gpt-image-2 model](https://developers.openai.com/api/docs/models/gpt-image-2)、[U.S. Copyright Office AI Copyrightability Report](https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-2-Copyrightability-Report.pdf)

6. **并发 agent 容易造成冲突、重复执行和回滚困难。** 多 agent 同时写需求、设计、代码、测试时，风险包括覆盖同一文件、基于过期上下文修改、重复调用付费模型、重复创建 issue/PR。推荐图式编排和 checkpoint。来源：[LangGraph Persistence](https://langchain-5e9cc07a.mintlify.app/oss/python/langgraph/persistence)、[LangGraph Time Travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)

7. **CI/CD 与自动化凭证是常见失控出口。** GitHub Actions 应默认 `GITHUB_TOKEN` 最小权限，使用 OIDC 替代长期云密钥，PR from fork 不暴露 secrets，禁止 agent 自动修改 release/deploy workflow 后立即执行。来源：[GitHub Actions Security Reference](https://docs.github.com/en/actions/reference/security)

8. **自测误报与验收漂移不可忽视。** agent 可能生成“看起来通过”的测试、跳过 flaky 失败、降低断言、只测 happy path。UI 从设计稿复刻时需要结构/交互测试、视觉回归测试、人工验收；业务逻辑需覆盖权限、异常、并发、幂等、回滚、数据迁移失败路径。

### 最高风险部分

高权限工具调用、不可信上下文进入 agent 指令流、skill/subagent 动态接入、生成 UI 设计稿、并发写入与自动回滚缺失、验收闭环由同一模型完成。

### 推荐工作流：风险控制版

Intake / Scope Gate -> 独立需求调研 -> Review / Decision Gate -> 需求/设计/技术文档落地 -> UI 设计稿生成 Gate -> 设计稿复刻 UI -> 业务逻辑开发 -> 功能自测与验收 -> Release / Rollback Gate。

### 建议 artifact 结构

`.agent-workflows/<run-id>/` 下保存 `requirement.md`、`risk-profile.md`、`permissions.yaml`、`sources.md`、`prompts/`、`artifacts/`、`logs/tool-calls.jsonl`、`logs/approvals.jsonl`、`logs/audit-events.jsonl`、`checkpoints/`、`manifests/skills.lock`、`subagents.lock`、`model-versions.lock`。

### Tool / skill 接入方式

每个 skill/subagent 必须注册 `name`、`version`、`source`、`pinned_ref`、`owner`、`trust_level`、`permissions`、`side_effects`、`inputs`、`outputs`、`approval_required_for`。

### 自动化与人工介入边界

需求调研、文档草稿、脱敏 UI 生成候选、sandbox UI 复刻、单元/集成/e2e/视觉回归可自动化；范围变更、合规/隐私判断、需求冻结、设计稿选择、架构取舍、上传真实用户/客户素材、权限/支付/迁移/生产数据/外部写 API、baseline 更新、上线验收、生产发布必须人工介入。

### 推荐缓解措施

默认 deny、最小权限、一次性审批、短期 token、不可信上下文隔离、工具参数 schema 校验、禁止模型直接构造 shell、skills.lock 固定版本、SBOM/OpenSSF/SLSA、单 writer 原则、文件级 lock、独立分支/worktree、checkpoint + artifact hash + Git commit、日志脱敏、测试不可由开发 agent 自行删除/降级、模型 snapshot 记录、预算暂停、上传前脱敏、AI-assisted provenance、MCP server 默认 stdio/loopback、HTTP transport 需 auth。

### 决策阻塞点

是否允许 agent 访问真实私有 repo、客户数据、设计素材和生产凭证；是否需要 ZDR/MAM/DPA；主 orchestrator 选择；`gpt-image-2` 在目标账号/区域/端点的可用性、价格、速率限制、retention；UI 版权策略；发布边界。

### Confidence

medium-high。安全、供应链、隐私、审计、checkpoint、人类审批等建议有官方或行业来源支撑；具体模型可用性、价格、组织合规要求、现有 agent 平台能力需要在实施前按目标环境重新验证。
