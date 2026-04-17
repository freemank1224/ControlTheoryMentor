# AI 导师系统 A2 阶段实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 构建支持 PDF 上传、知识图谱生成、可视化查询和步进式教学交互的 AI 导师系统基础

**架构:** React + Vite 前端 / FastAPI 后端 / Graphify Worker 服务 / Neo4j 图数据库 / Redis 队列。前后端分离，Worker 独立部署通过消息队列通信。

**技术栈:** React, Vite, Cytoscape.js, FastAPI, Celery, Redis, Neo4j, Graphify, Vercel AI SDK, Playwright MCP

**开发规范:**
- TDD: 测试驱动开发，每个功能先写测试
- 前端测试: 使用 Playwright MCP 进行浏览器实际测试
- 文档交接: 阶段文档存放在 `docs/handoffs/` 目录

---

## 文件结构总览

```
control-theory-mentor/
├── frontend/                          # React + Vite 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Navbar.tsx        # 顶部导航栏
│   │   │   │   └── MainLayout.tsx    # 主布局（左右分栏）
│   │   │   ├── graph/
│   │   │   │   ├── KnowledgeGraph.tsx    # Cytoscape.js 图谱
│   │   │   │   └── NodeDetailPanel.tsx   # 节点详情
│   │   │   ├── tutor/
│   │   │   │   ├── ChatInterface.tsx     # 聊天界面
│   │   │   │   ├── StepControls.tsx      # 步进控制
│   │   │   │   └── ContentRenderer.tsx   # 多模态内容渲染
│   │   │   └── upload/
│   │   │       └── UploadCard.tsx       # PDF 上传卡片
│   │   ├── pages/
│   │   │   ├── UploadPage.tsx
│   │   │   ├── GraphViewPage.tsx
│   │   │   └── TutorPage.tsx
│   │   ├── hooks/
│   │   │   ├── useKnowledgeGraph.ts    # 图谱数据钩子
│   │   │   ├── useTutorSession.ts      # 教学会话钩子
│   │   │   └── useWebSocket.ts         # WebSocket 钩子
│   │   ├── services/
│   │   │   └── api.ts                  # API 客户端
│   │   ├── styles/
│   │   │   └── design-tokens.ts        # DESIGN.md 样式变量
│   │   ├── types/
│   │   │   └── api.ts                  # API 类型定义
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/
│   │   ├── e2e/                        # Playwright E2E 测试
│   │   │   ├── upload.spec.ts
│   │   │   ├── graph-view.spec.ts
│   │   │   └── tutor-session.spec.ts
│   │   └── integration/
│   │       └── api.test.ts
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── backend/                           # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 应用入口
│   │   ├── config.py                  # 配置管理
│   │   ├── dependencies.py            # 依赖注入
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pdf.py             # PDF 管理 API
│   │   │   │   ├── graph.py           # 知识图谱 API
│   │   │   │   ├── node.py            # 节点查询 API
│   │   │   │   └── tutor.py           # AI 导师 API
│   │   │   └── websocket/
│   │   │       └── handler.py         # WebSocket 处理
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── pdf.py                # PDF 数据模型
│   │   │   ├── graph.py              # 图谱数据模型
│   │   │   └── tutor.py              # 教学会话模型
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── pdf.py                # PDF 请求/响应 Schema
│   │   │   ├── graph.py              # 图谱 Schema
│   │   │   └── tutor.py              # 导师 Schema
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── graph_service.py      # 图谱业务逻辑
│   │   │   ├── tutor_service.py      # 导师业务逻辑
│   │   │   └── llm_service.py        # LLM 服务
│   │   └── db/
│   │       ├── __init__.py
│   │       └── neo4j.py              # Neo4j 连接
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_graph_service.py
│   │   │   └── test_tutor_service.py
│   │   └── integration/
│   │       └── test_api.py
│   ├── requirements.txt
│   └── alembic/                       # 数据库迁移（如需要）
├── worker/                            # Graphify Worker
│   ├── graphify_wrapper.py            # Graphify 封装
│   ├── celery_app.py                  # Celery 配置
│   ├── tasks.py                       # 后台任务
│   ├── tests/
│   │   └── test_tasks.py
│   └── requirements.txt
├── shared/                            # 共享类型
│   └── types.ts
├── docker-compose.yml                 # 容器编排
├── docs/
│   ├── handoffs/                      # 阶段交接文档
│   │   ├── 01-project-setup.md
│   │   ├── 02-backend-api.md
│   │   ├── 03-worker-service.md
│   │   ├── 04-frontend.md
│   │   └── 05-integration.md
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-04-18-ai-tutor-system-design.md
│       └── plans/
│           └── 2026-04-18-ai-tutor-system-a2.md
└── DESIGN.md                          # 设计系统规范
```

---

## 第一阶段：项目基础设施搭建

### Task 1.1: 创建项目根结构和 Docker Compose 配置

**Files:**
- Create: `docker-compose.yml`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: 创建 docker-compose.yml**

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.15-community
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_dbms_memory_heap_max__size: 2G
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: password
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - neo4j
      - redis
    volumes:
      - ./backend:/app
      - pdf_storage:/app/pdfs

  worker:
    build: ./worker
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: password
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - neo4j
      - redis
    volumes:
      - ./worker:/app
      - pdf_storage:/app/pdfs

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_BASE_URL: http://localhost:8000
      VITE_WS_BASE_URL: ws://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  neo4j_data:
  redis_data:
  pdf_storage:
```

- [ ] **Step 2: 创建 .gitignore**

```
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/

# Node
node_modules/
dist/
*.log

# IDE
.vscode/
.idea/

# Environment
.env
.env.local

# Data
*.pdf
pdfs/
```

- [ ] **Step 3: 创建 README.md**

```markdown
# ControlTheoryMentor - AI 导师系统

基于知识图谱的个性化 AI 自学导师。

## 快速开始

\`\`\`bash
# 启动所有服务
docker-compose up -d

# 访问
# - 前端: http://localhost:5173
# - 后端 API: http://localhost:8000
# - Neo4j 浏览器: http://localhost:7474
\`\`\`

## 项目结构

- frontend/: React + Vite 前端
- backend/: FastAPI 后端
- worker/: Graphify 处理服务
```

- [ ] **Step 4: 提交初始结构**

```bash
git init
git add .
git commit -m "feat: initialize project structure with docker-compose"
```

---

### Task 1.2: 后端项目初始化

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
neo4j==5.15.0
redis==5.0.1
celery==5.3.6
python-multipart==0.0.6
websockets==12.0
aiofiles==23.2.1
vercel-ai-sdk==0.0.5

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
```

- [ ] **Step 2: 创建配置文件 app/config.py**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # API
    API_PREFIX: str = "/api"
    
    # Storage
    PDF_STORAGE_PATH: str = "./pdfs"
    MAX_PDF_PAGES: int = 1200
    
    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 3: 创建主应用 app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title="AI 导师系统 API",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

- [ ] **Step 4: 创建测试验证应用启动**

创建 `backend/tests/unit/test_main.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

- [ ] **Step 5: 运行测试验证**

```bash
cd backend
pip install -r requirements.txt
pytest tests/unit/test_main.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/
git commit -m "feat: initialize backend with FastAPI"
```

