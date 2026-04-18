# ControlTheoryMentor - AI 导师系统

基于知识图谱的个性化 AI 自学导师。当前 PDF 图谱流程已切换到上游 Graphify 0.4.21 的 detect / build / cluster / report / export 阶段，并通过真实 LLM 语义抽取驱动非代码语料。

## 快速开始

### 使用 Docker Compose (推荐)

```bash
# 启动所有服务
docker-compose up -d

# 访问
# - 前端: http://localhost:5173
# - 后端 API: http://localhost:8000/docs
# - Neo4j 浏览器: http://localhost:7474 (neo4j/password)
```

### 手动启动 (开发模式)

**前置要求:**
- Python 3.11+
- Node.js 20+
- Neo4j 5.15+
- Redis 7+

**后端启动:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**前端启动:**
```bash
cd frontend
npm install
npm run dev
```

**Worker 启动:**
```bash
cd worker
pip install -r requirements.txt
celery -A worker.celery_app worker --loglevel=info
```

## Graphify 运行时要求

Worker 不再提供本地规则兜底抽取。处理 PDF、文档或图片时，必须配置真实的 Graphify 语义模型运行时；否则任务会直接失败，而不是生成伪图谱。

支持的运行时变量:

```bash
GRAPHIFY_LLM_API_KEY=your-provider-key
GRAPHIFY_LLM_MODEL=gpt-4.1-mini
GRAPHIFY_LLM_BASE_URL=https://api.openai.com/v1
GRAPHIFY_LLM_TIMEOUT_SECONDS=120
GRAPHIFY_LLM_MAX_CHUNK_CHARS=50000
GRAPHIFY_LLM_MAX_OUTPUT_TOKENS=4000
```

说明:
- `GRAPHIFY_LLM_API_KEY` 也可用 `OPENAI_API_KEY` 代替。
- `GRAPHIFY_LLM_MODEL` 也可用 `OPENAI_MODEL` 代替。
- 代码-only 图谱仍可走 Graphify AST 抽取；但当前产品入口是 PDF 上传，所以默认需要 LLM 运行时。

## 项目结构

```
ControlTheoryMentor/
├── frontend/          # React + TypeScript + Vite 前端
│   ├── src/
│   │   ├── components/    # UI 组件
│   │   ├── pages/         # 页面组件
│   │   ├── services/      # API 服务层
│   │   └── types/         # TypeScript 类型定义
│   ├── tests/             # Playwright E2E 测试
│   ├── Dockerfile         # 多阶段构建配置
│   └── nginx.conf         # Nginx 生产配置
├── backend/           # FastAPI 后端
│   ├── app/
│   │   ├── api/           # API 路由
│   │   │   └── routes/    # 业务路由
│   │   ├── schemas/       # Pydantic 数据模型
│   │   ├── db/            # 数据库连接
│   │   └── config.py      # 配置管理
│   ├── tests/             # Pytest 测试套件
│   │   ├── unit/          # 单元测试
│   │   ├── integration/   # 集成测试
│   │   └── e2e/           # E2E 测试
│   └── Dockerfile         # 多阶段构建配置
├── worker/            # Celery 后台任务处理
│   ├── tasks/             # 异步任务定义
│   ├── celery_app.py      # Celery 应用配置
│   └── Dockerfile         # 多阶段构建配置
├── docs/              # 项目文档
│   └── handoffs/         # 阶段交付文档
└── docker-compose.yml  # 服务编排配置
```

## 开发指南

### API 文档

启动后端服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 测试

**后端测试:**
```bash
cd backend

# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# E2E 测试 (需要服务运行)
pytest tests/e2e/

# 运行所有测试
pytest tests/ -v
```

**前端测试:**
```bash
cd frontend

# 单元测试
npm run test

# E2E 测试
npm run test:e2e
```

### 环境变量

创建 `.env` 文件配置以下变量:

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_PREFIX=/api

# Storage
PDF_STORAGE_PATH=./pdfs
MAX_PDF_PAGES=1200

# Graphify semantic extraction
GRAPHIFY_LLM_API_KEY=
GRAPHIFY_LLM_MODEL=gpt-4.1-mini
GRAPHIFY_LLM_BASE_URL=
```

## 部署

### 生产部署

**1. 构建镜像:**
```bash
docker-compose build
```

**2. 启动服务:**
```bash
docker-compose up -d
```

**3. 健康检查:**
```bash
# 后端健康检查
curl http://localhost:8000/health

# 前端健康检查
curl http://localhost:5173
```

**4. 查看日志:**
```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f backend
docker-compose logs -f worker
docker-compose logs -f frontend
```

### Docker 镜像

所有服务使用多阶段构建:
- **Backend**: Python 3.11 slim + FastAPI
- **Worker**: Python 3.11 slim + Celery
- **Frontend**: Node 20 + Nginx Alpine

镜像特性:
- 最小化镜像大小
- 非 root 用户运行
- 内置健康检查
- 生产优化配置

## 技术栈

**前端:**
- React 18
- TypeScript 5
- Vite 5
- Cytoscape.js (知识图谱可视化)

**后端:**
- FastAPI
- Pydantic (数据验证)
- Neo4j (图数据库)
- Redis (缓存/消息队列)
- Celery (异步任务)

**知识图谱:**
- Graphify 0.4.21
- OpenAI 兼容 Chat Completions 语义抽取
- Graphify JSON / HTML / Markdown / Cypher 导出

**DevOps:**
- Docker & Docker Compose
- Multi-stage builds
- Nginx (反向代理)

## 文档

详细文档请查看:
- [集成测试文档](docs/handoffs/05-integration.md)
- API 文档: 启动后端访问 /docs

## License

MIT
