# Phase 01 Handoff: 知识底座完善

**阶段代号**: P1
**阶段状态**: ✅ 已完成
**上游输入**: 现有 Graphify worker 主链路、graph artifact 输出、基础 graph API
**下游消费者**: P2 导师编排闭环

## 1. 阶段目标

把现有“PDF -> graph artifact -> 基础展示”的能力升级为“AI 导师可以稳定调用的知识底座”。

本阶段完成后，Tutor 层必须能够：

1. 查询特定概念节点。
2. 获取相关邻居与前置关系。
3. 通过关键字和全文搜索候选概念。
4. 获取单个概念的完整教学上下文包。

## 2. 开工前必读

1. `docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md`
2. `docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md`
3. `docs/superpowers/specs/2026-04-18-ai-tutor-system-design.md`
4. `docs/parity-report-2026-04-18.md`

## 3. 当前仓库基线

### 已有

- Graphify worker 已接入真实语义抽取。
- `GET /api/graph/{graphId}` 能读取 graph artifact 并返回 Cytoscape 数据。
- PDF 上传、Worker、WebSocket 进度链路已成立。

### 不足

- graph route 内仍混有 demo/legacy 逻辑。
- 缺少独立 `node.py` 路由和 service 层。
- 缺少 `concept context` 聚合能力。
- tutor 尚未拥有稳定的图谱查询契约。

## 4. 本阶段范围

### 范围内

1. 建立 `backend/app/services/graph_service.py`
2. 建立 `backend/app/services/node_service.py`
3. 建立 `backend/app/api/routes/node.py`
4. 建立节点详情、邻居、搜索、全文搜索、语义搜索 API
5. 建立 `GET /api/tutor/concept/{id}/context`
6. 为 tutor 层定义 graph lookup contract

### 范围外

1. tutor session persistence
2. content generation
3. learning progress
4. tutor 前端页面

## 5. 交付清单

### API 交付

- `GET /api/node/{id}`
- `GET /api/node/{id}/neighbors`
- `GET /api/node/search`
- `GET /api/node/fulltext`
- `POST /api/node/semantic`
- `GET /api/tutor/concept/{id}/context`

### 代码结构交付

- route 与 service 分层
- graph / node schema 清晰拆分
- 统一的 concept context response model

### 测试交付

- node API 集成测试
- graph service / node service 单元测试
- 至少一条基于真实 artifact 的 context 聚合测试

## 6. 工作包分解

1. 清点当前 `graph.py` 中哪些路径属于真实路径，哪些属于 demo 路径。
2. 抽离 graph artifact / Neo4j 读取逻辑到 service 层。
3. 定义 `NodeDetail`、`NodeNeighbor`、`ConceptContext` 等 schema。
4. 实现 route，并补充测试。
5. 验证 tutor 调用 concept context 的最小路径。

## 7. 完成标准

必须全部满足：

1. Tutor 层不再需要自己读 graph JSON 文件。
2. 节点查询相关 API 有明确 schema，不复用 Cytoscape 视图格式。
3. `concept context` 响应能支撑后续教学计划生成。
4. demo/legacy graph 路径被标记、隔离或收敛，不影响真实路径。

## 8. 交给下一阶段的握手输出

P2 开始前必须能从本阶段拿到：

1. 问题分析可直接调用以下接口，且全部要求 `graphId` 作为图谱范围参数：`GET /api/node/search`、`GET /api/node/fulltext`、`POST /api/node/semantic`、`GET /api/node/{id}`、`GET /api/node/{id}/neighbors`、`GET /api/tutor/concept/{id}/context`。
2. `concept context` 已稳定为：`concept`、`prerequisites`、`relatedNodes`、`formulas`、`examples`、`sourceSections`、`lookup`、`metadata`。
3. tutor 可直接依赖 `lookup` 契约中的 `graphId`、`conceptId`、`sourcePriority`、`semanticSearchStrategy`、`graphSource`、`artifactPath`、`reportPath`、`neo4jEnrichmentAvailable`。
4. 当前查询限制已明确：artifact 为主数据源；Neo4j 仅做 best-effort enrichment；语义搜索当前实现为关键词提取 + fulltext fallback，而非 embedding 检索。

## 9. 遗留问题

1. Graphify 输出质量仍受 provider 和抽取质量影响，节点命中率与上下文完整度不能只从 API 层面判断。
2. Neo4j 当前未携带图级别隔离信息，P1 已采用 artifact-first 规则；P2 如果要强化 Neo4j 读取，需要先补 graph-scoped read model。
3. 语义搜索当前不是强语义召回，只适合作为 tutor analyze 的第一版候选概念检索入口。

## 10. 测试结果

1. 已执行：`c:/Users/Dyson/Documents/ControlTheoryMentor/.venv/Scripts/python.exe -m pytest backend/tests/unit/test_graph_service.py backend/tests/unit/test_node_service.py backend/tests/integration/test_node_api.py backend/tests/integration/test_graph_api.py backend/tests/integration/test_tutor_api.py -q`
2. 结果：`28 passed`。
3. 备注：存在 `21` 条 Pydantic V2 `Config` 旧写法告警，未阻塞本阶段交付，也不属于 P1 范围内功能缺陷。

## 11. 下一 session 启动提示词

可直接复制给下一次开发 session：

```text
请读取以下文档后继续 P1 阶段开发：
1. docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md
2. docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md
3. docs/handoffs/06-ai-tutor-phase-01-knowledge-foundation.md
4. docs/superpowers/specs/2026-04-18-ai-tutor-system-design.md

目标：完成知识底座完善阶段，只做 graph/node/context 相关能力，不进入 tutor persistence、content generation 或 learning 模块。
结束前必须更新 handoff 文档中的状态、测试结果、遗留问题和交接输出。
```