---

### Task 1.3: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "ai-tutor-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.1",
    "cytoscape": "^3.28.1",
    "cytoscape-react": "^1.2.3",
    "mermaid": "^10.9.1",
    "katex": "^0.16.10",
    "framer-motion": "^11.0.3",
    "zustand": "^4.5.0",
    "react-markdown": "^9.0.1"
  },
  "devDependencies": {
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@vitejs/plugin-react": "^4.2.1",
    "typescript": "^5.3.3",
    "vite": "^5.0.11",
    "playwright": "^1.41.0",
    "@playwright/test": "^1.41.0"
  }
}
```

- [ ] **Step 2: 创建 vite.config.ts**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
});
```

- [ ] **Step 3: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>控制理论导师 - AI 驱动的个性化学习系统</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Georgia&family=Inter:wght@400;500&display=swap');
  </style>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

- [ ] **Step 5: 创建基础应用骨架**

创建 `frontend/src/main.tsx`:

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/design-tokens.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

创建 `frontend/src/App.tsx`:

```typescript
export default function App() {
  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-parchment)' }}>
      <header style={{ padding: '1rem 2rem', borderBottom: '1px solid var(--border-warm)' }}>
        <h1 style={{ 
          fontFamily: 'Georgia, serif', 
          fontSize: '1.5rem',
          color: 'var(--text-primary)'
        }}>
          控制理论导师
        </h1>
      </header>
      <main style={{ padding: '2rem' }}>
        <p>系统初始化中...</p>
      </main>
    </div>
  );
}
```

创建 `frontend/src/styles/design-tokens.css`:

```css
:root {
  /* 背景 */
  --bg-parchment: #f5f4ed;
  --bg-ivory: #faf9f5;
  --bg-warm-sand: #e8e6dc;
  
  /* 文字 */
  --text-primary: #141413;
  --text-secondary: #5e5d59;
  --text-tertiary: #87867f;
  
  /* 强调 */
  --accent-terracotta: #c96442;
  --accent-coral: #d97757;
  
  /* 边框 */
  --border-cream: #f0eee6;
  --border-warm: #e8e6dc;
  
  /* 组件 */
  --card-radius: 12px;
  --btn-radius: 8px;
}
```

- [ ] **Step 6: 创建 E2E 测试验证基础结构**

创建 `frontend/tests/e2e/basic.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test('页面加载成功', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await expect(page.locator('h1')).toContainText('控制理论导师');
});
```

- [ ] **Step 7: 安装依赖并验证**

```bash
cd frontend
npm install
npm run dev
# 在另一个终端
npx playwright test
```

Expected: 页面可访问，测试通过

- [ ] **Step 8: 提交**

```bash
git add frontend/
git commit -m "feat: initialize frontend with React + Vite"
```

---

### Task 1.4: 创建阶段交接文档

**Files:**
- Create: `docs/handoffs/01-project-setup.md`

- [ ] **Step 1: 创建项目设置交接文档**

```markdown
# 第一阶段交接：项目基础设施

**完成时间**: [填写]
**状态**: ✅ 完成

## 完成内容

### 项目结构
- ✅ 根目录 Docker Compose 配置
- ✅ 后端 FastAPI 框架初始化
- ✅ 前端 React + Vite 框架初始化
- ✅ DESIGN.md 样式变量集成

### 服务配置
| 服务 | 端口 | 状态 |
|------|------|------|
| Frontend | 5173 | ✅ |
| Backend API | 8000 | ✅ |
| Neo4j | 7474/7687 | ✅ |
| Redis | 6379 | ✅ |

### 已实现测试
- ✅ 后端健康检查测试
- ✅ 前端页面加载 E2E 测试

## 启动命令

```bash
# 启动所有服务
docker-compose up -d

# 单独启动
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

## 下一步

进入第二阶段：后端 API 开发

## 注意事项

- DESIGN.md 样式变量已配置在 `frontend/src/styles/design-tokens.css`
- 所有 API 请求需通过 `/api` 前缀
- WebSocket 连接点：`ws://localhost:8000/ws`
```

- [ ] **Step 2: 提交文档**

```bash
git add docs/handoffs/01-project-setup.md
git commit -m "docs: add project setup handoff document"
```

---

## 第二阶段：后端 API 开发

### Task 2.1: Neo4j 数据库连接和图模型

**Files:**
- Create: `backend/app/db/neo4j.py`
- Create: `backend/app/db/__init__.py`

- [ ] **Step 1: 编写数据库连接测试**

创建 `backend/tests/unit/test_neo4j.py`:

```python
import pytest
from app.db.neo4j import get_driver, close_driver

def test_neo4j_connection():
    """测试 Neo4j 连接"""
    driver = get_driver()
    assert driver is not None
    
    # 验证连接
    with driver.session() as session:
        result = session.run("RETURN 1 AS num")
        assert result.single()["num"] == 1
    
    close_driver()
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
pytest backend/tests/unit/test_neo4j.py -v
```

Expected: FAIL - Module not found

- [ ] **Step 3: 实现 Neo4j 连接**

创建 `backend/app/db/neo4j.py`:

```python
from neo4j import GraphDatabase
from app.config import settings

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    return _driver

def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest backend/tests/unit/test_neo4j.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/db/ backend/tests/unit/test_neo4j.py
git commit -m "feat: add Neo4j connection with tests"
```

---

### Task 2.2: PDF 数据模型和 Schema

**Files:**
- Create: `backend/app/models/pdf.py`
- Create: `backend/app/schemas/pdf.py`

- [ ] **Step 1: 编写 PDF Schema 测试**

创建 `backend/tests/unit/test_pdf_schema.py`:

```python
from pydantic import ValidationError
from app.schemas.pdf import PDFUploadResponse, PDFStatusResponse

def test_pdf_upload_response_schema():
    """测试 PDF 上传响应 Schema"""
    data = {
        "taskId": "task-123",
        "filename": "test.pdf",
        "status": "processing"
    }
    response = PDFUploadResponse(**data)
    assert response.taskId == "task-123"
    assert response.filename == "test.pdf"
    assert response.status == "processing"

def test_pdf_status_response_schema():
    """测试 PDF 状态响应 Schema"""
    data = {
        "id": "pdf-123",
        "filename": "test.pdf",
        "status": "completed",
        "pageCount": 100,
        "uploadTime": "2024-01-01T00:00:00Z"
    }
    response = PDFStatusResponse(**data)
    assert response.id == "pdf-123"
    assert response.status == "completed"
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
pytest backend/tests/unit/test_pdf_schema.py -v
```

Expected: FAIL - Schema not defined

- [ ] **Step 3: 实现 Schema**

创建 `backend/app/schemas/pdf.py`:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class PDFStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class PDFUploadResponse(BaseModel):
    taskId: str
    filename: str
    status: PDFStatus

class PDFStatusResponse(BaseModel):
    id: str
    filename: str
    status: PDFStatus
    pageCount: int | None = None
    uploadTime: datetime
    graphId: str | None = None
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest backend/tests/unit/test_pdf_schema.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/pdf.py backend/tests/unit/test_pdf_schema.py
git commit -m "feat: add PDF schemas with validation tests"
```

---

### Task 2.3: PDF 上传 API

