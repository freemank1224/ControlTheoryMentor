# Phase 03 Handoff: 内容生成与渲染

**阶段代号**: P3
**阶段状态**: ✅ 核心闭环已完成（可交接 P4）
**上游输入**: P2 输出的 session schema、content request shape、graph highlight metadata
**下游消费者**: P4 学习闭环与硬化

## 1. 阶段目标

把 tutor step 从“模板化文本”升级为“内容对象 + 前端渲染”的完整链路。

本阶段完成后，系统必须能够：

1. 生成独立的 content artifact。
2. 通过 API 读取内容对象。
3. 在前端按类型渲染 markdown、mermaid、latex。
4. 让导师页真正消费 content artifact，而不是直接展示模板字符串。

## 2. 开工前必读

1. `docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md`
2. `docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md`
3. `docs/handoffs/07-ai-tutor-phase-02-tutor-orchestration.md`
4. `docs/superpowers/specs/2026-04-18-ai-tutor-system-design.md`

## 3. 输入握手条件

P3 启动前，必须确认 P2 已交付：

1. 稳定的 session response
2. 当前 step 的 content request 输入格式
3. 可供 UI 使用的 graph highlight metadata
4. 可恢复的 tutor session

### 当前已确认的 content request 输入格式

- 位置：`TeachingStep.content.contentRequest`
- 核心身份字段：`stage`、`stepId`、`stepTitle`、`objective`
- 生成上下文字段：`question`、`graphId`、`sessionMode`、`learnerLevel`
- 图谱锚点字段：`primaryConceptId`、`conceptIds`、`highlightedNodeIds`、`evidencePassageIds`
- 渲染协商字段：`responseMode`、`targetContentTypes`、`renderHint`
- 当前默认：P2 输出 `targetContentTypes=["markdown"]`，并用 `responseMode` 标记该 step 是否需要 P3 生成交互式内容

## 4. 本阶段范围

### 范围内

1. `Content Service`
2. `Content API`
3. `content artifact` schema
4. markdown / mermaid / latex 生成链路
5. `ContentRenderer`
6. 导师页与 content artifact 的接线

### 范围外

1. 学习进度建模
2. personalization based on history
3. animation / comic 的真实生成模型接入

## 5. 交付清单

### API 交付

- `POST /api/content/generate`
- `POST /api/content/interactive` 或协议占位
- `GET /api/content/{id}`
- `GET /api/content/{id}/mermaid`
- `GET /api/content/{id}/latex`

### 前端交付

- `ContentRenderer.tsx`
- tutor page 接入 content artifact
- markdown / mermaid / latex 渲染支持

### 测试交付

- content schema 单元测试
- content API 集成测试
- renderer 最小前端测试
- tutor -> content -> render 的集成验证

## 6. 工作包分解

1. 定义 content artifact schema 和 storage strategy。
2. 实现 content generation service 与缓存策略。
3. 设计并实现 `ContentRenderer`。
4. 调整 tutor session / step 输出，让前端按 content ID 拉取内容。
5. 在导师页接入 current step + content artifact 流程。

## 7. 完成标准

必须全部满足：

1. step 输出包含内容对象引用，而不是临时字符串。
2. markdown、mermaid、latex 至少三种类型可真实渲染。
3. 内容对象可重复获取和缓存。
4. tutor page 不再是占位页。

## 8. 交给下一阶段的握手输出

P4 开始前必须能从本阶段拿到：

1. content artifact schema
2. tutor 页面当前交互模型
3. content generation 结果如何关联到 session / step
4. 已知的渲染与生成限制

## 9. 已知风险

1. 如果 content artifact schema 不稳定，P4 的学习跟踪会失去依附对象。
2. Mermaid / LaTeX 渲染失败必须有 fallback，不可阻塞整个 tutor 页面。
3. interactive / animation / comic 可以先保留接口壳子，但必须明确状态为未完成。

## 10. 阶段结束时必须更新的内容

### content artifact schema 摘要

