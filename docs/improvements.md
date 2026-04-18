# 改进建议记录

## Task 1.1 (docker-compose.yml) 后续改进

### 安全增强
- [ ] 移除硬编码密码，使用环境变量 + .env.example
- [ ] 添加网络隔离（frontend/backend 分离）
- [ ] 配置 .env.example 模板

### 运维改进
- [ ] 添加健康检查（Neo4j, Redis, backend）
- [ ] 添加资源限制（内存/CPU）
- [ ] 添加重启策略
- [ ] 配置日志限制
- [ ] 修复 frontend 中 localhost 连接问题（应使用 service 名称）

### 文档完善
- [ ] 扩展 README.md（前置条件、故障排除、环境变量说明）

### 生产环境
- [ ] 创建 docker-compose.prod.yml（移除开发挂载、多阶段构建）