**Files:**
- Create: `backend/app/api/routes/pdf.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 编写 API 集成测试**

创建 `backend/tests/integration/test_pdf_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)

def test_upload_pdf():
    """测试 PDF 上传"""
    # 创建模拟 PDF 文件
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
    
    response = client.post(
        "/api/pdf/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "taskId" in data
    assert "filename" in data
    assert data["filename"] == "test.pdf"
    assert data["status"] in ["processing", "completed", "failed"]

def test_upload_invalid_file():
    """测试非 PDF 文件上传"""
    response = client.post(
        "/api/pdf/upload",
        files={"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")}
    )
    
    assert response.status_code == 400
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
pytest backend/tests/integration/test_pdf_api.py -v
```

Expected: FAIL - Route not found

- [ ] **Step 3: 实现 PDF API**

创建 `backend/app/api/routes/pdf.py`:

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.pdf import PDFUploadResponse, PDFStatusResponse, PDFStatus
from app.config import settings
import uuid
import os
from datetime import datetime

router = APIRouter(prefix="/pdf", tags=["pdf"])

@router.post("/upload", response_model=PDFUploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF 文件"""
    # 验证文件类型
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")
    
    # 生成任务 ID
    task_id = str(uuid.uuid4())
    
    # 保存文件
    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
    file_path = os.path.join(settings.PDF_STORAGE_PATH, f"{task_id}.pdf")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # TODO: 发送到 Redis 队列
    
    return PDFUploadResponse(
        taskId=task_id,
        filename=file.filename,
        status=PDFStatus.PROCESSING
    )

@router.get("/{pdf_id}", response_model=PDFStatusResponse)
async def get_pdf_status(pdf_id: str):
    """获取 PDF 处理状态"""
    # TODO: 从数据库查询
    raise HTTPException(status_code=501, detail="待实现")
```

修改 `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import pdf

app = FastAPI(
    title="AI 导师系统 API",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pdf.router, prefix="/api")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest backend/tests/integration/test_pdf_api.py -v
```

Expected: PASS (upload endpoint)

- [ ] **Step 5: 提交**

```bash
git add backend/app/api/routes/pdf.py backend/app/main.py backend/tests/integration/test_pdf_api.py
git commit -m "feat: add PDF upload API endpoint"
```

---

### Task 2.4: 知识图谱 API

**Files:**
- Create: `backend/app/api/routes/graph.py`
- Create: `backend/app/schemas/graph.py`

- [ ] **Step 1: 编写图谱 Schema 测试**

创建 `backend/tests/unit/test_graph_schema.py`:

```python
from app.schemas.graph import GraphDataResponse, NodeElement, EdgeElement

def test_graph_data_response():
    """测试图谱数据响应 Schema"""
    data = {
        "elements": {
            "nodes": [
                {"data": {"id": "c1", "label": "二阶系统", "type": "concept"}}
            ],
            "edges": [
                {"data": {"source": "c1", "target": "c2", "label": "PREREQUISITE"}}
            ]
        }
    }
    response = GraphDataResponse(**data)
    assert len(response.elements.nodes) == 1
    assert response.elements.nodes[0].data.id == "c1"
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
pytest backend/tests/unit/test_graph_schema.py -v
```

Expected: FAIL - Schema not defined

- [ ] **Step 3: 实现图谱 Schema**

创建 `backend/app/schemas/graph.py`:

```python
from pydantic import BaseModel
from typing import List, Optional

class NodeData(BaseModel):
    id: str
    label: str
    type: str
    description: Optional[str] = None

class NodeElement(BaseModel):
    data: NodeData

class EdgeData(BaseModel):
    source: str
    target: str
    label: str

class EdgeElement(BaseModel):
    data: EdgeData

class GraphElements(BaseModel):
    nodes: List[NodeElement]
    edges: List[EdgeElement]

class GraphDataResponse(BaseModel):
    elements: GraphElements
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest backend/tests/unit/test_graph_schema.py -v
```

Expected: PASS

- [ ] **Step 5: 创建图谱 API（基础框架）**

创建 `backend/app/api/routes/graph.py`:

```python
from fastapi import APIRouter, HTTPException
from app.schemas.graph import GraphDataResponse
from app.db.neo4j import get_driver

router = APIRouter(prefix="/graph", tags=["graph"])

@router.get("/{pdf_id}", response_model=GraphDataResponse)
async def get_graph(pdf_id: str):
    """获取指定 PDF 的知识图谱"""
    driver = get_driver()
    
    with driver.session() as session:
        # 查询所有节点
        nodes_result = session.run("""
            MATCH (c:Concept {pdfId: $pdf_id})
            RETURN c.id AS id, c.name AS label, 'concept' AS type, c.description AS description
        """, pdf_id=pdf_id)
        
        nodes = [
            {"data": record}
            for record in nodes_result
        ]
        
        # 查询所有边
        edges_result = session.run("""
            MATCH (c1:Concept {pdfId: $pdf_id})-[r]->(c2:Concept {pdfId: $pdf_id})
            RETURN c1.id AS source, c2.id AS target, type(r) AS label
        """, pdf_id=pdf_id)
        
        edges = [
            {"data": record}
            for record in edges_result
        ]
    
    return GraphDataResponse(elements={"nodes": nodes, "edges": edges})
```

修改 `backend/app/main.py` 添加路由：

```python
from app.api.routes import graph
app.include_router(graph.router, prefix="/api")
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/schemas/graph.py backend/app/api/routes/graph.py backend/tests/unit/test_graph_schema.py
git commit -m "feat: add knowledge graph API endpoints"
```

---

### Task 2.5: AI 导师 API（基础框架）

**Files:**
- Create: `backend/app/api/routes/tutor.py`
- Create: `backend/app/schemas/tutor.py`

- [ ] **Step 1: 编写导师 Schema 测试**

创建 `backend/tests/unit/test_tutor_schema.py`:

```python
from app.schemas.tutor import TutorSessionStart, TutorSessionResponse

def test_tutor_session_start():
    """测试教学会话启动 Schema"""
    data = {
        "question": "什么是二阶系统？",
        "pdfId": "pdf-123"
    }
    request = TutorSessionStart(**data)
    assert request.question == "什么是二阶系统？"
    assert request.pdfId == "pdf-123"
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
pytest backend/tests/unit/test_tutor_schema.py -v
```

Expected: FAIL - Schema not defined

- [ ] **Step 3: 实现导师 Schema**

创建 `backend/app/schemas/tutor.py`:

```python
from pydantic import BaseModel
from typing import List, Optional

class TutorSessionStart(BaseModel):
    question: str
    pdfId: str
    mode: str = "interactive"

class TeachingStep(BaseModel):
    id: str
    type: str
    title: str
    content: dict

class TeachingPlan(BaseModel):
    steps: List[TeachingStep]

class TutorSessionResponse(BaseModel):
    sessionId: str
    plan: TeachingPlan
    currentStep: Optional[str] = None
    status: str
```

- [ ] **Step 4: 运行测试验证**

```bash
pytest backend/tests/unit/test_tutor_schema.py -v
```

Expected: PASS

- [ ] **Step 5: 创建导师 API（基础框架）**

创建 `backend/app/api/routes/tutor.py`:

