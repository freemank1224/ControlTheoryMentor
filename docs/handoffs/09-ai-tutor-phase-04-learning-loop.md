# Phase 04 Handoff: 学习闭环与系统硬化

**阶段代号**: P4
**阶段状态**: 🚧 进行中（后端+前端学习闭环已打通，Playwright E2E 与基础观测已补齐，待生产监控接入）
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

## 10. 阶段更新（2026-04-19）

### 10.1 learning state schema 摘要

已新增 `backend/app/schemas/learning.py`，包含：

1. 事件模型：`LearningEventType`、`LearningEventRecord`
2. 掌握度模型：`MasteryLevel`、`ConceptMasteryState`
3. 反馈模型：`FeedbackDifficulty`、`LearningFeedbackEntry`
4. 进度聚合模型：`LearningProgress`
5. API 请求/响应：
1. `LearningTrackRequest` / `LearningTrackResponse`
2. `LearningProgressResponse`
3. `LearningFeedbackRequest` / `LearningFeedbackResponse`

### 10.2 已完成接口

已完成并接入 `backend/app/api/routes/learning.py`：

1. `POST /api/learning/track`
2. `GET /api/learning/progress`
3. `POST /api/learning/feedback`

已在 `backend/app/main.py` 挂载 `learning` router。

### 10.3 learning service 与持久化

已新增 `backend/app/services/learning_service.py`：

1. Redis 主存 + 内存回退（failover）
2. progress 聚合（step、event、mastery、feedback）
3. failback 时自动将 fallback 数据回写主存（避免恢复后状态丢失）

### 10.4 personalization input 回流 tutor

已在 tutor 编排中接入 learning：

1. `TutorAnalyzeRequest` / `TutorSessionStartRequest` 新增可选 `learnerId`
2. `analyze` 阶段读取学习快照并回写到 `suggestedSession.personalization`
3. `start_session` / `next` / `respond` 自动写入 learning 事件：
1. `session_started`
2. `step_started`
3. `step_completed`
4. `step_response`
5. `session_completed`
4. 计划编排会使用 `pendingReviewConceptIds` 调整练习与总结提示语

### 10.5 测试与回归结果

本次新增测试：

1. `backend/tests/unit/test_learning_service.py`
2. `backend/tests/integration/test_learning_api.py`
3. `backend/tests/integration/test_tutor_api.py`（新增 learning personalization 贯通用例）

执行结果（本地 2026-04-19）：

1. `pytest tests/unit/test_learning_service.py tests/integration/test_learning_api.py tests/integration/test_tutor_api.py -q`
2. `16 passed, 1 skipped`

前端新增接线与测试：

1. `frontend/src/types/api.ts`：learning API 类型 + `TutorSessionStart.learnerId`
2. `frontend/src/services/api.ts`：`trackLearningEvent`、`getLearningProgress`、`submitLearningFeedback`
3. `frontend/src/components/tutor/TutorWorkspace.tsx`：
1. learner id 输入
2. progress 面板
3. step content viewed 自动 track
4. step-level feedback 提交
4. `frontend/tests/integration/api.test.ts`：learning API client 覆盖

前端执行结果（本地 2026-04-19）：

1. `npm run test -- tests/integration/api.test.ts --run`
2. `8 passed`

回归与故障文档：

1. `docs/handoffs/09-learning-regression-checklist.md`
2. `docs/handoffs/09-learning-failure-and-rollback.md`

### 10.6 仍待未来阶段处理的问题

1. learning event 目前以规则聚合为主，尚未引入更细粒度 mastery 估计策略。
2. 目前 learnerId 由请求显式传入，尚未接入完整用户身份体系。
3. Playwright 已补齐 tutor-learning 关键路径 E2E，但当前用例仍以前端协议级 mock 为主，尚未纳入稳定的全链路后端数据夹具。
4. learning API 已提供基础运行指标与错误码映射，但尚未接入生产级指标平台/告警系统。

### 10.7 运行指标与错误码映射（新增）

learning API 新增运行观测端点：

- `GET /api/learning/metrics`

用于返回三类端点的基础运行指标：

1. `track`
2. `progress`
3. `feedback`

每个端点返回以下字段（用于运维巡检与初步排障）：

1. `totalRequests`
2. `successRequests`
3. `errorRequests`
4. `avgLatencyMs`
5. `lastLatencyMs`
6. `lastStatusCode`
7. `lastErrorCode`
8. `updatedAt`

并同时返回 `errorCodeMapping`，当前映射约定如下：

1. `LEARNING_INVALID_REQUEST`: 请求参数/结构校验失败（FastAPI validation layer，HTTP 422）
2. `LEARNING_STORE_UNAVAILABLE`: learning 持久化存储暂不可用（HTTP 503）
3. `LEARNING_TRACK_FAILED`: `POST /api/learning/track` 非预期失败（HTTP 500）
4. `LEARNING_PROGRESS_READ_FAILED`: `GET /api/learning/progress` 非预期失败（HTTP 500）
5. `LEARNING_FEEDBACK_FAILED`: `POST /api/learning/feedback` 非预期失败（HTTP 500）

### 10.8 Playwright tutor-learning E2E 场景（新增）

新增用例文件：

1. `frontend/tests/e2e/tutor-learning.spec.ts`

覆盖路径：

1. 启动 tutor 会话
2. 推进 step
3. 提交回答
4. 提交学习反馈
5. 二次会话验证个性化（待复习概念回流）

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