- 新增后端 schema: `backend/app/schemas/content.py`
- 核心对象: `ContentArtifact`
	- 身份与状态: `id`, `status`, `cacheKey`
	- 渲染协商: `renderHint`, `targetContentTypes`
	- 载荷: `markdown`, `mermaid`, `latex`, `interactive`
	- 上下文锚点: `source`（即 `TeachingContentRequest`）
	- 可追踪元数据: `createdAt`, `updatedAt`, `metadata`
- Tutor step 接线字段（`TeachingStep.content`）
	- `contentArtifactId`
	- `contentArtifactStatus`
	- `contentArtifactUpdatedAt`

### 已完成接口

- `POST /api/content/generate`
- `POST /api/content/interactive`
- `GET /api/content/{id}`
- `GET /api/content/{id}/mermaid`
- `GET /api/content/{id}/latex`

实现位置：

- route: `backend/app/api/routes/content.py`
- service: `backend/app/services/content_service.py`
- app 注册: `backend/app/main.py`

### 前端渲染能力

- 新增 `frontend/src/components/content/ContentRenderer.tsx`
	- Markdown: `react-markdown`
	- Mermaid: `mermaid` 运行时渲染 SVG
	- LaTeX: `react-katex` + `katex`
	- interactive: 协议占位 payload 渲染
- 新增 `frontend/src/hooks/useContentArtifact.ts`
	- 按 `contentArtifactId` 拉取 artifact
- 导师页从占位升级为真实流程
	- `frontend/src/components/tutor/TutorWorkspace.tsx`
	- `frontend/src/App.tsx` 路由接线
	- 支持 session 启动、next/back/jump/respond
	- 当前 step 按 `contentArtifactId` 拉取并渲染内容

### 测试结果

后端：

- `cd backend; ../.venv/Scripts/python.exe -m pytest tests/unit/test_content_schema.py tests/unit/test_content_service.py tests/integration/test_content_api.py tests/integration/test_tutor_api.py tests/unit/test_tutor_schema.py -q`
- 结果：`39 passed, 1 skipped, 21 warnings`

前端：

- `cd frontend; npm run build`
- 结果：构建通过
- `cd frontend; npm test -- --run src/components/content/ContentRenderer.test.tsx`
- 结果：`1 passed, 2 tests`

新增测试：

- `backend/tests/unit/test_content_schema.py`
- `backend/tests/unit/test_content_service.py`
- `backend/tests/integration/test_content_api.py`
- `frontend/src/components/content/ContentRenderer.test.tsx`

### 遗留问题

1. `ContentService` 当前仍是模板生成器（`template-v1`），未接入真实 LLM/worker 内容生成。
2. `interactive` 仍是协议占位 payload，未实现动画/comic 真实生成。
3. Mermaid 依赖在前端引入较大 bundle，后续可按需做动态加载和分包优化。
4. 现有 warnings 仍为仓库既有 Pydantic v2 class-based config deprecation，未在本阶段处理。

### 交给 P4 的学习跟踪依赖

1. 稳定 content artifact 身份主键：`TeachingStep.content.contentArtifactId`
2. session-step 到 artifact 的绑定路径：`TutorService._ensure_step_content_artifact`
3. 可重取内容接口：`GET /api/content/{id}`
4. 多模态内容读取接口：`/mermaid`、`/latex` typed payload
5. Tutor 页面交互模型：session 驱动 + current step artifact 渲染 + learner response 回写

## 11. 下一 session 启动提示词

```text
请读取以下文档后继续 P3 阶段开发：
1. docs/superpowers/plans/2026-04-18-ai-tutor-system-blueprint.md
2. docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md
3. docs/handoffs/07-ai-tutor-phase-02-tutor-orchestration.md
4. docs/handoffs/08-ai-tutor-phase-03-content-generation.md

目标：完成内容生成与渲染闭环，只做 content artifact、content API、ContentRenderer 和 tutor page 接线，不进入 learning progress / personalization 模块。
结束前必须更新 handoff 文档中的状态、测试结果、遗留问题和交接输出。
```