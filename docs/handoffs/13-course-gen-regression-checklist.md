# Course Generation Regression Checklist

- 文档版本: v1.0
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

## Phase 2: 双轨规划引擎（待执行）

- [ ] knowledge_learning builder 输出 4 步结构
- [ ] problem_solving builder 输出 4 步结构
- [ ] 每步包含 modalityPlan
- [ ] 关键步包含 checkpointSpec
- [ ] next/back/jump/respond 不触发重规划
- [ ] 旧会话缺省 courseType 回填策略验证
- [ ] golden-plan 快照稳定

## Phase 3: 多模态与参数交互（待执行）

- [ ] image/comic/animation 载荷协议回归
- [ ] 生图超时降级链路验证
- [ ] 参数交互组件端到端测试
- [ ] learning 新事件聚合回归

## Phase 4: 灰度与硬化（待执行）

- [ ] legacy + course-v1 并行兼容回归
- [ ] 性能与稳定性门禁达标
- [ ] 故障演练与回退验证完成

## 三件套门禁

- [x] Phase 1 handoff 已更新
- [x] 本回归清单已更新
- [x] 回退策略文档已更新

结论：Phase 1 三件套齐备，可进入 Phase 2。
