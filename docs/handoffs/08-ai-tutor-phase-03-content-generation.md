# Phase 03 Handoff: 内容生成与渲染

**阶段代号**: P3
**阶段状态**: ⏳ 待完成
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

完成阶段时，请在本文件补充：

- `阶段状态`
- `content artifact schema 摘要`
- `已完成接口`
- `前端渲染能力`
- `测试结果`
- `遗留问题`
- `交给 P4 的学习跟踪依赖`

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