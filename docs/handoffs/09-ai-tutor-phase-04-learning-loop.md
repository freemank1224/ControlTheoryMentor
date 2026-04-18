# Phase 04 Handoff: 学习闭环与系统硬化

**阶段代号**: P4
**阶段状态**: ⏳ 待完成
**上游输入**: P3 输出的 content artifact、tutor page、session 流程
**下游消费者**: 系统收尾、长期迭代

## 1. 阶段目标

把 AI 导师系统从“能完成单次教学”升级为“能持续学习与稳定回归的系统”。

本阶段完成后，系统必须能够：

1. 记录学习交互与进度。
2. 表示已掌握、待复习、当前步骤等学习状态。
3. 将学习记录回流到 tutor 分析与计划中。
4. 具备覆盖核心闭环的测试与回归文档。

## 2. 开工前必读

1. `docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md`
2. `docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md`
3. `docs/handoffs/08-ai-tutor-phase-03-content-generation.md`
4. 当前 tutor page 与 content artifact 契约文档

## 3. 输入握手条件

P4 启动前，必须确认 P3 已交付：

1. 稳定的 content artifact schema
2. tutor 页面可用
3. session 与 content 的关联关系清晰
4. step completion 可以从前端或后端确定

## 4. 本阶段范围

### 范围内

1. `Learning API`
2. `Learning Tracking Service`
3. progress model
4. feedback model
5. personalization input 回流 tutor analyze / planning
6. 集成测试、E2E、回归清单、观测补强

### 范围外

1. 全量用户体系与权限体系
2. 复杂推荐系统
3. 生产级监控平台完整接入

## 5. 交付清单

### API 交付

- `POST /api/learning/track`
- `GET /api/learning/progress`
- `POST /api/learning/feedback`

### 服务交付

- `learning_service.py`
- learning state persistence
- tutor personalized input bridge

### 测试与回归交付

- learning API 测试
- tutor session + content + learning 贯通测试
- 回归清单文档
- 已知故障与回退策略文档

## 6. 工作包分解

1. 定义 progress / feedback / mastery 数据模型。
2. 记录用户在 step 和 content 层面的行为。
3. 在 tutor analyze / plan 中读取 learning state。
4. 完成 E2E 用例和回归检查表。
5. 补充错误码、日志点与运维说明。

## 7. 完成标准

必须全部满足：

1. 用户再次进入系统时可以看到自己的当前进度。
2. tutor 新会话会读取已有学习状态并影响计划。
3. 系统具备覆盖图谱、tutor、content、learning 四条链路的回归验证。
4. handoff 文档和回归清单足以支撑后续新 session 接力。

## 8. 交付后的系统完成定义

当 P4 完成时，AI 导师系统至少达到以下标准：

1. 有真实图谱底座。
2. 有持久化导师会话。
3. 有内容生成与多模态渲染。
4. 有学习进度与反馈闭环。

## 9. 已知风险

1. 如果 learning state 设计过重，会拖慢 P4；优先做最小可用模型。
2. personalization 先做规则型回流即可，不必一开始就做复杂推荐。
3. 必须区分“学习记录已完成”和“推荐系统已完成”。

## 10. 阶段结束时必须更新的内容

完成阶段时，请在本文件补充：

- `阶段状态`
- `learning state schema 摘要`
- `已完成接口`
- `测试与回归结果`
- `仍待未来阶段处理的问题`

## 11. 下一 session 启动提示词

```text
请读取以下文档后继续 P4 阶段开发：
1. docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md
2. docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md
3. docs/handoffs/08-ai-tutor-phase-03-content-generation.md
4. docs/handoffs/09-ai-tutor-phase-04-learning-loop.md

目标：完成学习闭环与系统硬化，只做 learning API、progress model、feedback model、personalization input 和测试/回归补强。
结束前必须更新 handoff 文档中的状态、测试结果、遗留问题和交接输出。
```