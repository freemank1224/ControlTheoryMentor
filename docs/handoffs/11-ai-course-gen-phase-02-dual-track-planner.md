# Phase 02 Handoff: 双轨课程规划引擎

- 阶段代号: P2
- 阶段状态: 已完成（可进入 Phase 3）
- 上游输入: Phase 1 课程类型判定与契约扩展
- 下游消费者: Phase 3 多模态与参数交互
- 当前 Session ID: db047c89-78c7-4a88-a8de-3c7660fcd29a
- 文档版本: v1.0
- 更新时间: 2026-04-19

## 1. 阶段目标

实现课程规划双轨引擎，在 tutor 会话启动时按 courseType 生成稳定的四步计划，并固化 modalityPlan/checkpointSpec/planFinalized 契约，同时保证会话状态机流转不触发重规划，兼容历史旧会话读取。

## 2. 范围内 / 范围外

### 范围内

1. 拆分 knowledge_learning / problem_solving 两套 builder。
2. 四步计划结构统一，按轨道输出不同步骤语义与 modality。
3. 每步附带 modalityPlan。
4. 关键交互步附带 checkpointSpec。
5. 会话计划新增 planFinalized 并在 metadata 回传。
6. 旧会话缺省 courseType 与新字段自动回填。
7. next/back/jump/respond 回归验证不触发重规划。

### 范围外

1. Phase 3 多模态内容生成质量优化（image/comic/animation）。
2. checkpoint 自动评分引擎（当前仅给出结构契约）。
3. 学习事件新增维度的聚合策略扩展。

## 3. 交付清单

### Schema

- backend/app/schemas/tutor.py
  - 新增 ModalityPlan
  - 新增 CheckpointSpec
  - TeachingStep 新增 modalityPlan/checkpointSpec
  - TeachingPlan 新增 planFinalized

### Service

- backend/app/services/tutor_service.py
  - _build_teaching_plan 改为 courseType 分流
  - 新增 _build_knowledge_learning_plan
  - 新增 _build_problem_solving_plan
  - contentRequest targetContentTypes/renderHint 跟随 modalityPlan
  - _require_session 增加旧会话回填入口
  - 新增 _backfill_legacy_session 与 legacy modality/checkpoint 补齐逻辑
  - session metadata 回传 planFinalized

### Tests

- backend/tests/unit/test_tutor_schema.py
  - 新字段 schema 校验
- backend/tests/unit/test_tutor_service_phase2_planner.py
  - 双 builder golden snapshot
  - 旧会话回填验证
- backend/tests/integration/test_tutor_api.py
  - 启动返回新契约字段
  - problem_solving builder 路径
  - next/back/jump/respond 计划不重建断言

### Frontend Typing

- frontend/src/types/api.ts
  - 新增 ModalityPlan / CheckpointSpec
  - TeachingStep/TeachingPlan 增加 Phase 2 字段类型

## 4. 结构约束（Phase 2 必填）

### knowledge_learning builder

1. step-1 intro: 概念背景与证据定位
2. step-2 concept: 核心概念拆解（checkpoint）
3. step-3 practice/checkpoint: 迁移应用（checkpoint）
4. step-4 summary: 总结与下一步

### problem_solving builder

1. step-1 intro: 题目建模与目标定义
2. step-2 checkpoint: 变量盘点与约束检查
3. step-3 practice: 分步推导与结果验证
4. step-4 summary: 解题模板复盘与迁移

### 统一契约

1. plan.planFinalized = true
2. 每步存在 modalityPlan
3. 关键交互步存在 checkpointSpec
4. state transition 不改写 plan 内容

## 5. 旧会话兼容策略

1. 缺省 courseType: 自动 classify + resolve 并回填。
2. 缺省 autoCourseTypeDecision/courseTypeDecision: 自动生成兜底决策。
3. 缺省 planFinalized: 默认回填 true。
4. 缺省 step.modalityPlan: 按 stepType + requiresResponse 生成 legacy modality。
5. 缺省 step.checkpointSpec 且交互关键步: 生成 legacy_checkpoint。

## 6. 测试结果（Phase 2 门禁）

命令：

- c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/unit/test_tutor_schema.py tests/unit/test_tutor_service_phase2_planner.py tests/integration/test_tutor_api.py -vv

结果：

- 46 passed, 1 skipped
- skip 原因：本机 Redis 不可达导致 real-redis recovery 用例跳过（属于允许范围）

门禁结论：

1. 双 builder 结构稳定：通过
2. golden plan 快照通过：通过
3. next/back/jump/respond 不重规划：通过
4. 旧会话回填：通过

## 7. 风险与观察

1. checkpointSpec 当前是结构契约，尚无统一评分器；Phase 3 可接学习事件评分闭环。
2. problem_solving 轨道对 latex/interactive 的内容质量仍依赖 Phase 3 内容生成侧。
3. 前端当前主要消费 markdown，新的 modality 字段已完成类型对齐但渲染策略待 Phase 3 扩展。

## 8. 三件套门禁状态

1. handoff 文档: 本文件已更新
2. regression checklist: docs/handoffs/13-course-gen-regression-checklist.md 已更新
3. rollback 文档: docs/handoffs/13-course-gen-failure-and-rollback.md 已更新

结论：允许进入 Phase 3。

## 9. Phase 3 启动词

请先读取并确认以下三件套文档（Phase 2, 2026-04-19, Session db047c89-78c7-4a88-a8de-3c7660fcd29a）：
1) docs/handoffs/11-ai-course-gen-phase-02-dual-track-planner.md
2) docs/handoffs/13-course-gen-regression-checklist.md
3) docs/handoffs/13-course-gen-failure-and-rollback.md

然后启动 Phase 3：多模态与参数交互增强。
目标：基于 Phase 2 的 modalityPlan/checkpointSpec，打通 image/comic/animation 与参数控制（style/detail/pace/attempt），并将 checkpoint 与 learning 事件汇合到可观测链路。
门禁：多模态载荷协议回归通过、参数交互端到端通过、生图降级链路可用、学习事件聚合回归通过，并更新 Phase 3 handoff。
