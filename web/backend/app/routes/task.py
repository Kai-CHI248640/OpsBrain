"""
OpsBrain Web — Scheduled Task Routes

定时任务管理 API
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_session
from ..models import User
from ..schemas import ScheduledTaskCreate, ScheduledTaskUpdate
from ..services.task_service import TaskService
from ..utils.response import ApiResponse

task_router = APIRouter()


@task_router.get("/tasks")
async def list_tasks(user: User = Depends(get_current_user)):
    tasks = await TaskService.get_all_tasks()
    return ApiResponse.success(data=tasks)


@task_router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: User = Depends(get_current_user)):
    task = await TaskService.get_task_by_id(task_id)
    return ApiResponse.success(data=task)


@task_router.post("/tasks")
async def create_task(
    req: ScheduledTaskCreate,
    user: User = Depends(get_current_user),
):
    task = await TaskService.create_task(req.model_dump())
    return ApiResponse.success(data=task, message="任务创建成功")


@task_router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    req: ScheduledTaskUpdate,
    user: User = Depends(get_current_user),
):
    task = await TaskService.update_task(task_id, req.model_dump(exclude_none=True))
    return ApiResponse.success(data=task, message="任务更新成功")


@task_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: User = Depends(get_current_user)):
    await TaskService.delete_task(task_id)
    return ApiResponse.success(message="任务删除成功")


@task_router.post("/tasks/{task_id}/toggle")
async def toggle_task(
    task_id: str,
    is_enabled: bool,
    user: User = Depends(get_current_user),
):
    task = await TaskService.toggle_task(task_id, is_enabled)
    message = "任务已启用" if is_enabled else "任务已禁用"
    return ApiResponse.success(data=task, message=message)


@task_router.get("/tasks/{task_id}/logs")
async def get_task_logs(task_id: str, limit: int = 50, user: User = Depends(get_current_user)):
    logs = await TaskService.get_task_logs(task_id, limit)
    return ApiResponse.success(data=logs)


@task_router.get("/tasks/logs/all")
async def get_all_logs(limit: int = 100, user: User = Depends(get_current_user)):
    logs = await TaskService.get_all_logs(limit)
    return ApiResponse.success(data=logs)
