# AI 导师系统设计文档

**项目**: ControlTheoryMentor - AI 驱动的个性化自学导师系统
**日期**: 2026-04-18
**版本**: 1.0
**阶段**: A2 - 知识图谱核心 + API 服务

---

## 1. 项目概述

### 1.1 目标

构建一个集成多模态 LLM 服务的 AI 驱动课程个性化自学导师系统，具备以下核心能力：

1. **知识图谱生成**: 基于 Graphify 从 PDF 教材解析生成学科知识图谱
2. **个性化教学**: 结合知识图谱设计完整讲解内容（引入、拆解、逐步解析、总结）
3. **多模态互动**: 生成并呈现多模态教学内容（Markdown、Mermaid、LaTeX、动画、漫画、交互图形）
4. **知识映射**: 自动分析用户问题，映射到知识图谱节点

### 1.2 A2 阶段范围

- 单个 PDF 上传（最大 1200 页）→ 解析 → 生成图谱 → 可视化展示
- 图谱持久化存储
- 节点搜索/查询 API（精确匹配 + 全文搜索 + 关键词提取）
- 基础步进式教学交互框架

### 1.3 设计约束

- 外观风格遵循 [DESIGN.md](../../../../DESIGN.md) (Claude/Anthropic 设计系统)
- 技术栈: React + Vite / FastAPI / Neo4j / Redis
- 后台处理模式（用户上传后可离开，完成后通知）

---

## 2. 系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Knowledge   │  │ AI Tutor     │  │ Multi-modal  │          │
│  │  Graph View  │  │ Chat/UI      │  │ Sandbox      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Knowledge│ │  AI      │ │ Content  │ │ Learning │            │
│  │  API     │ │  Tutor   │ │ Gen      │ │ Track    │            │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
└───────┼────────────┼────────────┼────────────┼──────────────────┘
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Service Layer                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────────┐                 │
│  │ Graph     │ │ AI/LLM    │ │ Content       │                 │
│  │ Service   │ │ Service   │ │ Service       │                 │
│  └─────┬─────┘ └─────┬─────┘ └───────┬───────┘                 │
└────────┼─────────────┼─────────────────┼────────────────────────┘
         ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐               │
│  │ Neo4j   │ │ Redis   │ │ Storage │ │ Vector  │               │
│  │ (Graph) │ │ (Cache) │ │ (Files) │ │ (Future)│               │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘               │
└─────────────────────────────────────────────────────────────────┘
                         ▲
                         │
┌─────────────────────────────────────────────────────────────────┐
│                      Worker Layer                               │
│  ┌───────────┐ ┌───────────┐ ┌───────────────┐                 │
│  │ PDF →     │ │ Content   │ │ Agent         │                 │
│  │ Graph     │ │ Generator │ │ Executor      │                 │
│  │ Worker    │ │ Workers   │ │ (Future)      │                 │
│  └───────────┘ └───────────┘ └───────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
control-theory-mentor/
├── frontend/              # React + Vite
│   ├── src/
│   │   ├── components/    # UI 组件
│   │   ├── pages/         # 页面路由
│   │   ├── hooks/         # React Hooks
│   │   └── styles/        # DESIGN.md 样式变量
│   └── package.json
├── backend/              # FastAPI
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── services/     # 业务逻辑
│   │   ├── models/       # 数据模型
│   │   └── main.py
│   └── requirements.txt
├── worker/               # Graphify Worker
│   ├── graphify_wrapper.py
│   └── requirements.txt
├── shared/               # 共享类型/配置
│   └── types.ts
├── docker-compose.yml
└── DESIGN.md             # 设计系统规范
```

---

## 3. 数据库设计

### 3.1 Neo4j 图模式

#### 节点类型

```cypher
// PDF 文档
(:PDF {
  id: "uuid",
  filename: "控制理论教材.pdf",
  uploadTime: datetime,
  status: "processing|completed|failed",
  pageCount: 1200,
  metadata: {}
})