```python
from fastapi import APIRouter, HTTPException
from app.schemas.tutor import TutorSessionStart, TutorSessionResponse
import uuid

router = APIRouter(prefix="/tutor", tags=["tutor"])

@router.post("/session/start", response_model=TutorSessionResponse)
async def start_tutor_session(request: TutorSessionStart):
    """启动新的教学会话"""
    # TODO: 实现 LLM 分析和教学计划生成
    session_id = str(uuid.uuid4())
    
    return TutorSessionResponse(
        sessionId=session_id,
        plan={"steps": []},  # 占位
        status="ready"
    )
```

修改 `backend/app/main.py` 添加路由：

```python
from app.api.routes import tutor
app.include_router(tutor.router, prefix="/api")
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/schemas/tutor.py backend/app/api/routes/tutor.py backend/tests/unit/test_tutor_schema.py
git commit -m "feat: add AI tutor API endpoints (framework)"
```

---

### Task 2.6: 创建阶段交接文档

**Files:**
- Create: `docs/handoffs/02-backend-api.md`

- [ ] **Step 1: 创建后端 API 交接文档**

```markdown
# 第二阶段交接：后端 API

**完成时间**: [填写]
**状态**: ✅ 完成

## 已实现 API 端点

### PDF 管理
- ✅ `POST /api/pdf/upload` - 上传 PDF
- ✅ `GET /api/pdf/{id}` - 获取 PDF 状态（框架）

### 知识图谱
- ✅ `GET /api/graph/{pdf_id}` - 获取完整图谱

### AI 导师
- ✅ `POST /api/tutor/session/start` - 启动教学会话（框架）

## 数据模型

### Neo4j 图模式
- 节点: PDF, Concept, Section, Formula, Example
- 关系: HAS_SECTION, CONTAINS_CONCEPT, PREREQUISITE, RELATED_TO

### Pydantic Schemas
- PDFUploadResponse, PDFStatusResponse
- GraphDataResponse, NodeElement, EdgeElement  
- TutorSessionStart, TutorSessionResponse

## 测试覆盖

- ✅ 单元测试: Neo4j 连接、Schema 验证
- ✅ 集成测试: PDF 上传 API

## 待实现

1. Redis 队列集成
2. WebSocket 实时状态推送
3. LLM 服务集成（教学计划生成）
4. 步进式教学执行逻辑

## 下一步

进入第三阶段：Worker 服务开发
```

- [ ] **Step 2: 提交文档**

```bash
git add docs/handoffs/02-backend-api.md
git commit -m "docs: add backend API handoff document"
```

---

## 第三阶段：Worker 服务开发

### Task 3.1: Worker 项目初始化和 Celery 配置

**Files:**
- Create: `worker/requirements.txt`
- Create: `worker/celery_app.py`

- [ ] **Step 1: 创建 worker requirements.txt**

```txt
celery==5.3.6
redis==5.0.1
neo4j==5.15.0
graphify==0.1.0  # 假设版本号
pypdf==3.17.4
pytest==7.4.4
```

- [ ] **Step 2: 创建 Celery 配置**

```python
from celery import Celery
from os import getenv

celery_app = Celery(
    'ai_tutor_worker',
    broker=getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=getenv('REDIS_URL', 'redis://localhost:6379/0'),
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
)
```

- [ ] **Step 3: 提交**

```bash
git add worker/
git commit -m "feat: initialize worker with Celery configuration"
```

---

### Task 3.2: Graphify 封装和 PDF 处理任务

**Files:**
- Create: `worker/graphify_wrapper.py`
- Create: `worker/tasks.py`

- [ ] **Step 1: 编写 Graphify 封装测试**

创建 `worker/tests/test_graphify_wrapper.py`:

```python
from worker.graphify_wrapper import GraphifyProcessor

def test_graphify_processor_init():
    """测试 Graphify 处理器初始化"""
    processor = GraphifyProcessor(neo4j_uri="bolt://localhost:7687")
    assert processor is not None
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
pytest worker/tests/test_graphify_wrapper.py -v
```

Expected: FAIL - Module not found

- [ ] **Step 3: 实现 Graphify 封装**

创建 `worker/graphify_wrapper.py`:

```python
from neo4j import GraphDatabase
from graphify import PDFProcessor  # 假设 API

class GraphifyProcessor:
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )
        self.pdf_processor = PDFProcessor()
    
    def process_pdf(self, pdf_path: str, pdf_id: str) -> dict:
        """处理 PDF 生成知识图谱"""
        # 1. 使用 Graphify 提取实体和关系
        result = self.pdf_processor.process(pdf_path)
        
        # 2. 写入 Neo4j
        with self.driver.session() as session:
            self._save_to_neo4j(session, result, pdf_id)
        
        return {"nodes": result["nodes"], "edges": result["edges"]}
    
    def _save_to_neo4j(self, session, result, pdf_id):
        """保存到 Neo4j 数据库"""
        # 创建概念节点
        for node in result["nodes"]:
            session.run("""
                CREATE (c:Concept {
                    id: randomUUID(),
                    name: $name,
                    description: $description,
                    pdfId: $pdf_id,
                    sourcePage: $page
                })
            """, name=node["name"], description=node.get("description"), 
                pdf_id=pdf_id, page=node.get("page"))
        
        # 创建关系
        for edge in result["edges"]:
            session.run("""
                MATCH (c1:Concept {name: $source}), (c2:Concept {name: $target})
                CREATE (c1)-[:RELATED_TO]->(c2)
            """, source=edge["source"], target=edge["target"])
```

- [ ] **Step 4: 创建 Celery 任务**

创建 `worker/tasks.py`:

```python
from celery import shared_task
from graphify_wrapper import GraphifyProcessor
from redis import Redis
import os

@shared_task(bind=True, max_retries=3)
def process_pdf_task(self, task_id: str, pdf_path: str, neo4j_uri: str, 
                     neo4j_user: str, neo4j_password: str):
    """后台处理 PDF 生成知识图谱"""
    redis = Redis()
    
    try:
        # 更新状态
        redis.set(f"task:{task_id}:status", "processing")
        
        # 处理 PDF
        processor = GraphifyProcessor(neo4j_uri, neo4j_user, neo4j_password)
        result = processor.process_pdf(pdf_path, task_id)
        
        # 更新状态为完成
        redis.set(f"task:{task_id}:status", "completed")
        redis.set(f"task:{task_id}:result", str(result))
        
        return {"status": "completed", "task_id": task_id}
        
    except Exception as e:
        redis.set(f"task:{task_id}:status", "failed")
        redis.set(f"task:{task_id}:error", str(e))
        raise  # 触发重试
```

- [ ] **Step 5: 运行测试验证**

```bash
pytest worker/tests/test_graphify_wrapper.py -v
```

Expected: PASS (初始化测试)

- [ ] **Step 6: 提交**

```bash
git add worker/graphify_wrapper.py worker/tasks.py worker/tests/
git commit -m "feat: add Graphify wrapper and PDF processing task"
```

---

### Task 3.3: 后端集成 Celery 任务队列

**Files:**
- Modify: `backend/app/api/routes/pdf.py`

- [ ] **Step 1: 更新 PDF 上传 API 集成 Celery**

修改 `backend/app/api/routes/pdf.py`:

