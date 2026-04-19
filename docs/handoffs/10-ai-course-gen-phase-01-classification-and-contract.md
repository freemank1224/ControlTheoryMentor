# Phase 01 Handoff: 课程类型判定与契约扩展

- 阶段代号: P1
- 阶段状态: ✅ 已完成（可进入 Phase 2）
- 上游输入: Phase 0 / 现有 P2 tutor analyze + session start 基线
- 下游消费者: Phase 2 双轨课程规划引擎
- 当前 Session ID: db047c89-78c7-4a88-a8de-3c7660fcd29a
- 文档版本: v1.0
- 更新时间: 2026-04-19

## 1. 阶段目标

完成课程类型自动判定与契约扩展，在不破坏旧客户端请求的前提下，支持 analyze/start 的 auto/manual/override 三路径。

## 2. 范围内 / 范围外

### 范围内

1. 新增 `CourseType` 与 `CourseTypeDecision` 模型。
2. 扩展 tutor analyze/start 请求契约，支持 `courseTypeStrategy` + `courseTypeOverride`。
3. 实现 `classify_course_type(question, context)` 规则判定器。
4. analyze/start 响应 metadata 输出 `finalCourseType` 与 `autoDecision`。
5. 前端 TutorWorkspace 增加课程类型策略入口（auto/manual/override）。
6. 旧请求兼容（不带新字段、仅 legacy `courseType` 字段）。

### 范围外

1. 双轨课程计划结构重构（knowledge/problem 两套 builder）。
2. modalityPlan/checkpointSpec 大规模契约扩展。
3. 多模态内容渲染与学习事件新增类型。

## 3. 交付清单

### API / Schema

- `backend/app/schemas/tutor.py`
  - 新增 `CourseType`: `knowledge_learning | problem_solving`
  - 新增 `CourseTypeStrategy`: `auto | manual | override`
  - 新增 `CourseTypeDecision`: `decision/confidence/signals/overridden`
  - 扩展 `TutorAnalyzeRequest` / `TutorSessionStartRequest`
  - 增加 legacy 字段 `courseType` 映射到 `courseTypeOverride`
  - 扩展 `TutorAnalyzeResponse.metadata`

### Service

- `backend/app/services/course_type_classifier.py`
  - `classify_course_type(question, context)`
  - `resolve_course_type(strategy, auto_decision, course_type_override)`
- `backend/app/services/tutor_service.py`
  - `TutorService.classify_course_type(...)`
  - analyze/start 接入课程类型决策与 metadata 回传
  - 会话响应 metadata 注入：
    - `finalCourseType`
    - `autoDecision`
    - `courseTypeDecision`
    - `courseTypeStrategy`
    - `courseTypeOverride`

### Frontend

- `frontend/src/types/api.ts`
  - 新增 CourseType 相关类型、analyze 请求响应类型
- `frontend/src/services/api.ts`
  - 新增 `analyzeTutorQuestion(...)`
- `frontend/src/components/tutor/TutorWorkspace.tsx`
  - 新增课程类型策略选择入口
  - 新增 analyze 预判入口
  - start 请求携带策略/override 字段
- `frontend/src/components/tutor/TutorWorkspace.css`
  - start 表单布局适配新增字段

### Tests

- `backend/tests/unit/test_course_type_classifier.py`
- `backend/tests/unit/test_tutor_schema.py`
- `backend/tests/integration/test_tutor_api.py`
- `frontend/tests/integration/api.test.ts`

## 4. 字段表（Phase 1 必填）

### CourseType

- `knowledge_learning`: 概念理解、解释型课程
- `problem_solving`: 计算/推导/求解型课程

### CourseTypeDecision

- `decision`: 最终或自动判定的课程类型
- `confidence`: 0-1 置信度
- `signals`: 触发信号（关键词、上下文提示、策略标签等）
- `overridden`: 是否被手工覆盖

## 5. auto/manual/override 决策优先级（Phase 1 必填）

