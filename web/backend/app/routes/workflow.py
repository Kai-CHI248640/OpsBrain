"""
OpsBrain — Workflow Routes

工作流 CRUD + 执行 API（参考 ITOps Agent Platform）
"""

from __future__ import annotations

import json as _json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..auth import get_current_user
from ..database import async_session
from ..models import User, Workflow, WorkflowExecution, ApiKey
from ..services.workflow_service import WorkflowService
from ..utils.response import ApiResponse, NotFoundException

from logging_setup import get_logger

log = get_logger(__name__)
workflow_router = APIRouter()


def _now() -> datetime:
    return datetime.utcnow()


@workflow_router.get("/")
async def list_workflows(user: User = Depends(get_current_user)):
    """列出所有工作流"""
    async with async_session() as session:
        service = WorkflowService(session)
        workflows = await service.list_workflows()
    return ApiResponse.success(workflows, "查询成功")


@workflow_router.get("/templates/list")
async def list_templates(user: User = Depends(get_current_user)):
    """列出工作流模板"""
    async with async_session() as session:
        result = await session.execute(
            select(Workflow).where(Workflow.is_template == True)
            .order_by(Workflow.created_at.desc())
        )
        templates = result.scalars().all()
    return ApiResponse.success([t.to_dict() for t in templates], "查询成功")


@workflow_router.get("/export/{wf_id}")
async def export_workflow(wf_id: str, user: User = Depends(get_current_user)):
    """导出工作流"""
    async with async_session() as session:
        service = WorkflowService(session)
        wf = await service.get_workflow(wf_id)
    if not wf:
        raise NotFoundException("工作流不存在")
    return ApiResponse.success(wf, "导出成功")


@workflow_router.get("/{wf_id}")
async def get_workflow(wf_id: str, user: User = Depends(get_current_user)):
    """获取单个工作流详情"""
    async with async_session() as session:
        service = WorkflowService(session)
        wf = await service.get_workflow(wf_id)
    if not wf:
        raise NotFoundException("工作流不存在")
    return ApiResponse.success(wf, "查询成功")


@workflow_router.post("/")
async def create_workflow(data: dict, user: User = Depends(get_current_user)):
    """创建工作流"""
    async with async_session() as session:
        service = WorkflowService(session)
        result = await service.create_workflow(data)
    log.info("Workflow created", extra={"name": result["name"], "id": result["id"]})
    return ApiResponse.success(result, "创建成功")


@workflow_router.put("/{wf_id}")
async def update_workflow(wf_id: str, data: dict, user: User = Depends(get_current_user)):
    """更新工作流"""
    async with async_session() as session:
        service = WorkflowService(session)
        result = await service.update_workflow(wf_id, data)
    if not result:
        raise NotFoundException("工作流不存在")
    return ApiResponse.success(result, "更新成功")


@workflow_router.delete("/{wf_id}")
async def delete_workflow(wf_id: str, user: User = Depends(get_current_user)):
    """删除工作流及其执行记录"""
    async with async_session() as session:
        result = await session.execute(select(Workflow).where(Workflow.id == wf_id))
        wf = result.scalar_one_or_none()
        if not wf:
            raise NotFoundException("工作流不存在")

        exec_result = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.workflow_id == wf_id)
        )
        for ex in exec_result.scalars().all():
            await session.delete(ex)

        await session.delete(wf)
        await session.commit()

    return ApiResponse.success({"id": wf_id}, "删除成功")


@workflow_router.post("/{wf_id}/execute")
async def execute_workflow(wf_id: str, data: dict, user: User = Depends(get_current_user)):
    """执行工作流"""
    async with async_session() as session:
        service = WorkflowService(session)
        wf = await service.get_workflow(wf_id)
        if not wf:
            raise NotFoundException("工作流不存在")
        if not wf["is_enabled"]:
            return ApiResponse.error("工作流已禁用", 400)

        execution = await service.create_execution(wf_id, data.get("input", ""))

    import asyncio
    asyncio.create_task(_run_workflow(execution["id"], wf, data.get("input", "")))

    return ApiResponse.success({
        "execution_id": execution["id"],
        "status": "running",
        "message": f"工作流 '{wf['name']}' 已开始执行",
    }, "执行成功")