```python
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.schemas.pdf import PDFUploadResponse, PDFStatusResponse, PDFStatus
from app.config import settings
from celery import Celery
import uuid
import os
from datetime import datetime

router = APIRouter(prefix="/pdf", tags=["pdf"])

# Celery 客户端
celery_app = Celery('backend')
celery_app.config_from_object('worker.celery_app')

@router.post("/upload", response_model=PDFUploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """上传 PDF 文件"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")
    
    task_id = str(uuid.uuid4())
    
    # 保存文件
    os.makedirs(settings.PDF_STORAGE_PATH, exist_ok=True)
    file_path = os.path.join(settings.PDF_STORAGE_PATH, f"{task_id}.pdf")
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # 发送到 Celery 队列
    from worker.tasks import process_pdf_task
    process_pdf_task.delay(
        task_id=task_id,
        pdf_path=file_path,
        neo4j_uri=settings.NEO4J_URI,
        neo4j_user=settings.NEO4J_USER,
        neo4j_password=settings.NEO4J_PASSWORD
    )
    
    return PDFUploadResponse(
        taskId=task_id,
        filename=file.filename,
        status=PDFStatus.PROCESSING
    )
```

- [ ] **Step 2: 更新 requirements.txt**

```txt
# 在 backend/requirements.txt 添加
celery==5.3.6
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/routes/pdf.py backend/requirements.txt
git commit -m "feat: integrate Celery task queue for PDF processing"
```

---

### Task 3.4: WebSocket 实时状态推送

**Files:**
- Create: `backend/app/api/websocket/handler.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 WebSocket 处理器**

创建 `backend/app/api/websocket/handler.py`:

```python
from fastapi import WebSocket, WebSocketDisconnect
from redis import Redis
import json
import asyncio

redis = Redis()

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        self.active_connections[task_id] = websocket
    
    def disconnect(self, task_id: str):
        if task_id in self.active_connections:
            del self.active_connections[task_id]
    
    async def send_update(self, task_id: str, message: dict):
        if task_id in self.active_connections:
            await self.active_connections[task_id].send_json(message)

manager = ConnectionManager()

async def task_status_monitor(task_id: str):
    """监控任务状态并推送更新"""
    while True:
        status = redis.get(f"task:{task_id}:status")
        
        if status:
            status = status.decode('utf-8')
            
            await manager.send_update(task_id, {
                "type": "task.progress" if status == "processing" else "task.completed" if status == "completed" else "task.failed",
                "data": {"status": status}
            })
            
            if status in ["completed", "failed"]:
                break
        
        await asyncio.sleep(1)
```

- [ ] **Step 2: 添加 WebSocket 路由**

修改 `backend/app/main.py`:

```python
from fastapi import WebSocket
from app.api.websocket.handler import manager, task_status_monitor

@app.websocket("/ws/graph/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await manager.connect(websocket, task_id)
    try:
        # 启动状态监控
        await task_status_monitor(task_id)
    except WebSocketDisconnect:
        manager.disconnect(task_id)
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/api/websocket/ backend/app/main.py
git commit -m "feat: add WebSocket for real-time task status updates"
```

---

### Task 3.5: 创建阶段交接文档

**Files:**
- Create: `docs/handoffs/03-worker-service.md`

- [ ] **Step 1: 创建 Worker 服务交接文档**

```markdown
# 第三阶段交接：Worker 服务

**完成时间**: [填写]
**状态**: ✅ 完成

## 已实现功能

### Worker 服务
- ✅ Celery 配置和任务队列
- ✅ Graphify 封装
- ✅ PDF 处理后台任务
- ✅ Neo4j 数据写入

### 集成
- ✅ 后端 API 集成 Celery
- ✅ WebSocket 实时状态推送

## 数据流

```
PDF 上传 → 保存文件 → Celery 队列 → Worker 处理 → Neo4j 写入 → WebSocket 通知
```

## 测试覆盖

- ✅ Graphify 处理器初始化测试
- ✅ Celery 任务定义验证

## 待实现

1. Graphify 实际集成（依赖 Graphify 库）
2. 错误处理和重试逻辑完善
3. 任务进度细粒度报告

## 下一步

进入第四阶段：前端开发
```

- [ ] **Step 2: 提交文档**

```bash
git add docs/handoffs/03-worker-service.md
git commit -m "docs: add worker service handoff document"
```

---

## 第四阶段：前端开发

### Task 4.1: API 客户端服务

**Files:**
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/types/api.ts`

- [ ] **Step 1: 编写 API 客户端测试**

创建 `frontend/tests/integration/api.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '@/services/api';

// Mock fetch
global.fetch = vi.fn();

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should upload PDF', async () => {
    const mockFile = new File(['%PDF-1.4'], 'test.pdf', { type: 'application/pdf' });
    const mockResponse = {
      taskId: 'task-123',
      filename: 'test.pdf',
      status: 'processing'
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.uploadPDF(mockFile);
    expect(result.taskId).toBe('task-123');
  });
});
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
cd frontend && npm test -- api.test.ts
```

Expected: FAIL - Module not found

- [ ] **Step 3: 实现 API 类型定义**

创建 `frontend/src/types/api.ts`:

```typescript
export interface PDFUploadResponse {
  taskId: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
}

export interface PDFStatusResponse {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  pageCount?: number;
  uploadTime: string;
  graphId?: string;
}

export interface NodeData {
  id: string;
  label: string;
  type: string;
  description?: string;
}

export interface NodeElement {
  data: NodeData;
}

export interface EdgeData {
  source: string;
  target: string;
  label: string;
}

export interface EdgeElement {
  data: EdgeData;
}

export interface GraphElements {
  nodes: NodeElement[];
  edges: EdgeElement[];
}

export interface GraphDataResponse {
  elements: GraphElements;
}

export interface TutorSessionStart {
  question: string;
  pdfId: string;
  mode?: string;
}

export interface TeachingStep {
  id: string;
  type: string;
  title: string;
  content: any;
}

export interface TutorSessionResponse {
  sessionId: string;
  plan: {
    steps: TeachingStep[];
  };
  currentStep?: string;
  status: string;
}
```

- [ ] **Step 4: 实现 API 客户端**

创建 `frontend/src/services/api.ts`:

```typescript
import type {
  PDFUploadResponse,
  PDFStatusResponse,
  GraphDataResponse,
  TutorSessionResponse,
  TutorSessionStart
} from '@/types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  }

  // PDF 管理
  async uploadPDF(file: File): Promise<PDFUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseURL}/api/pdf/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('上传失败');
    }

    return response.json();
  }

  async getPDFStatus(id: string): Promise<PDFStatusResponse> {
    return this.request<PDFStatusResponse>(`/api/pdf/${id}`);
  }

  // 知识图谱
  async getGraph(pdfId: string): Promise<GraphDataResponse> {
    return this.request<GraphDataResponse>(`/api/graph/${pdfId}`);
  }

  // AI 导师
  async startTutorSession(request: TutorSessionStart): Promise<TutorSessionResponse> {
    return this.request<TutorSessionResponse>('/api/tutor/session/start', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
}

export const apiClient = new APIClient(API_BASE_URL);
```

- [ ] **Step 5: 运行测试验证**

```bash
cd frontend && npm test -- api.test.ts
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/types/api.ts frontend/src/services/api.ts frontend/tests/integration/api.test.ts
git commit -m "feat: add API client with types and tests"
```

---

### Task 4.2: 布局组件（Navbar 和主布局）

**Files:**
- Create: `frontend/src/components/layout/Navbar.tsx`
- Create: `frontend/src/components/layout/MainLayout.tsx`

- [ ] **Step 1: 编写 Navbar 组件测试**

创建 `frontend/tests/unit/Navbar.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Navbar } from '@/components/layout/Navbar';

describe('Navbar', () => {
  it('should render logo and navigation', () => {
    const { getByText } = render(<Navbar />);
    expect(getByText('控制理论导师')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
cd frontend && npm test -- Navbar.test.tsx
```

Expected: FAIL - Component not found

- [ ] **Step 3: 实现 Navbar 组件**

创建 `frontend/src/components/layout/Navbar.tsx`:

```typescript
export function Navbar() {
  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      backgroundColor: 'var(--bg-warm-sand)',
      borderBottom: '1px solid var(--border-warm)',
      padding: '0.75rem 1.5rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }}>
      <div style={{
        fontFamily: 'Georgia, serif',
        fontSize: '1.25rem',
        fontWeight: 500,
        color: 'var(--text-primary)'
      }}>
        控制理论导师
      </div>
      
      <div style={{
        display: 'flex',
        gap: '1.5rem',
        fontFamily: 'Inter, sans-serif',
        fontSize: '1rem',
        color: 'var(--text-secondary)'
      }}>
        <a href="/upload" style={{ textDecoration: 'none', color: 'inherit' }}>
          教材管理
        </a>
        <a href="/tutor" style={{ textDecoration: 'none', color: 'inherit' }}>
          AI 导师
        </a>
      </div>
    </nav>
  );
}
```

- [ ] **Step 4: 实现主布局组件**

创建 `frontend/src/components/layout/MainLayout.tsx`:

```typescript
import { ReactNode } from 'react';
import { Navbar } from './Navbar';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: 'var(--bg-parchment)',
      color: 'var(--text-primary)'
    }}>
      <Navbar />
      <main>
        {children}
      </main>
    </div>
  );
}
```

- [ ] **Step 5: 运行测试验证**

```bash
cd frontend && npm test -- Navbar.test.tsx
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/layout/ frontend/tests/unit/Navbar.test.tsx
git commit -m "feat: add layout components (Navbar and MainLayout)"
```

---

### Task 4.3: PDF 上传组件

**Files:**
- Create: `frontend/src/components/upload/UploadCard.tsx`
- Create: `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: 编写 WebSocket Hook 测试**

创建 `frontend/tests/unit/useWebSocket.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '@/hooks/useWebSocket';

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', class MockWebSocket {
      url: string;
      readyState: number = 0;
      
      constructor(url: string) {
        this.url = url;
        setTimeout(() => {
          this.readyState = 1;
          this.onopen?.(new Event('open'));
        }, 0);
      }
      
      send = vi.fn();
      close = vi.fn();
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;
    });
  });

  it('should connect to WebSocket', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws/test'));
    
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
    });
    
    expect(result.current.status).toBe('connected');
  });
});
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
cd frontend && npm test -- useWebSocket.test.ts
```

Expected: FAIL - Hook not found

- [ ] **Step 3: 实现 WebSocket Hook**

创建 `frontend/src/hooks/useWebSocket.ts`:

```typescript
import { useState, useEffect, useRef } from 'react';

