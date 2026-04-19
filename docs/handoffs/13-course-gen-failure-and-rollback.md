# Course Generation Failure and Rollback Playbook

- 文档版本: v1.2
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

## 5. Phase 2 专项：双轨规划引擎

### 5.1 失败信号

1. `POST /api/tutor/session/start` 生成的 `plan.steps` 非 4 步，或 track 与 `finalCourseType` 不一致。
2. `plan.planFinalized` 缺失或为 `false`，导致状态机流转期间可能重复规划。
3. `modalityPlan` / `checkpointSpec` 字段缺失，前端渲染和 checkpoint 评估契约不稳定。
4. `next/back/jump/respond` 任一操作导致 plan 内容变化（非仅 runtime 状态变化）。
5. 旧会话读取时缺省 `courseType` 触发 5xx 或返回结构不完整。

### 5.2 快速止损

1. 临时固定走 `knowledge_learning` builder，避免双轨分流异常扩大。
2. 若新字段影响前端渲染，保留 `content.markdown` 主路径并忽略 `modalityPlan/checkpointSpec`。
3. 暂停 checkpoint 严格评估，保留 `requiresResponse` 交互语义。

### 5.3 回退策略

#### 软回退（优先）

1. 保留双轨入口，但强制 `planFinalized=true` 且禁用重规划逻辑变更。
2. 将 `targetContentTypes` 临时压缩为 `['markdown']`，确保渲染路径单一稳定。
3. 对旧会话继续启用回填逻辑：自动补齐 `courseType/planFinalized/modalityPlan`。

#### 硬回退（必要时）

1. 回退 [backend/app/services/tutor_service.py](backend/app/services/tutor_service.py) 到单 builder 版本。
2. 回退 [backend/app/schemas/tutor.py](backend/app/schemas/tutor.py) 新增 `modalityPlan/checkpointSpec/planFinalized` 字段。
3. 回退 Phase 2 新增测试：[backend/tests/unit/test_tutor_service_phase2_planner.py](backend/tests/unit/test_tutor_service_phase2_planner.py) 及相关集成断言。

### 5.4 最小恢复验证

1. `tests/unit/test_tutor_schema.py` 通过。
2. `tests/unit/test_tutor_service_phase2_planner.py` 通过。
3. `tests/integration/test_tutor_api.py` 通过（允许 Redis 恢复用例在本地 skip）。

## 6. Phase 3 专项：多模态与参数交互

### 6.1 失败信号

1. `POST /api/content/generate` 在 image 请求下频繁超时或 5xx，且无 markdown 降级。
2. `ContentArtifactType` 出现 image/comic/animation 后，前端渲染出现空白或崩溃。
3. 参数交互（style/detail/pace/attempt）触发重生成后，learning 事件未回流（`parameter_adjusted` 缺失）。
4. 同一 step 多次参数重生成导致 artifact 缓存错乱或 renderHint 不可用。

### 6.2 快速止损

1. 前端参数组件降级为只读，停止发送 `generationParams`。
2. 强制 `targetContentTypes=['markdown']`，暂时下线 image/comic/animation tab。
3. learning 事件链路异常时，保留 tutor 主链路，参数事件改为非阻塞 best-effort。

### 6.3 回退策略

#### 软回退（优先）

1. 保留多模态 schema，但默认 renderHint 回落到 markdown。
2. image 生成链路切换到 fallback-only 模式，避免外部生图依赖抖动影响主流程。
3. 参数交互仅记录 UI 状态，不触发强制 regenerate。

#### 硬回退（必要时）

1. 回退 [backend/app/services/content_service.py](backend/app/services/content_service.py) 中 image/comic/animation 生成分支。
2. 回退 [backend/app/schemas/content.py](backend/app/schemas/content.py) 的 generation params 与新增 payload 字段。
3. 回退 [frontend/src/components/tutor/TutorWorkspace.tsx](frontend/src/components/tutor/TutorWorkspace.tsx) 参数交互组件。
4. 回退 [frontend/src/components/content/ContentRenderer.tsx](frontend/src/components/content/ContentRenderer.tsx) 新增多模态渲染分支。

### 6.4 最小恢复验证

1. `tests/unit/test_content_schema.py` 通过。
2. `tests/unit/test_content_service.py` 通过（重点验证 image fail to markdown fallback）。
3. `tests/integration/test_content_api.py` 通过。
4. `npm run test:e2e -- tests/e2e/tutor-learning.spec.ts` 通过。

## 7. 责任与升级

1. P0/P1 触发：立即停止进入下一阶段，先完成本阶段回退闭环。
2. 未完成三件套更新：禁止标记阶段完成。
3. 回退后必须在下一次 Session 首屏记录“回退原因/影响范围/恢复证据”。
