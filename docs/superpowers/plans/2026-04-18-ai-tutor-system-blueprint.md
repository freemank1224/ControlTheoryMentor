# AI 导师系统整体蓝图

**文档日期**: 2026-04-18
**适用范围**: ControlTheoryMentor AI 导师系统的跨阶段、跨 session 接力开发
**配套文档**:
- 设计规格: `docs/superpowers/specs/2026-04-18-ai-tutor-system-design.md`
- 阶段任务分解: `docs/superpowers/plans/2026-04-18-ai-tutor-system-phase-breakdown.md`
- 阶段交接文档: `docs/handoffs/06-ai-tutor-phase-01-knowledge-foundation.md` 到 `docs/handoffs/09-ai-tutor-phase-04-learning-loop.md`

## 1. 目标与问题定义

ControlTheoryMentor 不是一个单纯的 PDF 图谱工具，也不是一个普通问答 Bot。目标系统必须同时满足以下四个能力闭环：

1. **知识图谱生成**: 教材 PDF 经过 Graphify 与 LLM 处理后，得到可查询、可视化、可教学引用的知识图谱。
2. **个性化教学编排**: 用户问题先映射到图谱，再生成教学计划、教学步骤与会话状态。
3. **内容生成与多模态渲染**: 每个教学步骤都可以生成可渲染的内容对象，而不是只返回模板字符串。
4. **学习闭环**: 系统能够记录学习交互、维护进度、调整后续教学。

当前仓库已经基本具备第 1 项的真实 Graphify 主链路，也具备第 2 项的最小步进式 session 骨架，但第 3 和第 4 项尚未形成系统化模块。

## 2. 顶层系统架构

AI 导师系统按五层组织，层与层之间必须通过稳定契约交互，而不是靠 route 文件互相拼接。

### 2.1 前端交互层

职责：承接用户上传、图谱浏览、导师会话、多模态教学内容和学习进度展示。

模块：
- `Upload Experience`
- `Knowledge Graph View`
- `Tutor Session UI`
- `Content Renderer`
- `Learning Progress Panel`
- `Session History / Textbook Context`

### 2.2 API 编排层

职责：提供稳定入口，对外暴露 REST/WebSocket 契约，不承担复杂业务细节。

模块：
- `PDF API`
- `Graph API`
- `Node / Search API`
- `Tutor API`
- `Content API`
- `Learning API`
- `WebSocket Task/Event API`

### 2.3 领域服务层

职责：沉淀核心业务逻辑，使功能可以测试、复用、替换。

模块：
- `Graph Service`
- `Node Search Service`
- `Tutor Orchestrator`
- `Session State Service`
- `Content Service`
- `Learning Tracking Service`
- `LLM Gateway / Prompt Service`

### 2.4 Worker / 异步执行层

职责：处理 PDF 图谱生成、长时内容生成和未来的 agentic 执行任务。

模块：
- `PDF -> Graph Worker`
- `Content Generation Worker`
- `Future Agent Executor`

### 2.5 数据与存储层

职责：为不同数据类型提供清晰边界和持久化位置。

模块：
- `Neo4j`: 知识图谱主库
- `Redis`: 会话状态、任务状态、短期缓存
- `File Storage`: PDF、graph artifacts、content artifacts
- `Vector Store (Future)`: 语义召回和内容检索增强

## 3. 核心架构原则

1. **Graph-first**: AI 导师必须建立在图谱可查询的事实底座上，不能直接退化为纯聊天机器人。
2. **Session-first**: 教学过程必须围绕会话状态机组织，而不是单轮无状态回答。
3. **Content-as-artifact**: 教学内容必须成为可追踪、可缓存、可重渲染的内容对象，而不是临时字符串。
4. **Persistent state**: 教学会话、学习进度、生成内容都必须可持久化，不能长期依赖进程内存。
5. **Contracts before UI**: 每个前端能力都必须先有稳定 API 契约和数据模型。
6. **Async heavy work**: PDF 图谱生成和多模态内容生成优先走异步 worker，不阻塞用户请求链路。
7. **Phase handoff by docs**: 每个阶段都必须产出交接文档，保证新 session 只靠文档就能接力开发。

## 4. 标准数据流

### 4.1 PDF 到图谱

1. 用户上传 PDF。
2. `PDF API` 创建任务并返回 `taskId`。
3. `Worker` 运行 Graphify 与语义抽取。
4. 图谱写入 artifact storage 与 Neo4j。
5. `Graph API` 与 `Node/Search API` 为 tutor 层提供查询能力。

### 4.2 用户问题到教学会话

