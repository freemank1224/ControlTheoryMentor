# 第三阶段交接：Worker 服务开发

**完成时间**: 2026-04-18
**状态**: ✅ 完成

## 已实现功能

### Worker 服务
- ✅ Celery 配置和任务队列 (`worker/celery_app.py`)
- ✅ Graphify 封装 (`worker/graphify_wrapper.py`)
- ✅ PDF 处理后台任务 (`worker/tasks.py`)
- ✅ Neo4j 数据写入集成
- ✅ 单元测试和集成测试

### 后端集成
- ✅ 后端 API 集成 Celery (`backend/app/api/routes/pdf.py`)
- ✅ WebSocket 实时状态推送 (`backend/app/api/websocket/handler.py`)
- ✅ 任务状态查询接口

## 文件清单

### Worker 服务
```
worker/
├── requirements.txt           # Worker 依赖包
├── celery_app.py             # Celery 应用配置
├── graphify_wrapper.py       # Graphify 封装（Mock 实现）
├── tasks.py                  # Celery 后台任务定义
└── tests/
    ├── __init__.py
    ├── test_graphify_wrapper.py  # Graphify 封装测试
    └── test_tasks.py              # 任务测试
```

### 后端更新
```
backend/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── pdf.py        # 更新：集成 Celery
│   │   └── websocket/
│   │       ├── __init__.py
│   │       └── handler.py    # 新增：WebSocket 处理
│   └── main.py               # 更新：添加 WebSocket 路由
└── requirements.txt          # 已包含 Celery
```

## 数据流

```
用户上传 PDF
    ↓
前端: POST /api/pdf/upload
    ↓
后端: 保存文件 → 生成 taskId
    ↓
后端: process_pdf_task.delay() → Celery 队列
    ↓
前端: 连接 WS /ws/graph/{taskId}
    ↓
Worker: 从 Redis 取任务
    ↓
Worker: GraphifyProcessor.process_pdf()
    ├─ 提取文本 (pypdf)
    ├─ 提取概念 (正则匹配)
    ├─ 提取关系 (共现分析)
    └─ 写入 Neo4j
    ↓
Worker: 更新任务状态 → Redis
    ↓
WebSocket: 推送进度更新
    ├─ task.progress {percent, message}
    ├─ task.completed {graphId}
    └─ task.failed {error}
```

## API 更新

### 新增/更新的端点

#### POST /api/pdf/upload
**更新**: 集成 Celery 后台处理
```json
// Request
POST /api/pdf/upload
Content-Type: multipart/form-data
file: <PDF file>

// Response
{
  "id": "pdf-123",
  "filename": "textbook.pdf",
  "page_count": 42,
  "status": "processing"  // 立即返回，后台处理
}
```

#### GET /api/pdf/{pdf_id}/status
**更新**: 包含任务状态信息
```json
{
  "id": "pdf-123",
  "status": "processing",
  "task_id": "task-123",      // 新增
  "task_status": "PROGRESS",  // 新增
  "task_info": {              // 新增
    "percent": 45,
    "message": "正在提取第3章概念..."
  }
}
```

#### WS /ws/graph/{task_id}
**新增**: WebSocket 实时更新
```javascript
// 连接
const ws = new WebSocket('ws://localhost:8000/ws/graph/task-123');

// 消息类型
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // 连接确认
  if (data.type === 'connection.established') {
    console.log('Connected to task updates');
  }

  // 进度更新
  if (data.type === 'task.progress') {
    console.log(`Progress: ${data.data.percent}%`);
    console.log(`Message: ${data.data.message}`);
  }

  // 处理完成
  if (data.type === 'task.completed') {
    console.log(`Graph ID: ${data.data.graph_id}`);
    // 导航到图谱视图
  }

  // 处理失败
  if (data.type === 'task.failed') {
    console.error(`Error: ${data.data.error}`);
  }
};
```

## Graphify 封装说明

### 当前实现
- **上游对齐实现**: 使用 Graphify 0.4.21 的 detect / build / cluster / analyze / report / export 流程
- **语义抽取**: 对 PDF、文档、图片使用真实 LLM 语义抽取，并写出 `.graphify_detect.json`、`.graphify_ast.json`、`.graphify_semantic.json`、`.graphify_extract.json`
- **代码抽取**: 对 code 文件继续使用 Graphify 官方 AST 抽取
- **失败策略**: 不再提供本地规则兜底；缺少或错误的 provider 配置会直接失败

### 接口定义
```python
class GraphifyProcessor:
  def __init__(self, neo4j_uri, neo4j_user, neo4j_password, artifacts_root=None, llm_config=None)
  def process_pdf(self, pdf_path, graph_id, progress_callback=None) -> Dict[str, Any]
    def close()
```