@workflow_router.get("/{wf_id}/executions")
async def list_executions(wf_id: str, user: User = Depends(get_current_user)):
    """列出工作流的执行记录"""
    async with async_session() as session:
        service = WorkflowService(session)
        executions = await service.list_executions(wf_id)
    return ApiResponse.success(executions, "查询成功")


@workflow_router.get("/executions/{exec_id}")
async def get_execution(exec_id: str, user: User = Depends(get_current_user)):
    """获取执行详情"""
    async with async_session() as session:
        service = WorkflowService(session)
        ex = await service.get_execution(exec_id)
    if not ex:
        raise NotFoundException("执行记录不存在")
    return ApiResponse.success(ex, "查询成功")


@workflow_router.post("/templates/{tmpl_id}/instantiate")
async def instantiate_template(tmpl_id: str, data: dict, user: User = Depends(get_current_user)):
    """从模板创建工作流"""
    async with async_session() as session:
        result = await session.execute(select(Workflow).where(Workflow.id == tmpl_id))
        tmpl = result.scalar_one_or_none()
        if not tmpl:
            raise NotFoundException("模板不存在")

        wf = Workflow(
            name=data.get("name", f"{tmpl.name} (副本)"),
            description=tmpl.description,
            nodes=tmpl.nodes,
            edges=tmpl.edges,
            agent_configs=tmpl.agent_configs,
            is_template=False,
        )
        session.add(wf)
        await session.commit()
        await session.refresh(wf)

    return ApiResponse.success(wf.to_dict(), "创建成功")


@workflow_router.post("/import")
async def import_workflow(data: dict, user: User = Depends(get_current_user)):
    """导入工作流"""
    wf_data = data.get("workflow", data)
    if not wf_data.get("name"):
        return ApiResponse.error("工作流名称不能为空")

    async with async_session() as session:
        service = WorkflowService(session)
        result = await service.create_workflow(wf_data)

    return ApiResponse.success(result, "导入成功")


async def _run_workflow(exec_id: str, wf_dict: dict, initial_input: str = ""):
    """异步执行工作流"""
    import asyncio

    nodes = wf_dict.get("nodes", [])
    edges = wf_dict.get("edges", [])

    execution_order = _topological_sort(nodes, edges)
    node_results = {}

    async with async_session() as session:
        service = WorkflowService(session)
        await service.update_execution(exec_id, {"execution_order": execution_order})

    try:
        for i, node_id in enumerate(execution_order):
            node = next((n for n in nodes if n.get("id") == node_id), None)
            if not node:
                continue

            node_type = node.get("type", "agent")
            node_data = node.get("data", {})

            log.info(f"Workflow executing node {i+1}/{len(execution_order)}",
                     extra={"node_id": node_id, "type": node_type})

            async with async_session() as session:
                service = WorkflowService(session)
                await service.update_execution(exec_id, {"current_node_index": i})

            try:
                if node_type == "start":
                    node_results[node_id] = {"status": "completed", "output": initial_input}
                elif node_type == "end":
                    prev_output = _get_previous_output(node_id, edges, node_results)
                    node_results[node_id] = {"status": "completed", "output": prev_output}
                elif node_type == "agent":
                    result = await _execute_agent_node(node_id, node_data, initial_input, node_results, edges)
                    node_results[node_id] = result
                elif node_type == "condition":
                    result = await _execute_condition_node(node_id, node_data, node_results, edges)
                    node_results[node_id] = result
                elif node_type == "delay":
                    delay_sec = node_data.get("seconds", 5)
                    await asyncio.sleep(min(delay_sec, 60))
                    node_results[node_id] = {"status": "completed", "output": f"延迟 {delay_sec}秒"}
                else:
                    node_results[node_id] = {"status": "skipped", "output": f"未知节点类型: {node_type}"}
            except Exception as e:
                node_results[node_id] = {"status": "failed", "error": str(e)}
                log.error(f"Node execution failed", extra={"node_id": node_id, "error": str(e)})

            async with async_session() as session:
                service = WorkflowService(session)
                await service.update_execution(exec_id, {"node_results": node_results})

        async with async_session() as session:
            service = WorkflowService(session)
            await service.update_execution(exec_id, {
                "status": "completed",
                "node_results": node_results,
            })

        log.info("Workflow execution completed", extra={"exec_id": exec_id})

    except Exception as e:
        async with async_session() as session:
            service = WorkflowService(session)
            await service.update_execution(exec_id, {
                "status": "failed",
                "error_message": str(e),
                "node_results": node_results,
            })

        log.error("Workflow execution failed", extra={"exec_id": exec_id, "error": str(e)})