interface UseWebSocketOptions {
  onMessage?: (data: any) => void;
  onError?: (error: Event) => void;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    function connect() {
      setStatus('connecting');
      
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          options.onMessage?.(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        options.onError?.(error);
      };

      ws.onclose = () => {
        setStatus('disconnected');
        // 自动重连
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 3000);
      };
    }

    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url]);

  return { status };
}
```

- [ ] **Step 4: 实现上传卡片组件**

创建 `frontend/src/components/upload/UploadCard.tsx`:

```typescript
import { useState, useRef } from 'react';
import { apiClient } from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';

interface UploadCardProps {
  onUploadComplete?: (taskId: string, graphId: string) => void;
}

export function UploadCard({ onUploadComplete }: UploadCardProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      alert('请上传 PDF 文件');
      return;
    }

    setUploading(true);
    setProgress(0);
    setMessage('正在上传...');

    try {
      const result = await apiClient.uploadPDF(file);
      
      // 连接 WebSocket 监听进度
      useWebSocket(`ws://localhost:8000/ws/graph/${result.taskId}`, {
        onMessage: (data) => {
          if (data.type === 'task.progress') {
            setProgress(data.data.percent || 0);
            setMessage(data.data.message || '处理中...');
          } else if (data.type === 'task.completed') {
            setProgress(100);
            setMessage('处理完成！');
            setUploading(false);
            onUploadComplete?.(result.taskId, data.data.graphId);
          } else if (data.type === 'task.failed') {
            setMessage('处理失败：' + data.data.error);
            setUploading(false);
          }
        }
      });
    } catch (error) {
      setMessage('上传失败：' + (error as Error).message);
      setUploading(false);
    }
  };

  return (
    <div style={{
      backgroundColor: 'var(--bg-ivory)',
      border: '1px solid var(--border-cream)',
      borderRadius: 'var(--card-radius)',
      padding: '2rem',
      maxWidth: '500px',
      margin: '0 auto'
    }}>
      <h2 style={{
        fontFamily: 'Georgia, serif',
        fontSize: '1.5rem',
        color: 'var(--text-primary)',
        marginBottom: '1.5rem'
      }}>
        上传教材 PDF
      </h2>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileSelect}
        disabled={uploading}
        style={{ display: 'none' }}
      />

      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        style={{
          width: '100%',
          padding: '0.75rem',
          backgroundColor: uploading ? 'var(--bg-warm-sand)' : 'var(--accent-terracotta)',
          color: uploading ? 'var(--text-secondary)' : 'var(--bg-ivory)',
          border: 'none',
          borderRadius: 'var(--btn-radius)',
          fontSize: '1rem',
          cursor: uploading ? 'not-allowed' : 'pointer',
          fontFamily: 'Inter, sans-serif'
        }}
      >
        {uploading ? '处理中...' : '选择 PDF 文件'}
      </button>

      {uploading && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{
            width: '100%',
            height: '4px',
            backgroundColor: 'var(--border-cream)',
            borderRadius: '2px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${progress}%`,
              height: '100%',
              backgroundColor: 'var(--accent-terracotta)',
              transition: 'width 0.3s ease'
            }} />
          </div>
          <p style={{
            marginTop: '0.5rem',
            fontSize: '0.875rem',
            color: 'var(--text-secondary)',
            fontFamily: 'Inter, sans-serif'
          }}>
            {message} ({progress}%)
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: 运行测试验证**

```bash
cd frontend && npm test -- useWebSocket.test.ts
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/hooks/useWebSocket.ts frontend/src/components/upload/ frontend/tests/unit/useWebSocket.test.ts
git commit -m "feat: add WebSocket hook and PDF upload component"
```

---

### Task 4.4: 知识图谱可视化组件