1. 用户发起教学问题。
2. `Tutor API` 调用 `Tutor Orchestrator`。
3. `Tutor Orchestrator` 先调用 `Node Search Service` 和 `Graph Service` 获取相关节点与上下文。
4. 基于图谱上下文生成教学计划和步骤结构。
5. `Session State Service` 持久化 session，并返回会话摘要给前端。

### 4.3 教学步骤到内容对象

1. 用户推进到某个步骤。
2. `Tutor Orchestrator` 为该步骤生成 `content request`。
3. `Content Service` 判断是否命中缓存；若未命中则调用 LLM/worker 生成内容。
4. 返回 `content artifact`，其中可能包含 markdown、mermaid、latex、interactive payload 等。
5. 前端 `Content Renderer` 按类型渲染。

### 4.4 用户交互到学习闭环

1. 用户回复、跳步、反馈、完成练习。
2. `Learning Tracking Service` 记录概念掌握状态、当前进度、偏好和薄弱点。
3. `Tutor Orchestrator` 根据学习记录调整后续步骤、难度和建议。

## 5. 目标模块边界

### 5.1 Graph Service

输入：graph artifacts、Neo4j 数据

输出：
- 完整图谱
- 子图
- 节点详情
- 概念上下文聚合结果

### 5.2 Tutor Orchestrator

输入：用户问题、graph context、session state、learning state

输出：
- 分析结果
- teaching plan
- current step transition
- graph highlight hints
- content generation requests

### 5.3 Content Service

输入：step request、concept context、render type、difficulty

输出：
- `content artifact`
- `render metadata`
- `cache key`
- `content status`

### 5.4 Learning Tracking Service

输入：user action、session outcome、content interaction

输出：
- progress snapshot
- mastered / weak concepts
- next-step recommendation

## 6. 目标仓库结构

现有仓库已经有 `backend/app/api/routes`、`worker/`、`frontend/src/components` 等基础结构，但为了支撑完整系统，推荐落到以下目标形态：

```text
backend/app/
  api/
    routes/
      pdf.py
      graph.py
      node.py
      tutor.py
      content.py
      learning.py
    websocket/
      handler.py
  services/
    graph_service.py
    node_service.py
    tutor_service.py
    session_service.py
    content_service.py
    learning_service.py
    llm_service.py
  repositories/
    graph_repository.py
    session_repository.py
    content_repository.py
    learning_repository.py
  schemas/
    pdf.py
    graph.py
    node.py
    tutor.py
    content.py
    learning.py

frontend/src/
  components/
    graph/
    tutor/
    content/
    learning/
    layout/
    upload/
  hooks/
    useKnowledgeGraph.ts
    useTutorSession.ts
    useContentArtifact.ts
    useLearningProgress.ts
  services/
    api.ts
  types/
    api.ts
```

## 7. 阶段划分

系统分四个阶段推进，每个阶段必须形成独立闭环并产出 handoff 文档。

1. **阶段 1: 知识底座完善**
   目标：把图谱能力从“可展示”升级到“可被 tutor 调用”。

2. **阶段 2: 导师编排闭环**
   目标：把问题分析、图谱映射、教学计划、会话推进全部串成稳定状态机。

3. **阶段 3: 内容生成与多模态渲染**
   目标：让每个步骤产生真正的内容对象，并能在前端渲染。

4. **阶段 4: 学习闭环与系统硬化**
   目标：记录学习进度、形成个性化反馈，并补齐测试、监控与回归基线。

## 8. 当前仓库基线判断

### 已经具备

- 真实 Graphify worker 主链路
- graph artifact 输出
- 基础图谱获取接口
- PDF 上传 + WebSocket 进度
- 最小 tutor session 状态机骨架

### 尚未系统化

- `backend/app/services` 领域服务层
- `Node/Search API` 与完整 concept context
- `tutor/analyze` 与会话列表/恢复
- `Content API` 与内容 artifact 模型
- `ContentRenderer` 与导师主页面
- `Learning API` 与进度记录
- 阶段级 handoff 协议

## 9. 文档接力规则

每个阶段的新 session 必须遵守以下规则：

1. 先阅读本蓝图。
2. 再阅读阶段任务分解文档。
3. 然后读取当前阶段 handoff 文档。
4. 只在阶段定义的范围内开发，不跨阶段偷做功能。
5. 每个阶段结束时更新 handoff 文档中的 `已完成`、`遗留问题`、`交给下一阶段的输入`。

## 10. 成功标准

当以下四个闭环全部成立时，才算达到 AI 导师系统的整体目标：

1. 用户上传教材后，能够得到真实可查询图谱。
2. 用户提问后，系统能把问题映射到图谱并生成教学计划。
3. 用户进入步骤后，系统能返回独立内容对象并完成多模态渲染。
4. 用户完成学习后，系统能记录进度并影响后续教学。