async def _execute_agent_node(node_id: str, node_data: dict, initial_input: str,
                               node_results: dict, edges: list) -> dict:
    """执行 Agent 节点 — 调用 LLM"""
    import httpx

    prompt = node_data.get("prompt", "")
    agent_name = node_data.get("agent_name", "Agent")

    prev_output = _get_previous_output(node_id, edges, node_results) or initial_input

    full_prompt = f"{prompt}\n\n输入: {prev_output}" if prev_output else prompt

    try:
        async with async_session() as session:
            result = await session.execute(
                select(ApiKey).where(ApiKey.is_active == True, ApiKey.api_type == "llm")
                .order_by(ApiKey.is_default.desc())
            )
            ak = result.scalar_one_or_none()

        if not ak:
            return {"status": "failed", "error": "No active API key configured"}

        base = (ak.api_base or "").strip()
        if base:
            url = base.rstrip("/") + "/chat/completions"
        else:
            from ..routes.agent import _PROVIDERS
            url = _PROVIDERS.get(ak.provider.strip(), "")

        if not url:
            return {"status": "failed", "error": f"Unknown provider: {ak.provider}"}

        messages = [
            {"role": "system", "content": f"你是 {agent_name}，一个专业的网络运维助手。"},
            {"role": "user", "content": full_prompt},
        ]

        headers = {
            "Authorization": f"Bearer {ak.api_key}",
            "Content-Type": "application/json",
        }
        body = {"model": ak.model, "messages": messages, "max_tokens": 2000}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        reply = data["choices"][0]["message"]["content"]
        return {"status": "completed", "output": reply, "agent": agent_name}

    except Exception as e:
        return {"status": "failed", "error": str(e)}


async def _execute_condition_node(node_id: str, node_data: dict, node_results: dict, edges: list) -> dict:
    """执行条件节点"""
    condition = node_data.get("condition", "")
    prev_output = _get_previous_output(node_id, edges, node_results)

    if not condition:
        return {"status": "completed", "output": "true", "branch": "true"}

    try:
        result = eval(condition, {"__builtins__": {}}, {
            "input": prev_output or "",
            "output": prev_output or "",
            "len": len,
            "str": str,
            "int": int,
            "contains": lambda s, sub: sub in str(s),
        })
        branch = "true" if result else "false"
        return {"status": "completed", "output": str(result), "branch": branch}
    except Exception:
        return {"status": "completed", "output": "true", "branch": "true"}


def _get_previous_output(node_id: str, edges: list, node_results: dict) -> str:
    """获取前驱节点的输出"""
    for edge in edges:
        if edge.get("target") == node_id:
            source_id = edge.get("source")
            if source_id and source_id in node_results:
                result = node_results[source_id]
                return result.get("output", "")
    return ""


def _topological_sort(nodes: list, edges: list) -> list:
    """拓扑排序，返回执行顺序"""
    in_degree = {}
    adj = {}

    for node in nodes:
        nid = node.get("id", "")
        in_degree[nid] = 0
        adj[nid] = []

    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in in_degree and tgt in in_degree:
            in_degree[tgt] += 1
            adj[src].append(tgt)

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    order = []

    while queue:
        current = queue.pop(0)
        order.append(current)
        for neighbor in adj.get(current, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        log.warning("Circular dependency detected in workflow, using fallback order")
        return [n.get("id") for n in nodes]

    return order