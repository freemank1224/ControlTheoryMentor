# AI 导师系统阶段任务分解

**文档日期**: 2026-04-18
**用途**: 作为跨 session 接力开发的阶段总控清单
**先读文档**:
- `docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md`
- `docs/superpowers/specs/2026-04-18-ai-tutor-system-design.md`

## 1. 阶段总览

| 阶段 | 名称 | 核心目标 | 依赖 | 输出物 |
|------|------|----------|------|--------|
| P1 | 知识底座完善 | 让 tutor 能稳定调用图谱和节点上下文 | 现有 Graphify 主链路 | graph/node/context API + graph service |
| P2 | 导师编排闭环 | 让问题分析、计划生成、会话推进成为持久化状态机 | P1 | tutor analyze/session orchestration |
| P3 | 内容生成与渲染 | 让步骤输出真实内容对象并在前端渲染 | P2 | content API + content renderer |
| P4 | 学习闭环与硬化 | 形成进度、反馈、个性化与系统回归 | P3 | learning API + progress model + regression suite |

## 2. 阶段依赖关系

```text
P1 知识底座完善
  -> P2 导师编排闭环
       -> P3 内容生成与渲染
            -> P4 学习闭环与硬化
```

强约束：
- P2 不应在没有 `concept context` 和节点检索基线时硬写 tutor 分析逻辑。
- P3 不应在没有稳定 session/current step 契约时直接实现内容生成。
- P4 不应在没有 content artifact 和 session persistence 时定义学习进度模型。

## 3. 阶段 1: 知识底座完善

### 3.1 目标

将现有图谱链路从“artifact 可展示”提升为“tutor 可消费的数据底座”。

### 3.2 工作包

1. 建立 `Graph Service` 与 `Node Service`，将 route 中的 demo/legacy 逻辑抽离。
2. 明确 graph artifact、Neo4j 读模型和 API 输出模型之间的映射。
3. 实现节点详情、邻居、精确搜索、全文搜索、语义搜索的分层接口。
4. 实现 `concept context` 聚合能力，至少包含：概念、相关节点、前置概念、公式、例题、来源章节。
5. 清理或标记旧的 demo graph create/query/traverse 路径，避免和真实路径混用。
6. 为 tutor 层定义统一的 graph lookup contract。

### 3.3 最小交付

- `GET /api/node/{id}`
- `GET /api/node/{id}/neighbors`
- `GET /api/node/search`
- `GET /api/node/fulltext`
- `POST /api/node/semantic`
- `GET /api/tutor/concept/{id}/context`

### 3.4 完成标准

- tutor 层不再直接拼装 graph JSON 文件。
- 任意一个 tutor 会话可以通过 API 获取 concept context。
- 针对真实 graph artifact 至少有一套集成测试。

## 4. 阶段 2: 导师编排闭环

### 4.1 目标

把 tutor 从“模板响应”升级为基于图谱上下文的编排系统。

### 4.2 工作包

1. 实现 `POST /api/tutor/analyze`，输入问题，输出相关图谱节点与分析摘要。
2. 将 P1 的 `passages` 真正接入 tutor analyze 与 plan generation，使导师编排基于图谱结果 + 原文证据，而不是只消费节点标签。
3. 将 chunk 级 `passages` 进一步细化为句段级引用与排序，降低 tutor 上下文噪声，并为后续 content generation 提供更干净的 evidence payload。
4. 将 session state 从进程内存迁移到 Redis。
5. 扩展 tutor session API：`current`、`back`、`jump`、`sessions` 列表与恢复。
6. 建立 `Tutor Orchestrator`，统一处理 analyze、plan、step transition。
7. 在 step 输出中加入 graph highlight metadata。
8. 将 session response 与前端导师页需要的契约稳定下来。

### 4.3 最小交付

- `POST /api/tutor/analyze`
- `GET /api/tutor/sessions`
- `GET /api/tutor/session/{id}` 或 `/current`
- `POST /api/tutor/session/{id}/back`
- `POST /api/tutor/session/{id}/jump`
- Redis-based session store

### 4.4 完成标准

- 服务重启前后的 session 状态具备可恢复机制。
- tutor session 的每一步都能指出自己依赖的 graph topics / highlighted nodes。
- step transition 不再只依赖硬编码模板。

## 5. 阶段 3: 内容生成与渲染

### 5.1 目标

让每个教学步骤输出真正的 `content artifact`，并由前端按类型渲染。

### 5.2 工作包

1. 建立 `Content Service` 与 `Content API`。
2. 定义 `content artifact` schema，包括 `id`、`type`、`status`、`data`、`source context`。
3. 先实现 markdown、mermaid、latex 三类内容；animation/comic/interactive 保留协议。
4. 加入内容缓存和可重取能力。
5. 实现前端 `ContentRenderer`。
6. 将导师页接入 session + content artifact 流程。

### 5.3 最小交付

- `POST /api/content/generate`
- `GET /api/content/{id}`
- `GET /api/content/{id}/mermaid`
- `GET /api/content/{id}/latex`
- `frontend/src/components/content/ContentRenderer.tsx`

### 5.4 完成标准

- step 不再只返回模板 markdown 文本。
- content artifact 可以独立查询和重复渲染。
- 前端导师页能显示至少 markdown + mermaid + latex。

## 6. 阶段 4: 学习闭环与硬化

### 6.1 目标

让系统从“会话式导师”升级为“持续学习导师”。

### 6.2 工作包

1. 建立 `Learning Tracking Service` 与 `Learning API`。
2. 记录 step 完成、回答质量、反馈、已掌握概念、待复习概念。
3. 将 learning state 反馈给 tutor analyze 与 plan generation。
4. 完成 tutor session 的前端全流程体验。
5. 加入内容生成、学习跟踪、session 恢复的集成/E2E 测试。
6. 增加错误码、日志、观测与回归清单。

### 6.3 最小交付

- `POST /api/learning/track`
- `GET /api/learning/progress`
- `POST /api/learning/feedback`
- tutor page 可用版本
- 内容生成和学习进度的回归测试

### 6.4 完成标准

- 用户重新进入系统后，能看到自己的当前进度。
- tutor 在新会话开始时可以读取历史学习状态。
- 系统具备覆盖核心闭环的回归测试。

## 7. 每阶段统一输出物

每个阶段结束时必须交付以下内容：

1. 代码变更
2. 通过的测试结果摘要
3. 更新后的 handoff 文档
4. 需要下一阶段接手的输入列表
5. 未解决风险与明确的边界说明

## 8. 每阶段禁止事项

1. 不跨阶段提前做 UI 或后续业务逻辑，除非当前阶段契约必须预留。
2. 不把临时模板逻辑包装成“已完成内容生成”。
3. 不把进程内存态状态管理误写成“持久化完成”。
4. 不让前端直接依赖 worker artifact 目录结构。
5. 不在没有 handoff 更新的情况下结束阶段。

## 9. 推荐执行顺序

每次新 session 的建议顺序：

1. 阅读蓝图文档。
2. 阅读当前阶段 handoff 文档。
3. 阅读上一阶段 handoff 文档中的输出物与未解决问题。
4. 仅实现当前阶段工作包。
5. 用当前阶段的完成标准做收尾验证。
6. 更新 handoff 文档后结束 session。