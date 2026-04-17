# ControlTheoryMentor - AI 导师系统

基于知识图谱的个性化 AI 自学导师。

## 快速开始

```bash
# 启动所有服务
docker-compose up -d

# 访问
# - 前端: http://localhost:5173
# - 后端 API: http://localhost:8000
# - Neo4j 浏览器: http://localhost:7474
```

## 项目结构

- frontend/: React + Vite 前端
- backend/: FastAPI 后端
- worker/: Graphify 处理服务