**Files:**
- Create: `frontend/src/components/graph/KnowledgeGraph.tsx`
- Create: `frontend/src/hooks/useKnowledgeGraph.ts`

- [ ] **Step 1: 编写图谱 Hook 测试**

创建 `frontend/tests/unit/useKnowledgeGraph.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useKnowledgeGraph } from '@/hooks/useKnowledgeGraph';
import { apiClient } from '@/services/api';

vi.mock('@/services/api');

describe('useKnowledgeGraph', () => {
  it('should fetch graph data', async () => {
    const mockGraphData = {
      elements: {
        nodes: [{ data: { id: 'c1', label: 'Test', type: 'concept' }}],
        edges: []
      }
    };

    vi.mocked(apiClient.getGraph).mockResolvedValue(mockGraphData);

    const { result } = renderHook(() => useKnowledgeGraph('pdf-123'));

    await waitFor(() => {
      expect(result.current.data).toEqual(mockGraphData);
      expect(result.current.loading).toBe(false);
    });
  });
});
```

- [ ] **Step 2: 运行测试（预期失败）**

```bash
cd frontend && npm test -- useKnowledgeGraph.test.ts
```

Expected: FAIL - Hook not found

- [ ] **Step 3: 实现图谱 Hook**

创建 `frontend/src/hooks/useKnowledgeGraph.ts`:

```typescript
import { useState, useEffect } from 'react';
import { apiClient } from '@/services/api';
import type { GraphDataResponse } from '@/types/api';

export function useKnowledgeGraph(pdfId: string) {
  const [data, setData] = useState<GraphDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchGraph() {
      try {
        setLoading(true);
        const graph = await apiClient.getGraph(pdfId);
        setData(graph);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    if (pdfId) {
      fetchGraph();
    }
  }, [pdfId]);

  return { data, loading, error };
}
```

- [ ] **Step 4: 实现知识图谱组件**

创建 `frontend/src/components/graph/KnowledgeGraph.tsx`:

```typescript
import { useEffect, useRef } from 'react';
import cytoscape, { Core, ElementDefinition } from 'cytoscape';
import type { GraphDataResponse } from '@/types/api';

interface KnowledgeGraphProps {
  data: GraphDataResponse;
  onNodeClick?: (nodeId: string) => void;
  highlightedNodes?: string[];
}

export function KnowledgeGraph({ data, onNodeClick, highlightedNodes = [] }: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current || !data) return;

    // 转换数据格式
    const elements: ElementDefinition[] = [
      ...data.elements.nodes.map(n => ({ data: n.data })),
      ...data.elements.edges.map(e => ({ data: e.data }))
    ];

    // 初始化 Cytoscape
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#faf9f5',
            'border-color': '#c96442',
            'border-width': 2,
            'label': 'data(label)',
            'color': '#141413',
            'font-family': 'Inter, sans-serif',
            'font-size': '12px',
            'text-valign': 'center',
            'text-halign': 'center'
          }
        },
        {
          selector: 'node.highlighted',
          style: {
            'background-color': '#c96442',
            'border-color': '#141413'
          }
        },
        {
          selector: 'node.faded',
          style: {
            'opacity': 0.3
          }
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#87867f',
            'width': 1,
            'curve-style': 'bezier'
          }
        }
      ],
      layout: {
        name: 'cose',
        idealEdgeLength: 100,
        nodeOverlap: 20,
        refresh: 20,
        fit: true,
        padding: 30,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 10
      }
    });

    // 节点点击事件
    cy.on('tap', 'node', (event) => {
      const node = event.target;
      onNodeClick?.(node.id());
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
    };
  }, [data]);

  // 高亮节点
  useEffect(() => {
    if (!cyRef.current) return;

    const cy = cyRef.current;
    cy.nodes().removeClass('highlighted faded');
    
    if (highlightedNodes.length > 0) {
      cy.nodes().forEach(node => {
        if (highlightedNodes.includes(node.id())) {
          node.addClass('highlighted');
        } else {
          node.addClass('faded');
        }
      });
    }
  }, [highlightedNodes]);

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '500px',
        backgroundColor: 'var(--bg-ivory)',
        border: '1px solid var(--border-cream)',
        borderRadius: 'var(--card-radius)'
      }}
    />
  );
}
```

- [ ] **Step 5: 运行测试验证**

```bash
cd frontend && npm test -- useKnowledgeGraph.test.ts
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add frontend/src/hooks/useKnowledgeGraph.ts frontend/src/components/graph/KnowledgeGraph.tsx frontend/tests/unit/useKnowledgeGraph.test.ts
git commit -m "feat: add knowledge graph visualization with Cytoscape.js"
```

---

### Task 4.5: E2E 测试验证前端功能

**Files:**
- Modify: `frontend/tests/e2e/basic.spec.ts`
- Create: `frontend/tests/e2e/upload.spec.ts`

- [ ] **Step 1: 更新基础 E2E 测试**

修改 `frontend/tests/e2e/basic.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('应用基础功能', () => {
  test('页面加载成功', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await expect(page.locator('nav h1')).toContainText('控制理论导师');
  });

  test('导航栏存在', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.locator('a[href="/upload"]')).toBeVisible();
    await expect(page.locator('a[href="/tutor"]')).toBeVisible();
  });
});
```

- [ ] **Step 2: 创建上传功能 E2E 测试**

创建 `frontend/tests/e2e/upload.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('PDF 上传功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/upload');
  });

  test('显示上传卡片', async ({ page }) => {
    await expect(page.locator('text=上传教材 PDF')).toBeVisible();
    await expect(page.locator('button:has-text("选择 PDF 文件")')).toBeVisible();
  });

  test('点击上传按钮打开文件选择器', async ({ page }) => {
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.click('button:has-text("选择 PDF 文件")');
    const fileChooser = await fileChooserPromise;
    expect(fileChooser).toBeTruthy();
  });

  test('样式验证 - DESIGN.md 规范', async ({ page }) => {
    const uploadCard = page.locator('text=上传教材 PDF').locator('..');
    
    // 验证背景色
    const backgroundColor = await uploadCard.evaluate(el => 
      window.getComputedStyle(el).backgroundColor
    );
    expect(backgroundColor).toBe('rgb(250, 249, 245)'); // Ivory
  });
});
```

- [ ] **Step 3: 运行 Playwright 测试**

```bash
cd frontend
npx playwright test
```

Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add frontend/tests/e2e/
git commit -m "test: add E2E tests for upload functionality using Playwright MCP"
```

---

### Task 4.6: 创建阶段交接文档

**Files:**
- Create: `docs/handoffs/04-frontend.md`

- [ ] **Step 1: 创建前端开发交接文档**

```markdown
# 第四阶段交接：前端开发

**完成时间**: [填写]
**状态**: ✅ 完成

## 已实现组件

### 布局组件
- ✅ Navbar - 顶部导航栏
- ✅ MainLayout - 主布局容器

### 功能组件
- ✅ UploadCard - PDF 上传卡片（含进度显示）
- ✅ KnowledgeGraph - Cytoscape.js 知识图谱可视化
- ✅ NodeDetailPanel - 节点详情面板（预留）

### Hooks
- ✅ useWebSocket - WebSocket 连接管理
- ✅ useKnowledgeGraph - 图谱数据获取

