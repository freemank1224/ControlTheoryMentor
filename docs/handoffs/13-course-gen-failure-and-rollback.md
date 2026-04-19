# Course Generation Failure and Rollback Playbook

- 文档版本: v1.0
- 更新时间: 2026-04-19

## 1. 目的

定义课程生成分阶段改造期间的故障识别、止损和回退操作，确保不破坏现有 tutor 主流程。

## 2. 通用故障分级

1. P0: analyze/start 大面积 5xx 或会话不可创建。
2. P1: 分类结果错误率明显升高，影响主路径质量。
3. P2: 前端入口可用但策略字段行为偏差。
4. P3: 文档/测试证据不齐，阻塞阶段握手。

## 3. Phase 1 专项：分类与契约扩展

### 3.1 失败信号

1. `POST /api/tutor/analyze` 或 `POST /api/tutor/session/start` 返回 422/500，且与新字段相关。
2. `finalCourseType` / `autoDecision` 缺失或结构不符合契约。
3. manual/override 失效（最终类型不符合用户输入策略）。
4. 旧客户端请求（不带新字段）回归失败。

### 3.2 快速止损

1. 前端临时将策略固定为 `auto`，停止发送 override 字段。
2. 后端依赖旧行为：缺失字段自动回退到 auto path。
3. 保留 legacy `courseType` 映射，避免客户端升级耦合。

### 3.3 回退策略

#### 软回退（优先）

1. 将请求统一走 `courseTypeStrategy=auto`。
2. 仅透传 `autoDecision` 供观测，不使用人工覆盖结果。
3. 保留新字段但不激活 manual/override UI 入口。

#### 硬回退（必要时）

1. 回退 [backend/app/services/tutor_service.py](backend/app/services/tutor_service.py) 对 `finalCourseType/courseTypeDecision` 的写入逻辑。
2. 回退 [backend/app/schemas/tutor.py](backend/app/schemas/tutor.py) 新增字段并恢复旧契约。
3. 回退 [frontend/src/components/tutor/TutorWorkspace.tsx](frontend/src/components/tutor/TutorWorkspace.tsx) 新增策略入口。
4. 执行回归测试确认恢复：
   - backend tutor schema + tutor api
   - frontend api integration

### 3.4 数据兼容

1. 会话 metadata 允许缺省 courseType 相关字段。
2. 读取时使用默认 `knowledge_learning` + 兜底 `autoDecision`，避免历史会话崩溃。

## 4. 验收与恢复完成标准

1. analyze/start 恢复 200 主路径。
2. legacy 请求可正常创建会话。
3. 至少通过：
   - `tests/unit/test_tutor_schema.py`
   - `tests/integration/test_tutor_api.py`
   - `frontend/tests/integration/api.test.ts`
4. 更新 handoff + regression checklist + rollback 三件套状态。

## 5. 责任与升级

1. P0/P1 触发：立即停止进入下一阶段，先完成本阶段回退闭环。
2. 未完成三件套更新：禁止标记阶段完成。
3. 回退后必须在下一次 Session 首屏记录“回退原因/影响范围/恢复证据”。
