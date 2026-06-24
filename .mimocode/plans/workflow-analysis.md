# ITOps Agent Platform 工作流功能分析

## 项目结构
```
itops-agent-platform/
├── backend/src/
│   ├── models/          # 数据模型
│   ├── routes/          # API 路由
│   ├──schemas/          # 数据验证
├── frontend/src/        # React 前端
```

## 核心工作流功能

### 1. 工作流定义 (Workflow Definition)
- **流程节点**：开始、结束、Agent执行、条件判断、循环
- **节点配置**：Agent选择、输入参数、输出处理
- **流程编排**：拖拽式可视化编辑

### 2. Agent 管理
- **预设 Agent**：告警处理、故障诊断、日志分析、系统巡检、变更执行、文档生成、合规检查
- **自定义 Agent**：支持配置系统提示词、模型、温度参数
- **Agent 测试**：执行历史追踪

### 3. 工作流执行
- **执行引擎**：顺序执行、条件分支、循环处理
- **状态管理**：运行中、成功、失败、等待
- **日志记录**：详细执行日志

### 4. 可视化界面
- **流程设计器**：拖拽式节点编辑
- **执行监控**：实时状态展示
- **历史查询**：执行记录查看

## OpsBrain 集成方案

### 1. 前端集成 (Vue 3)
- 参考 ITOps 的 React 工作流设计器
- 使用 Vue 3 + Element Plus 实现拖拽式流程编辑
- 节点类型：开始/结束/Agent/条件/循环

### 2. 后端集成 (FastAPI)
- 新增工作流模型：Workflow, WorkflowNode, WorkflowExecution
- 新增 API 接口：
  - `POST /api/v1/workflows` 创建工作流
  - `GET /api/v1/workflows` 列出工作流
  - `POST /api/v1/workflows/{id}/execute` 执行工作流
  - `GET /api/v1/workflows/{id}/status` 获取执行状态

### 3. Agent 编排
- 复用现有 Subagent 机制
- 支持工作流中调用多个 Agent
- 支持 Agent 间数据传递

## 实现步骤

1. **数据模型设计** (1天)
2. **API 接口开发** (2天)
3. **前端工作流设计器** (3天)
4. **执行引擎实现** (2天)
5. **集成测试** (1天)

## 技术栈

- **前端**: Vue 3 + Element Plus + Vue Flow (流程图库)
- **后端**: FastAPI + SQLAlchemy
- **执行引擎**: Python 异步任务队列
- **可视化**: Vue Flow / React Flow (参考)