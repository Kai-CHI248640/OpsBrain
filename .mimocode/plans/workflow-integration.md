# ITOps Agent Platform 工作流功能分析报告

## 1. 工作流核心数据结构

### 数据库表设计 (SQLite)
```sql
CREATE TABLE workflows (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  nodes TEXT,          -- JSON: 节点配置
  edges TEXT,          -- JSON: 边配置
  agent_configs TEXT,  -- JSON: Agent 配置
  is_template INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 节点类型 (WorkflowNode)
- `start`: 开始节点
- `end`: 结束节点
- `agent`: Agent 执行节点
- `condition`: 条件判断节点
- `loop`: 循环节点
- `approval`: 审批节点

### 边配置 (WorkflowEdge)
```typescript
interface WorkflowEdge {
  id: string;
  source: string;  // 源节点ID
  target: string;  // 目标节点ID
  sourceHandle?: string;
  targetHandle?: string;
  type?: 'default' | 'condition';
  condition?: string;  // 条件表达式
}
```

## 2. API 接口设计

### 工作流管理
```
GET    /api/workflows           - 列出所有工作流
GET    /api/workflows/:id       - 获取单个工作流
POST   /api/workflows           - 创建工作流
PUT    /api/workflows/:id       - 更新工作流
DELETE /api/workflows/:id       - 删除工作流
POST   /api/workflows/import    - 导入工作流
GET    /api/workflows/export/:id - 导出工作流
```

### 工作流执行
```
POST   /api/tasks               - 创建任务（触发工作流执行）
GET    /api/tasks/:id           - 获取任务状态
GET    /api/tasks/:id/logs      - 获取执行日志
```

## 3. 执行引擎核心逻辑

### 执行流程
1. **拓扑排序**: 根据节点依赖关系计算执行顺序
2. **节点执行**: 按顺序执行每个节点
3. **状态管理**: 记录每个节点的执行结果
4. **错误处理**: 失败时记录错误并通知

### 关键函数
```typescript
executeWorkflow(taskId, workflow, initialInput, context)
├─ topologicalSort(nodes, edges)  // 拓扑排序
├─ executeFromIndex(...)          // 从指定索引执行
│  ├─ executeAgentNode()          // 执行 Agent 节点
│  ├─ executeConditionNode()      // 执行条件节点
│  └─ executeLoopNode()           // 执行循环节点
└─ generateWorkflowExecutionReport()  // 生成报告
```

## 4. OpsBrain 集成方案

### 4.1 数据模型设计 (Python/SQLAlchemy)

```python
# web/backend/app/models.py
class Workflow(Base):
    __tablename__ = "workflows"
    
    id = Column(String, primary_key=True, default=uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    nodes = Column(JSON)  # 节点配置
    edges = Column(JSON)  # 边配置
    agent_configs = Column(JSON)  # Agent 配置
    is_template = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    
    id = Column(String, primary_key=True, default=uuid4)
    workflow_id = Column(String, ForeignKey("workflows.id"))
    task_id = Column(String, ForeignKey("tasks.id"))
    status = Column(String)  # running/completed/failed/paused
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    node_results = Column(JSON)  # 节点执行结果
    execution_order = Column(JSON)  # 执行顺序
```

### 4.2 API 接口实现

```python
# web/backend/app/routes/workflow.py
@workflow_router.post("/")
async def create_workflow(data: dict, user: User = Depends(get_current_user)):
    """创建工作流"""
    pass

@workflow_router.get("/")
async def list_workflows(user: User = Depends(get_current_user)):
    """列出工作流"""
    pass

@workflow_router.post("/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, data: dict):
    """执行工作流"""
    pass
```

### 4.3 前端集成 (Vue 3)

**技术选型**:
- **流程图库**: Vue Flow (https://vueflow.dev/)
- **节点编辑**: Element Plus 表单组件
- **状态管理**: Pinia

**组件结构**:
```
workflow-designer/
├── WorkflowCanvas.vue     # 流程画布
├── NodePalette.vue        # 节点面板
├── NodeEditor.vue         # 节点编辑器
├── WorkflowList.vue       # 工作流列表
└── ExecutionMonitor.vue   # 执行监控
```

### 4.4 执行引擎实现

```python
# web/backend/app/services/workflow_executor.py
class WorkflowExecutor:
    async def execute(self, workflow_id: str, context: dict = None):
        workflow = await self.get_workflow(workflow_id)
        execution_order = self.topological_sort(workflow.nodes, workflow.edges)
        
        node_results = {}
        for node_id in execution_order:
            node = workflow.nodes[node_id]
            result = await self.execute_node(node, context)
            node_results[node_id] = result
            
            # 条件判断/循环处理
            if node.type == "condition":
                if not self.evaluate_condition(node, result):
                    continue
            elif node.type == "loop":
                await self.handle_loop(node, result)
        
        return node_results
```

## 5. 实现计划

| 阶段 | 任务 | 预计时间 |
|------|------|---------|
| 1 | 数据模型设计 + 迁移脚本 | 1天 |
| 2 | 后端 API 接口开发 | 2天 |
| 3 | 前端流程设计器 (Vue Flow) | 3天 |
| 4 | 执行引擎 + Agent 编排 | 2天 |
| 5 | 集成测试 + 文档 | 1天 |

## 6. 参考资料

- ITOps Agent Platform: https://github.com/qinshihu/itops-agent-platform
- Vue Flow: https://vueflow.dev/
- Prefect (Python 工作流引擎): https://www.prefect.io/