// 知识点/概念
(:Concept {
  id: "uuid",
  name: "二阶系统",
  description: "具有两个独立储能环节的动态系统...",
  sourcePage: [45, 46, 47],
  level: "basic|intermediate|advanced",
  chapter: "第3章"
})

// 章节/节
(:Section {
  id: "uuid",
  title: "3.2 时域分析",
  order: 1,
  parentId: "uuid"
})

// 公式
(:Formula {
  id: "uuid",
  latex: "$$\\frac{d^2y}{dt^2} + 2\\zeta\\omega_n\\frac{dy}{dt} + \\omega_n^2 y = \\omega_n^2 u$$",
  name: "二阶系统微分方程",
  description: "标准形式..."
})

// 示例/例题
(:Example {
  id: "uuid",
  title: "RLC 电路响应",
  content: "..."
})
```

#### 关系类型

```cypher
(PDF)-[:HAS_SECTION]->(Section)
(PDF)-[:CONTAINS_CONCEPT]->(Concept)
(Section)-[:INCLUDES]->(Concept)
(Concept)-[:PREREQUISITE]->(Concept)
(Concept)-[:RELATED_TO]->(Concept)
(Concept)-[:USES_FORMULA]->(Formula)
(Concept)-[:HAS_EXAMPLE]->(Example)
```

#### 索引

```cypher
CREATE FULLTEXT INDEX concept_search FOR (c:Concept) ON EACH [c.name, c.description]
CREATE INDEX ON :Concept(id)
CREATE INDEX ON :PDF(id)
```

### 3.2 Redis 数据结构

```
# 任务队列
queue:pdf:tasks          # List, Celery 任务队列

# 任务状态
task:{taskId}:status     # String, "processing|completed|failed"
task:{taskId}:progress   # Hash, {percent: 45, message: "..."}

