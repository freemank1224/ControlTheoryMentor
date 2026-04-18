# Phase 02 Handoff: 导师编排闭环

**阶段代号**: P2
**阶段状态**: ⏳ 进行中（P2 第一批 tutor orchestration 已落地并通过 tutor 定向测试）
**上游输入**: P1 知识底座输出的 graph lookup contract 与 concept context API
**下游消费者**: P3 内容生成与渲染

## 1. 阶段目标

将现有 tutor 从模板问答与内存态骨架，升级为基于图谱上下文的持久化编排系统。

本阶段完成后，系统必须能够：

1. 分析用户问题并返回相关知识点。
2. 基于知识点生成教学计划。
3. 将 session state 持久化到 Redis。
4. 支持会话推进、回退、跳转和恢复。

## 2. 开工前必读

1. `docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md`
2. `docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md`
3. `docs/handoffs/06-ai-tutor-phase-01-knowledge-foundation.md`
4. `docs/handoffs/07-ai-tutor-phase-02-tutor-orchestration.md`

## 3. 输入握手条件

P2 启动前，必须确认 P1 已交付：

1. 可用的节点搜索接口
2. 可用的 concept context 接口
3. tutor 可依赖的 graph lookup contract
4. 至少一套 graph/node/context 测试基线

若以上条件缺失，P2 不能假设图谱能力存在，应先回退到 P1 文档修复。

## 4. 本阶段范围

### 范围内

1. `POST /api/tutor/analyze`
2. `GET /api/tutor/sessions`
3. session persistence to Redis
4. `current / next / respond / back / jump` 完整状态机
5. `Tutor Orchestrator` 统一处理分析、计划、推进逻辑
6. graph highlight metadata
7. 将 P1 `passages` 接入 tutor analyze 与 plan generation，形成图谱 + 原文证据联合上下文
8. 对 chunk 级 `passages` 做句段级裁剪与排序，输出更适合 tutor 编排的 evidence payload

### 范围外

1. 独立 content artifact 生成
2. frontend ContentRenderer
3. 学习进度建模

## 5. 交付清单

### API 交付

- `POST /api/tutor/analyze`
- `GET /api/tutor/sessions`
- `GET /api/tutor/session/{id}`
- `POST /api/tutor/session/start`
- `POST /api/tutor/session/{id}/next`
- `POST /api/tutor/session/{id}/respond`
- `POST /api/tutor/session/{id}/back`
- `POST /api/tutor/session/{id}/jump`

### 服务交付

- `tutor_service.py` 或 `tutor_orchestrator.py`
- `session_service.py`
- Redis-backed session repository

### 测试交付

- tutor analyze 测试
- session persistence 测试
- step transition 测试
- restart/recovery 行为验证

## 6. 工作包分解

1. 将现有 tutor route 中的编排逻辑下沉到 service 层。
2. 设计 Redis session schema。
3. 将 session 响应模型与前端契约稳定下来。
4. 基于 graph context + source passages 实现 `tutor/analyze`。
5. 对 source passages 做句段级裁剪、去噪和排序，形成 tutor 可消费的 evidence payload。
6. 扩展 session API，并补齐测试。
7. 为 P3 输出 content request contract。

## 7. 完成标准

必须全部满足：

1. session state 不再仅存于进程内存。
2. `tutor/analyze` 返回的知识点来自图谱能力，而不是纯模板关键字判断。
3. `tutor/analyze` 和 plan generation 已接入图谱对应的原文证据片段，而不是只使用概念名。
4. session step 输出中包含下一阶段可消费的 content generation input。
5. 会话可以列出、读取、推进、回退和跳转。

## 8. 交给下一阶段的握手输出

P3 开始前必须能从本阶段拿到：

1. 稳定的 session response schema
2. current step 的 content request shape
3. graph highlight metadata shape
4. tutor 页面需要消费的 API 列表

## 9. 已知风险

1. 如果 graph context 过稀，analyze 结果可能不稳定，必须保留降级策略并写入文档。
2. Redis 中 session schema 一旦确定，后续阶段不要随意破坏兼容性。
3. 如果 step transition 依赖 LLM，应加输出 schema 校验和 fallback。

## 10. 阶段结束时必须更新的内容

完成阶段时，请在本文件补充：

- `阶段状态`
- `Redis session schema 摘要`
- `已完成接口`
- `测试结果`
- `遗留问题`
- `交给 P3 的 content request 契约`

## 10A. 当前进度快照

### Redis session schema 摘要

- session 顶层字段：`id`、`question`、`pdfId`、`mode`、`context`、`analysis`、`topics`、`plan`、`messages`、`currentStepIndex`、`status`、`awaitingResponse`、`createdAt`、`updatedAt`
- 默认通过 `SessionService` 访问；运行时优先 Redis，`ping` 失败时回退 `memory-fallback`
- Redis 写入形态：`tutor:session:{session_id}` 存 session payload，`tutor:sessions` 用 `updatedAt` 时间戳做排序索引

### 已完成接口

- `POST /api/tutor/analyze`
- `GET /api/tutor/sessions`
- `GET /api/tutor/session/{id}`
- `POST /api/tutor/session/start`
- `POST /api/tutor/session/{id}/next`
- `POST /api/tutor/session/{id}/respond`
- `POST /api/tutor/session/{id}/back`
- `POST /api/tutor/session/{id}/jump`

### 当前实现说明

- tutor route 已改成薄路由，编排逻辑下沉到 `backend/app/services/tutor_service.py`
- `tutor/analyze` 已接入 graph semantic search + concept context，并把 `passages` 压成句段级 `evidencePassages`
- plan generation 已把 `graphHighlights`、`evidencePassages`、`contentRequest` 放进每个 step 的 `content`
- session list / get / next / respond / back / jump 已统一走 `SessionService`

### 测试结果

- `cd backend; ../.venv/Scripts/python.exe -m pytest tests/integration/test_tutor_api.py tests/unit/test_tutor_schema.py -q`
- 结果：`27 passed, 21 warnings`
- 当前 warnings 为既有 Pydantic v2 class-based config deprecation，未在本批次处理

### 遗留问题

- 目前只验证了 tutor 定向 API 与 schema；尚未补 session restart/recovery 的更完整集成验证
- Redis fallback 已实现，但还没有针对真实 Redis online 场景补专门测试
- `chat / quiz / solve` 仍然是轻量模板实现，不属于本批次的 graph-grounded orchestration 深化范围
- P2 全阶段仍未完成，后续还需要继续收敛 recovery 行为与面向 P3 的消费契约稳定性

### 交给 P3 的 content request 契约

- 位置：每个 `TeachingStep.content.contentRequest`
- 当前字段：`stage`、`primaryConceptId`、`conceptIds`、`highlightedNodeIds`、`evidencePassageIds`、`renderHint`、`learnerLevel`
- 当前用途：为 P3 内容生成器提供 step 级内容请求骨架，使其可基于图谱节点高亮与证据片段生成更具体的教学内容

## 11. 下一 session 启动提示词

```text
请读取以下文档后继续 P2 阶段开发：
1. docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md
2. docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md
3. docs/handoffs/06-ai-tutor-phase-01-knowledge-foundation.md
4. docs/handoffs/07-ai-tutor-phase-02-tutor-orchestration.md

目标：完成导师编排闭环，只做 tutor analyze、session persistence、step orchestration 和 graph highlight metadata，不进入 content artifact 与 learning 模块。
结束前必须更新 handoff 文档中的状态、测试结果、遗留问题和交接输出。
```