"""
OpsBrain Web — Workflow Service

业务逻辑层：工作流定义、执行等操作
"""

from __future__ import annotations

import json as _json
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Workflow, WorkflowExecution


def _now() -> datetime:
    return datetime.utcnow()


class WorkflowService:
    """工作流业务服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        result = await self.session.execute(
            select(Workflow).order_by(Workflow.updated_at.desc())
        )
        workflows = result.scalars().all()
        return [w.to_dict() for w in workflows]

    async def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """获取单个工作流"""
        result = await self.session.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        return workflow.to_dict() if workflow else None

    async def create_workflow(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """创建工作流"""
        workflow = Workflow(
            name=data.get("name", ""),
            description=data.get("description", ""),
            nodes=_json.dumps(data.get("nodes", [])),
            edges=_json.dumps(data.get("edges", [])),
            agent_configs=_json.dumps(data.get("agent_configs", {})),
            is_template=data.get("is_template", False),
            is_enabled=data.get("is_enabled", True),
        )
        self.session.add(workflow)
        await self.session.commit()
        await self.session.refresh(workflow)

        return workflow.to_dict()

    async def update_workflow(self, workflow_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新工作流"""
        result = await self.session.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            return None

        if "name" in data:
            workflow.name = data["name"]
        if "description" in data:
            workflow.description = data["description"]
        if "nodes" in data:
            workflow.nodes = _json.dumps(data["nodes"])
        if "edges" in data:
            workflow.edges = _json.dumps(data["edges"])
        if "agent_configs" in data:
            workflow.agent_configs = _json.dumps(data["agent_configs"])
        if "is_enabled" in data:
            workflow.is_enabled = data["is_enabled"]

        workflow.updated_at = _now()
        await self.session.commit()
        await self.session.refresh(workflow)

        return workflow.to_dict()

    async def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        result = await self.session.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            return False

        await self.session.delete(workflow)
        await self.session.commit()

        return True

    async def create_execution(self, workflow_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """创建工作流执行记录"""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError("Workflow not found")

        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_name=workflow["name"],
            status="running",
            start_time=_now(),
            initial_input=_json.dumps(params or {}),
            execution_order=_json.dumps([]),
            node_results=_json.dumps({}),
        )
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)

        return execution.to_dict()

    async def update_execution(self, execution_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新执行记录"""
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if not execution:
            return None

        if "status" in data:
            execution.status = data["status"]
            if data["status"] in ("completed", "failed"):
                execution.end_time = _now()
        if "current_node_index" in data:
            execution.current_node_index = data["current_node_index"]
        if "execution_order" in data:
            execution.execution_order = _json.dumps(data["execution_order"])
        if "node_results" in data:
            execution.node_results = _json.dumps(data["node_results"])
        if "error_message" in data:
            execution.error_message = data["error_message"]

        execution.updated_at = _now()
        await self.session.commit()
        await self.session.refresh(execution)

        return execution.to_dict()

    async def list_executions(self, workflow_id: str) -> List[Dict[str, Any]]:
        """列出工作流的执行记录"""
        result = await self.session.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .order_by(WorkflowExecution.created_at.desc())
        )
        executions = result.scalars().all()
        return [e.to_dict() for e in executions]

    async def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取执行记录"""
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        return execution.to_dict() if execution else None