### 运行时要求
```bash
GRAPHIFY_LLM_API_KEY=...
GRAPHIFY_LLM_MODEL=gpt-4.1-mini
GRAPHIFY_LLM_BASE_URL=
GRAPHIFY_LLM_TIMEOUT_SECONDS=120
GRAPHIFY_LLM_MAX_CHUNK_CHARS=50000
GRAPHIFY_LLM_MAX_OUTPUT_TOKENS=4000
```

说明:
- `GRAPHIFY_LLM_API_KEY` 可由 `OPENAI_API_KEY` 代替。
- `GRAPHIFY_LLM_MODEL` 可由 `OPENAI_MODEL` 代替。
- Worker 任务只保留 `process_pdf_task`、`health_check_task`、`cleanup_old_tasks`。

## 测试覆盖

### 单元测试
- ✅ LLM 配置校验
- ✅ 抽取结果合并去重
- ✅ PDF 产物写出流程

### 任务测试
- ✅ process_pdf_task 结构
- ✅ health_check_task
- ✅ 非可重试配置错误
- ✅ 错误处理和重试逻辑

### 运行测试
```bash
# Worker 测试
cd worker
pytest tests/ -v

# 后端集成测试
cd backend
pytest tests/integration/ -v
```

## 部署配置

### 环境变量
```bash
# .env
REDIS_URL=redis://localhost:6379/0
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### 启动 Worker
```bash
cd worker
celery -A celery_app worker --loglevel=info --pool=solo
```

### Docker 配置
需要在 `docker-compose.yml` 中添加 worker 服务：
```yaml
worker:
  build: ./worker
  environment:
    REDIS_URL: redis://redis:6379/0
    NEO4J_URI: bolt://neo4j:7687
  depends_on:
    - redis
    - neo4j
```

## 已知限制

### 当前实现限制
1. **Graphify Mock**: 使用简单的正则匹配，非真正的 NLP/LLM 提取
2. **进度报告**: 进度更新为粗粒度（10%, 30%, 70%, 90%）
3. **错误处理**: 部分 Redis 错误被静默处理

### 待优化项
1. 实际集成 Graphify 库
2. 细粒度进度报告（页级别）
3. 完善错误处理和重试逻辑
4. 添加任务优先级队列

## 技术要点

### Celery 配置
- **Broker**: Redis
- **Result Backend**: Redis
- **任务路由**: pdf_processing, graph_generation 队列
- **重试策略**: 指数退避 (60s * retry_count)
- **超时设置**: 1小时硬限制，50分钟软限制

### WebSocket 管理
- **连接管理**: ConnectionManager 类管理多个连接
- **状态监控**: 轮询 Redis 获取任务状态
- **消息类型**: connection.established, task.progress, task.completed, task.failed
- **错误处理**: 自动清理断开的连接

### Neo4j 集成
- **节点类型**: PDF, Concept
- **关系类型**: RELATED_TO
- **索引**: 需要创建 id 和 pdfId 索引

## 下一步

进入第四阶段：**前端开发**

### 需要实现的前端功能
1. API 客户端服务 (`frontend/src/services/api.ts`)
2. WebSocket Hook (`frontend/src/hooks/useWebSocket.ts`)
3. PDF 上传组件 (`frontend/src/components/upload/UploadCard.tsx`)
4. 知识图谱可视化 (`frontend/src/components/graph/KnowledgeGraph.tsx`)

### 前端集成要点
- 使用 WebSocket 实时显示处理进度
- 任务完成后自动跳转到图谱视图
- 错误处理和用户反馈

## 故障排查

### Worker 不启动
```bash
# 检查 Redis 连接
redis-cli ping

# 检查 Celery 配置
celery -A worker.celery_app inspect active

# 查看日志
celery -A worker.celery_app worker --loglevel=debug
```

### WebSocket 连接失败
```bash
# 检查后端是否运行
curl http://localhost:8000/health

# 检查 WebSocket 路由
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://localhost:8000/ws/graph/test-123
```

### Neo4j 写入失败
```bash
# 检查 Neo4j 连接
cypher-shell -u neo4j -p password

# 查看节点
MATCH (n) RETURN n LIMIT 10;
```

## 交付清单

- [x] Worker Celery 配置
- [x] Graphify 封装（Mock 实现）
- [x] PDF 处理任务
- [x] 后端 Celery 集成
- [x] WebSocket 实时更新
- [x] 单元测试
- [x] 交接文档

**所有 5 个子任务已完成 ✅**