# 会话缓存
session:{sessionId}:state # Hash, 教学会话状态
```

---

## 4. API 设计

### 4.1 RESTful API

#### PDF 管理

```
POST   /api/pdf/upload          # 上传 PDF，返回 taskId
GET    /api/pdf/{id}            # 获取 PDF 信息
GET    /api/pdf/{id}/status     # 查询处理状态
GET    /api/pdf                 # 列出所有 PDF
```

#### 知识图谱

```
GET    /api/graph/{pdfId}       # 获取完整图谱（Cytoscape 格式）
GET    /api/graph/{pdfId}/nodes # 分页获取节点
GET    /api/graph/{pdfId}/edges # 分页获取边
```

#### 节点查询

```
GET    /api/node/{id}           # 获取节点详情
GET    /api/node/{id}/neighbors # 获取邻居节点（N=1）
GET    /api/node/search?q={kw}  # 精确匹配搜索
GET    /api/node/fulltext?q={kw} # 全文搜索（D1）
POST   /api/node/semantic       # 语义搜索（D2，LLM 提取关键词）
```

#### AI 导师

```
POST   /api/tutor/chat          # 发送问题，AI 生成讲解
GET    /api/tutor/session/{id}  # 获取会话历史
GET    /api/tutor/sessions      # 用户所有会话列表
POST   /api/tutor/analyze       # 分析问题，返回相关知识点
GET    /api/tutor/concept/{id}/context # 获取概念的完整上下文
```

#### 教学会话（步进式）

```
POST   /api/tutor/session/start        # 启动新的教学会话
GET    /api/tutor/session/{id}/current # 获取当前步骤状态
POST   /api/tutor/session/{id}/next    # 执行下一步
POST   /api/tutor/session/{id}/respond # 用户响应后继续
POST   /api/tutor/session/{id}/back    # 回退到上一步
POST   /api/tutor/session/{id}/jump    # 跳转到指定步骤
```

#### 内容生成

```
POST   /api/content/generate    # 根据知识点生成教学内容
POST   /api/content/interactive # 生成交互式内容（图形/动画）
GET    /api/content/{id}        # 获取已生成的内容
GET    /api/content/{id}/mermaid     # 获取 Mermaid 图表
GET    /api/content/{id}/latex       # 获取 LaTeX 公式
GET    /api/content/{id}/animation   # 获取动画配置
GET    /api/content/{id}/comic       # 获取 AI 漫画场景
```

#### 学习进度

```
POST   /api/learning/track      # 记录学习交互
GET    /api/learning/progress   # 获取学习进度
POST   /api/learning/feedback   # 用户反馈
```

### 4.2 WebSocket

```
WS /ws/graph/{taskId}
# 事件类型：
# - task.started
# - task.progress {percent, message}
# - task.completed {graphId}
# - task.failed {error}
```

### 4.3 响应格式

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

图谱数据（Cytoscape.js 格式）：
```json
{
  "elements": {
    "nodes": [
      {"data": {"id": "c1", "label": "二阶系统", "type": "concept"}}
    ],
    "edges": [
      {"data": {"source": "c1", "target": "c2", "label": "PREREQUISITE"}}
    ]
  }
}
```

---

## 5. 前端设计

### 5.1 主界面布局

```
┌─────────────────────────────────────────────────────────────────────┐
│  导航栏 (Sticky, Warm Sand #e8e6dc)                                  │
│  [Logo] 控制理论导师  [📚 教材管理] [⚙️ 设置]                       │
├─────────────────────────────────────┬───────────────────────────────┤
│  左侧：主交互区 (66%)                │  右侧：信息面板 (33%)          │
│  ┌─────────────────────────────┐   │  ┌─────────────────────────┐  │
│  │   教学内容展示区             │   │  │   知识图谱              │  │
│  │   (ContentRenderer)         │   │  │   (CytoscapeCanvas)     │  │
│  │   - Markdown/Mermaid/LaTeX  │   │  │   [当前高亮节点]        │  │
│  │   - 动画/漫画               │   │  │   [相关节点]            │  │
│  │   - 交互图形               │   │  │                         │  │
│  │   ━━━━━━━━━━━━━━━━━━━━━━━  │   │  ├─────────────────────────┤  │
│  │   用户输入区                │   │  │   学习进度              │  │
│  │   ┌─────────────────────┐  │   │  │   [当前步骤 2/5]        │  │
│  │   │ [文本输入框]         │  │   │  │   [已完成知识点]        │  │
│  │   │ [🎤 语音输入按钮]    │  │   │  │                         │  │
│  │   │ [发送]              │  │   │  ├─────────────────────────┤  │
│  │   └─────────────────────┘  │   │  │   当前会话              │  │
│  │                             │   │  │   [会话历史]            │  │
│  └─────────────────────────────┘   │  ├─────────────────────────┤  │
│                                     │  │   教材信息              │  │
│                                     │  │   [当前教材]            │  │
│                                     │  │   [章节导航]            │  │
│                                     │  └─────────────────────────┘  │
└─────────────────────────────────────┴───────────────────────────────┘
```

### 5.2 DESIGN.md 样式规范

```css
/* 主背景 */
--bg-parchment: #f5f4ed;
--bg-ivory: #faf9f5;

/* 文字 */
--text-primary: #141413;  /* Anthropic Near Black */
--text-secondary: #5e5d59; /* Olive Gray */

/* 强调 */
--accent-terracotta: #c96442;

/* 组件 */
--card-radius: 12px;
--btn-primary-bg: #c96442;
--btn-primary-text: #faf9f5;
```

### 5.3 核心组件

```
<TutorSessionLayout>
  <Navbar />
  <MainGrid>
    <LeftPanel>
      <ContentDisplay />      {/* 教学内容展示 */}
      <InputArea>             {/* 用户输入 + 语音 */}
        <TextInput />
        <VoiceInputButton />
        <StepControls />      {/* 上一步/下一步/跳转 */}
      </InputArea>
    </LeftPanel>
    <RightPanel>
      <KnowledgeGraph />      {/* Cytoscape.js */}
      <LearningProgress />
      <SessionHistory />
      <TextbookInfo />
    </RightPanel>
  </MainGrid>
</TutorSessionLayout>
```

### 5.4 多模态内容渲染

```tsx
interface ContentRendererProps {
  content: {
    type: 'markdown' | 'mermaid' | 'latex' | 'comic' | 'animation' | 'interactive';
    data: any;
  };
}
```

---

## 6. 核心数据流

### 6.1 PDF → 知识图谱（后台处理）

```
用户上传 PDF
    ↓
Frontend: POST /api/pdf/upload
    ↓
Backend: 生成 taskId → Redis 队列
    ↓
Frontend: 连接 WS /ws/graph/{taskId} 监听进度
    ↓
Worker: 从 Redis 取任务
    ↓
Worker: 调用 Graphify 解析 PDF
    ↓ (实时推送进度)
WS: task.progress {percent: 45, message: "正在提取第3章概念..."}
    ↓
Worker: 写入 Neo4j (节点 + 关系)
    ↓
Worker: 更新 PDF 状态为 completed
    ↓
WS: task.completed {graphId}
    ↓
Frontend: 导航到图谱视图
```

### 6.2 AI 导师步进式教学

```
用户提问
    ↓
Frontend: POST /api/tutor/session/start
    ↓
Backend: LLM 分析问题 → 匹配图谱节点 → 生成教学计划
    ↓
Frontend: 显示教学计划概览
    ↓
用户点击"开始学习"
    ↓
Frontend: POST /api/tutor/session/{id}/next
    ↓
Backend: 执行 step-1 → 生成内容
    ↓
Frontend: ContentRenderer 渲染内容
    ↓
右侧图谱同步：高亮相关节点
    ↓
用户交互 (回答问题/点击按钮)
    ↓
Frontend: POST /api/tutor/session/{id}/respond
    ↓
Backend: 根据用户响应决定下一步
    ↓
循环直到完成
```

---

## 7. 错误处理

### 7.1 错误码

```python
class ErrorCode(Enum):
    # 客户端错误
    INVALID_PDF = (4001, "PDF 文件格式无效")
    PDF_TOO_LARGE = (4002, "PDF 超过 1200 页限制")
    NODE_NOT_FOUND = (4004, "知识点不存在")
    INVALID_QUERY = (4005, "查询参数错误")

    # 服务端错误
    GRAPHIFY_ERROR = (5001, "图谱生成失败")
    NEO4J_ERROR = (5002, "数据库查询失败")
    LLM_TIMEOUT = (5003, "AI 响应超时")
    WORKER_UNAVAILABLE = (5004, "处理服务不可用")
```

### 7.2 Worker 故障处理

```python
@celery.task(bind=True, max_retries=3)
def process_pdf(task_id):
    try:
        graphify.process()
    except Exception as e:
        redis.set(f"task:{task_id}:status", "failed")
        raise
```

---

## 8. 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端 | React + Vite + Cytoscape.js + Mermaid + KaTeX + Framer Motion |
| 后端 | FastAPI + Celery + Redis |
| 图数据库 | Neo4j |
| LLM | Vercel AI SDK + AI Gateway |
| 样式 | DESIGN.md (Claude 主题) |
| 容器 | Docker + docker-compose |

---

## 9. 测试策略

```
tests/
├── unit/              # 单元测试
│   ├── backend/
│   ├── worker/
│   └── frontend/
├── integration/       # 集成测试
│   ├── api_neo4j.py
│   └── worker_flow.py
└── e2e/               # 端到端测试
    └── tutor_session.spec.ts
```

---

## 10. 下一步

设计完成后，将进入实现计划阶段：
1. 项目初始化（仓库结构、依赖配置）
2. 后端 API 开发（FastAPI + Neo4j）
3. Worker 服务开发（Graphify 集成）
4. 前端组件开发（React + Cytoscape.js）
5. 集成测试与部署