1. 先计算 `autoDecision = classify_course_type(question, context)`。
2. `manual`:
   - 有 `courseTypeOverride` -> 强制采用 override（`overridden` 由是否与 auto 不同决定）
   - 无 `courseTypeOverride` -> 回退 auto
3. `override`:
   - 有 `courseTypeOverride` -> 采用 override（保留 autoDecision 供观测）
   - 无 `courseTypeOverride` -> 回退 auto
4. `auto`:
   - 默认采用 auto
   - 若存在 legacy/补充 override 值，走兼容覆盖路径

## 6. 旧请求兼容说明（Phase 1 必填）

1. 不带 `courseTypeStrategy/courseTypeOverride` 的旧请求仍可正常调用 analyze/start。
2. legacy `courseType` 字段自动映射到 `courseTypeOverride`。
3. 老会话缺失课程类型字段时，session response metadata 兜底回填默认结构，避免读取失败。

## 7. 测试结果（Phase 1 必填）

### 分类器分支覆盖

命令：

- `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m coverage run --branch -m pytest tests/unit/test_course_type_classifier.py -q`
- `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m coverage report --include="app/services/course_type_classifier.py" -m`

结果：

- `Branch Cover = 100%`（满足 >=90% 门禁）

### analyze/start 三路径 + 兼容测试

命令：

- `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/unit/test_course_type_classifier.py tests/unit/test_tutor_schema.py tests/integration/test_tutor_api.py -q`
- `npm run test -- tests/integration/api.test.ts --run`（frontend）

结果：

- backend: `57 passed, 1 skipped`
- frontend: `1 file passed, 9 tests passed`
- 覆盖 auto/manual/override 三路径 + legacy 兼容

## 8. 遗留风险

1. 当前分类器为规则引擎，语义歧义样本仍可能误分；Phase 2 可补 LLM classifier 插槽。
2. `courseType` legacy 字段仍保留，需在后续阶段明确废弃窗口。
3. 现阶段仅完成分类与契约扩展，课程计划仍是单 builder，尚未按课程类型分轨生成。

## 9. 握手输出（Phase 1 必填）

### finalCourseType 结构

- 位置：
  - `POST /api/tutor/analyze` -> `response.metadata.finalCourseType`
  - `POST /api/tutor/session/start` -> `response.metadata.finalCourseType`
- 类型：`knowledge_learning | problem_solving`

### autoDecision 示例

```json
{
  "decision": "knowledge_learning",
  "confidence": 0.76,
  "signals": ["keyword_knowledge:2", "keyword_problem:0"],
  "overridden": false
}
```

### 前端 override 协议

- 请求字段：
  - `courseTypeStrategy`: `auto | manual | override`
  - `courseTypeOverride`: `knowledge_learning | problem_solving`（manual/override 时可传）
- 兼容字段：
  - `courseType`（legacy，自动映射为 override）

## 10. 三件套门禁状态

1. handoff 文档: ✅ 本文件已更新
2. regression checklist: ✅ `docs/handoffs/13-course-gen-regression-checklist.md` 已更新
3. rollback 文档: ✅ `docs/handoffs/13-course-gen-failure-and-rollback.md` 已更新

结论：✅ 允许进入 Phase 2。

## 11. Phase 2 启动词

```text
请先读取并确认以下三件套文档（Phase 1, 2026-04-19, Session db047c89-78c7-4a88-a8de-3c7660fcd29a）：
1) docs/handoffs/10-ai-course-gen-phase-01-classification-and-contract.md
2) docs/handoffs/13-course-gen-regression-checklist.md
3) docs/handoffs/13-course-gen-failure-and-rollback.md

然后启动 Phase 2：双轨课程规划引擎重构。
目标：拆分 knowledge_learning / problem_solving 两套 builder，固化 4 步流程并输出 modalityPlan + checkpointSpec；保证 next/back/jump/respond 不触发重规划；兼容旧会话缺省 courseType 自动回填。
门禁：双 builder 单测通过、golden-plan 快照稳定、状态机不重规划回归通过，并更新 Phase 2 handoff。
```