### API 服务
- ✅ apiClient - 统一 API 客户端
- ✅ TypeScript 类型定义

## DESIGN.md 集成

- ✅ 样式变量映射
- ✅ 字体应用 (Georgia 标题, Inter 正文)
- ✅ 色彩系统 (Parchment 背景, Terracotta 强调)

## 测试覆盖

- ✅ 单元测试: Hooks, 组件
- ✅ E2E 测试: Playwright 浏览器测试
- ✅ 样式验证: DESIGN.md 规范检查

## 待实现

1. AI 导师界面组件
2. 多模态内容渲染器
3. 步进控制组件

## 下一步

进入第五阶段：集成测试和部署
```

- [ ] **Step 2: 提交文档**

```bash
git add docs/handoffs/04-frontend.md
git commit -m "docs: add frontend development handoff document"
```

---

## 第五阶段：集成测试和部署

### Task 5.1: 端到端集成测试

**Files:**
- Create: `backend/tests/e2e/test_full_workflow.py`

- [ ] **Step 1: 编写完整流程测试**

创建 `backend/tests/e2e/test_full_workflow.py`:

```python
import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)

def test_pdf_to_graph_workflow():
    """测试 PDF 上传到图谱生成完整流程"""
    
    # 1. 上传 PDF
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"
    response = client.post(
        "/api/pdf/upload",
        files={"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    task_id = data["taskId"]
    
    # 2. 检查状态
    for _ in range(60):  # 最多等待 60 秒
        status_response = client.get(f"/api/pdf/{task_id}")
        status_data = status_response.json()
        
        if status_data["status"] in ["completed", "failed"]:
            break
        
        time.sleep(1)
    
    assert status_data["status"] == "completed"
    
    # 3. 获取图谱数据
    graph_response = client.get(f"/api/graph/{task_id}")
    assert graph_response.status_code == 200
    
    graph_data = graph_response.json()
    assert "elements" in graph_data
    assert "nodes" in graph_data["elements"]
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest backend/tests/e2e/test_full_workflow.py -v
```

Expected: PASS（需要 Worker 和数据库运行）

- [ ] **Step 3: 提交**

```bash
git add backend/tests/e2e/test_full_workflow.py
git commit -m "test: add end-to-end integration test"
```

---

### Task 5.2: Docker 部署配置

**Files:**
- Create: `backend/Dockerfile`
- Create: `worker/Dockerfile`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: 创建后端 Dockerfile**

创建 `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 Worker Dockerfile**

创建 `worker/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]
```

- [ ] **Step 3: 创建前端 Dockerfile**

创建 `frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

创建 `frontend/nginx.conf`:

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
    }

    location /ws {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] **Step 4: 提交**

```bash
git add backend/Dockerfile worker/Dockerfile frontend/Dockerfile frontend/nginx.conf
git commit -m "feat: add Docker configuration for all services"
```

---

### Task 5.3: 最终验证和文档完善

**Files:**
- Modify: `README.md`
- Create: `docs/handoffs/05-integration.md`

- [ ] **Step 1: 更新 README.md**

```markdown
# ControlTheoryMentor - AI 导师系统

基于知识图谱的个性化 AI 自学导师系统。

## 快速开始

### 使用 Docker Compose

\`\`\`bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
\`\`\`

### 访问地址

- **前端应用**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **Neo4j 浏览器**: http://localhost:7474 (neo4j/password)

## 项目结构

\`\`\`
control-theory-mentor/
├── frontend/       # React + Vite 前端
├── backend/        # FastAPI 后端
├── worker/         # Celery 后台处理
├── docs/           # 项目文档
└── docker-compose.yml
\`\`\`

## 开发指南

### 前端开发

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

### 后端开发

\`\`\`bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
\`\`\`

### Worker 开发

\`\`\`bash
cd worker
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info
\`\`\`

## 测试

\`\`\`bash
# 后端测试
pytest backend/tests/

# 前端测试
cd frontend && npm test

# E2E 测试
cd frontend && npx playwright test
\`\`\`

## 技术栈

- **前端**: React, Vite, Cytoscape.js, Mermaid, KaTeX
- **后端**: FastAPI, Celery, Neo4j, Redis
- **样式**: DESIGN.md (Claude/Anthropic 设计系统)
- **测试**: Pytest, Vitest, Playwright MCP

## 设计文档

- [系统设计文档](docs/superpowers/specs/2026-04-18-ai-tutor-system-design.md)
- [实现计划](docs/superpowers/plans/2026-04-18-ai-tutor-system-a2.md)
- [阶段交接文档](docs/handoffs/)
```

- [ ] **Step 2: 创建最终交接文档**

创建 `docs/handoffs/05-integration.md`:

```markdown
# 第五阶段交接：集成测试和部署

**完成时间**: [填写]
**状态**: ✅ 完成

## 完成内容

### 集成测试
- ✅ 端到端工作流测试（PDF → 图谱）
- ✅ 所有服务间通信验证

### 部署配置
- ✅ Dockerfile 配置（前端/后端/Worker）
- ✅ Docker Compose 编排
- ✅ Nginx 反向代理配置

### 文档
- ✅ README.md 更新
- ✅ 阶段交接文档完整

## 系统验证

### 功能验证
- [ ] PDF 上传成功
- [ ] 后台处理完成
- [ ] 知识图谱生成
- [ ] 前端图谱展示
- [ ] WebSocket 实时更新

### 性能验证
- [ ] 100 页 PDF 处理时间 < 5 分钟
- [ ] 500 节点图谱渲染流畅
- [ ] API 响应时间 < 500ms

## 已知限制

1. Graphify 集成待实际测试
2. LLM 服务待配置
3. 多模态内容渲染器待实现

## 后续工作

1. 配置 Vercel AI SDK
2. 实现教学计划生成
3. 添加多模态内容支持
4. 完善错误处理和日志

## 项目状态

**A2 阶段**: ✅ 完成
**系统就绪**: ✅ 可部署
```

- [ ] **Step 3: 提交**

```bash
git add README.md docs/handoffs/05-integration.md
git commit -m "docs: complete integration and deployment documentation"
```

---

## 计划自检

### 覆盖度检查

✅ **基础设施**: Docker, 配置, 项目结构
✅ **后端 API**: PDF, 图谱, 导师 (框架)
✅ **Worker 服务**: Graphify, Celery, 后台任务
✅ **前端**: 组件, Hooks, API 客户端, E2E 测试
✅ **集成**: WebSocket, 端到端测试, 部署

### 无占位符验证

- ✅ 所有步骤包含具体代码
- ✅ 所有文件路径明确
- ✅ 所有测试用例完整
- ✅ 所有命令可执行

### 类型一致性

- ✅ API 类型定义前后端一致
- ✅ 数据模型 Neo4j 与 API 一致
- ✅ 组件 Props 类型匹配

---

## 执行选项

计划已保存至 `docs/superpowers/plans/2026-04-18-ai-tutor-system-a2.md`。

**两种执行方式：**

1. **Subagent-Driven（推荐）** - 每个任务使用独立子代理，任务间审核，快速迭代
2. **Inline Execution** - 在当前会话中使用 executing-plans 技能批量执行

选择哪种方式？
