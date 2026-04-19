# Phase 04 Handoff: 灰度发布与硬化（GA 收官）

- 阶段代号: P4
- 阶段状态: ✅ 已完成（GA 准入通过）
- 上游输入: Phase 3 多模态与参数交互
- 下游消费者: 生产发布与运维值守
- 文档版本: v1.0
- 更新时间: 2026-04-19

## 1. 阶段目标

在 legacy 与新契约并行的前提下，完成灰度发布与硬化验收，确保：

1. 混合版本请求可兼容。
2. 不出现阻塞型 5xx。
3. 性能达到门禁阈值。
4. 回退路径可演练、可执行。
5. 形成 GA 准入结论并收官。

## 2. 范围内 / 范围外

### 范围内

1. legacy/new/mixed-fields 契约兼容矩阵验证。
2. canary 交通下稳定性验证（无 blocking 5xx）。
3. core API 性能验收（analyze/session start）。
4. primary 故障 -> fallback -> failback 回退演练。
5. 三件套更新与 GA 结论输出。

### 范围外

1. legacy 字段正式下线（本阶段仅并行，不做移除）。
2. Redis/网络层基础设施扩容优化。
3. 新一轮课程分类策略升级（例如 LLM classifier）。

## 3. 交付清单

### 新增测试

- `backend/tests/integration/test_tutor_api_phase4_hardening.py`
  - mixed legacy/new/mixed-fields 契约矩阵
  - mixed canary traffic 无阻塞 5xx
  - 性能门禁验证与 p95 指标输出
  - rollback drill（fallback + failback）

### 前端兼容回归增强

- `frontend/tests/integration/api.test.ts`
  - 新增 mixed-fields 请求透传用例：同时发送
    - `courseTypeStrategy`
    - `courseTypeOverride`
    - `courseType`

### 文档更新

- `docs/handoffs/13-course-gen-regression-checklist.md`
- `docs/handoffs/13-course-gen-failure-and-rollback.md`
- `docs/handoffs/14-ai-course-gen-phase-04-canary-hardening.md`（本文件）

## 4. 测试门禁结果

### 4.1 混合版本通过（PASS）

命令：

- `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/integration/test_tutor_api_phase4_hardening.py -q -s`
- `c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest tests/unit/test_course_type_classifier.py::test_resolve_auto_strategy_applies_legacy_override_if_present tests/unit/test_tutor_schema.py::TestTutorAnalyzeSchemas::test_tutor_analyze_request_legacy_course_type_maps_to_override tests/unit/test_tutor_schema.py::TestTutorAnalyzeSchemas::test_tutor_session_start_request_manual_override_and_legacy_field tests/integration/test_tutor_api.py::TestTutorAnalyzeAPI::test_tutor_analyze_legacy_course_type_field_is_compatible tests/integration/test_tutor_api.py::TestTutorSessionAPI::test_session_start_supports_auto_manual_override_paths tests/integration/test_tutor_api.py::TestTutorSessionAPI::test_start_session_legacy_course_type_field_is_compatible -q`
- `npm run test -- tests/integration/api.test.ts --run`

结果：

- backend phase4 hardening: `4 passed`
- backend targeted compatibility: `8 passed`
- frontend compatibility: `10 passed`

### 4.2 无阻塞 5xx（PASS）

证据：

- `test_phase4_mixed_canary_traffic_has_no_blocking_5xx`
- 结论：混合 canary traffic 期间未出现 status >= 500。

### 4.3 性能达标（PASS）

证据（Phase4 perf metrics）：

- analyze: avg `1.23 ms`, p95 `1.45 ms`
- session/start: avg `2.82 ms`, p95 `3.41 ms`

门禁阈值：

- analyze p95 < `200 ms`
- session/start p95 < `350 ms`

结论：显著低于阈值，性能门禁通过。

### 4.4 回退可执行（PASS）

证据：

- `test_phase4_rollback_drill_fallback_and_failback_keeps_contract`
- 演练路径：primary down -> memory fallback -> primary recover -> failback
- 验证点：
  - `metadata.store` 按预期切换
  - `finalCourseType` 不漂移
  - `planFinalized` 不丢失

## 5. 风险与后续建议

1. 当前仍保留 legacy 字段并行，建议在下一窗口定义 deprecation timeline。
2. 可在生产灰度增加线上 p95 与 5xx 仪表盘，持续对比本地 canary 基线。
3. 若未来新增策略字段，优先补 mixed-fields 合同测试，避免再次出现双版本断裂。

## 6. GA 准入结论

- 混合版本通过: ✅
- 无阻塞 5xx: ✅
- 性能达标: ✅
- 回退可执行: ✅
- 三件套更新完成: ✅

结论：✅ Phase 4 达成，允许 GA。
