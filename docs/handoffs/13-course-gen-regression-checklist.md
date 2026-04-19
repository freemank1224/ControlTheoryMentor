# Course Generation Regression Checklist

- 文档版本: v1.1
- 更新时间: 2026-04-19

## 使用说明

每个阶段完成时更新本清单。未勾选项视为阻塞发布/阻塞进入下一阶段。

## Phase 1: 分类与契约扩展（已完成）

- [x] CourseType 与 CourseTypeDecision schema 已落地。
- [x] analyze/start 支持 `auto/manual/override` 三路径。
- [x] 旧请求兼容：缺省新字段可调用；legacy `courseType` 可映射。
- [x] 分类器分支覆盖 >= 90%。
- [x] analyze/start 三路径集成测试通过。
- [x] 前端入口覆盖策略选择 + override。

### Phase 1 回归证据

- backend unit+integration:
  - `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/unit/test_course_type_classifier.py tests/unit/test_tutor_schema.py tests/integration/test_tutor_api.py -q`
  - 结果：`57 passed, 1 skipped`
- classifier branch coverage:
  - `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m coverage run --branch -m pytest tests/unit/test_course_type_classifier.py -q`
  - `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m coverage report --include="app/services/course_type_classifier.py" -m`
  - 结果：`Branch Cover 100%`
- frontend integration:
  - `npm run test -- tests/integration/api.test.ts --run`
  - 结果：`9 passed`

## Phase 2: 双轨规划引擎（已完成）

- [x] knowledge_learning builder 输出 4 步结构
- [x] problem_solving builder 输出 4 步结构
- [x] 每步包含 modalityPlan
- [x] 关键步包含 checkpointSpec
- [x] next/back/jump/respond 不触发重规划
- [x] 旧会话缺省 courseType 回填策略验证
- [x] golden-plan 快照稳定

### Phase 2 回归证据

- backend unit+integration:
  - c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/unit/test_tutor_schema.py tests/unit/test_tutor_service_phase2_planner.py tests/integration/test_tutor_api.py -vv
  - 结果: 46 passed, 1 skipped
- 关键断言覆盖:
  - 双 builder golden 快照: tests/unit/test_tutor_service_phase2_planner.py
  - 旧会话回填: tests/unit/test_tutor_service_phase2_planner.py
  - next/back/jump/respond 不重规划: tests/integration/test_tutor_api.py::TestTutorSessionAPI::test_list_sessions_back_jump_and_respond_flow

## Phase 3: 多模态与参数交互（已完成）

- [x] image/comic/animation 载荷协议回归
- [x] 生图超时降级链路验证
- [x] 参数交互组件端到端测试
- [x] learning 新事件聚合回归

### Phase 3 回归证据

- backend multimodal + fallback:
  - `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/unit/test_content_schema.py tests/unit/test_content_service.py tests/integration/test_content_api.py -q`
  - 结果: `12 passed`
  - 覆盖点: image/comic/animation 载荷、image timeout/failure fallback to markdown
- frontend parameter interaction E2E:
  - `npm run test:e2e -- tests/e2e/tutor-learning.spec.ts`
  - 结果: `1 passed`
  - 覆盖点: 参数交互触发重生成 + image fallback 场景 + learning `parameter_adjusted` 事件回流
- frontend renderer smoke:
  - `npm run test -- src/components/content/ContentRenderer.test.tsx --run`
  - 结果: `2 passed`

## Phase 4: 灰度与硬化（已完成）

- [x] legacy + course-v1 并行兼容回归
- [x] 性能与稳定性门禁达标
- [x] 故障演练与回退验证完成

### Phase 4 回归证据

- backend Phase 4 hardening gates:
  - `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/integration/test_tutor_api_phase4_hardening.py -q -s`
  - 结果: `4 passed`
  - 覆盖点:
    - mixed legacy/new/mixed-fields 契约矩阵
    - mixed canary traffic 无 blocking 5xx
    - 性能门禁（in-memory canary）
    - rollback drill（Redis primary down -> memory fallback -> failback）
- backend targeted compatibility pack:
  - `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/unit/test_course_type_classifier.py::test_resolve_auto_strategy_applies_legacy_override_if_present tests/unit/test_tutor_schema.py::TestTutorAnalyzeSchemas::test_tutor_analyze_request_legacy_course_type_maps_to_override tests/unit/test_tutor_schema.py::TestTutorAnalyzeSchemas::test_tutor_session_start_request_manual_override_and_legacy_field tests/integration/test_tutor_api.py::TestTutorAnalyzeAPI::test_tutor_analyze_legacy_course_type_field_is_compatible tests/integration/test_tutor_api.py::TestTutorSessionAPI::test_session_start_supports_auto_manual_override_paths tests/integration/test_tutor_api.py::TestTutorSessionAPI::test_start_session_legacy_course_type_field_is_compatible -q`
  - 结果: `8 passed`
- frontend API compatibility regression:
  - `npm run test -- tests/integration/api.test.ts --run`
  - 结果: `10 passed`
  - 覆盖点: mixed legacy/new 字段同时透传（`courseTypeStrategy + courseTypeOverride + courseType`）

### Phase 4 性能验收快照

- analyze: avg `1.23 ms`, p95 `1.45 ms`
- session/start: avg `2.82 ms`, p95 `3.41 ms`
- 门禁阈值:
  - analyze p95 < `200 ms`
  - session/start p95 < `350 ms`
- 结论: 通过（显著低于阈值）

## 三件套门禁

- [x] Phase 1 handoff 已更新
- [x] Phase 2 handoff 已更新
- [x] Phase 4 handoff 已更新
- [x] 本回归清单已更新
- [x] 回退策略文档已更新

结论：Phase 4 三件套齐备，满足 GA 准入。
