"""
OpsBrain Web — Scheduled Task Service

定时任务业务逻辑层
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session
from ..models import ScheduledTask, TaskExecutionLog
from ..utils.response import ApiResponse, NotFoundException


class TaskService:
    @staticmethod
    async def get_all_tasks() -> List[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(ScheduledTask).order_by(ScheduledTask.created_at.desc())
            )
            tasks = result.scalars().all()
            return [task.to_dict() for task in tasks]

    @staticmethod
    async def get_task_by_id(task_id: str) -> dict:
        async with async_session() as session:
            result = await session.execute(
                select(ScheduledTask).where(ScheduledTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                raise NotFoundException("任务不存在")
            return task.to_dict()

    @staticmethod
    async def create_task(data: dict) -> dict:
        async with async_session() as session:
            task = ScheduledTask(
                name=data["name"],
                target_agent_id=data["target_agent_id"],
                target_agent_name=data.get("target_agent_name", ""),
                task_content=data.get("task_content", ""),
                start_time=data.get("start_time", ""),
                time_config=json.dumps(data.get("time_config", {})),
                time_mode=data.get("time_mode", "simple"),
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task.to_dict()

    @staticmethod
    async def update_task(task_id: str, data: dict) -> dict:
        async with async_session() as session:
            result = await session.execute(
                select(ScheduledTask).where(ScheduledTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                raise NotFoundException("任务不存在")

            if "name" in data:
                task.name = data["name"]
            if "target_agent_id" in data:
                task.target_agent_id = data["target_agent_id"]
            if "target_agent_name" in data:
                task.target_agent_name = data["target_agent_name"]
            if "task_content" in data:
                task.task_content = data["task_content"]
            if "start_time" in data:
                task.start_time = data["start_time"]
            if "time_config" in data:
                task.time_config = json.dumps(data["time_config"])
            if "time_mode" in data:
                task.time_mode = data["time_mode"]
            if "is_enabled" in data:
                task.is_enabled = data["is_enabled"]

            await session.commit()
            await session.refresh(task)
            return task.to_dict()

    @staticmethod
    async def delete_task(task_id: str) -> None:
        async with async_session() as session:
            result = await session.execute(
                select(ScheduledTask).where(ScheduledTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                raise NotFoundException("任务不存在")

            await session.execute(
                delete(TaskExecutionLog).where(TaskExecutionLog.task_id == task_id)
            )
            await session.delete(task)
            await session.commit()

    @staticmethod
    async def toggle_task(task_id: str, is_enabled: bool) -> dict:
        async with async_session() as session:
            result = await session.execute(
                select(ScheduledTask).where(ScheduledTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                raise NotFoundException("任务不存在")

            task.is_enabled = is_enabled
            await session.commit()
            await session.refresh(task)
            return task.to_dict()

    @staticmethod
    async def create_execution_log(task: dict, status: str = "running", error_message: str = "") -> dict:
        async with async_session() as session:
            log_entry = TaskExecutionLog(
                task_id=task["id"],
                task_name=task["name"],
                target_agent_id=task["target_agent_id"],
                target_agent_name=task["target_agent_name"],
                task_content=task["task_content"],
                status=status,
                error_message=error_message,
            )
            session.add(log_entry)
            await session.commit()
            await session.refresh(log_entry)
            return log_entry.to_dict()

    @staticmethod
    async def update_execution_log(log_id: str, status: str, error_message: str = "") -> dict:
        async with async_session() as session:
            result = await session.execute(
                select(TaskExecutionLog).where(TaskExecutionLog.id == log_id)
            )
            log_entry = result.scalar_one_or_none()
            if not log_entry:
                raise NotFoundException("执行日志不存在")

            log_entry.status = status
            log_entry.error_message = error_message
            await session.commit()
            await session.refresh(log_entry)
            return log_entry.to_dict()

    @staticmethod
    async def update_task_execution(task_id: str) -> None:
        async with async_session() as session:
            result = await session.execute(
                select(ScheduledTask).where(ScheduledTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task:
                task.last_executed_at = datetime.utcnow()
                task.execution_count += 1
                await session.commit()

    @staticmethod
    async def get_task_logs(task_id: str, limit: int = 50) -> List[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(TaskExecutionLog)
                .where(TaskExecutionLog.task_id == task_id)
                .order_by(TaskExecutionLog.created_at.desc())
                .limit(limit)
            )
            logs = result.scalars().all()
            return [log.to_dict() for log in logs]

    @staticmethod
    async def get_all_logs(limit: int = 100) -> List[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(TaskExecutionLog)
                .order_by(TaskExecutionLog.created_at.desc())
                .limit(limit)
            )
            logs = result.scalars().all()
            return [log.to_dict() for log in logs]
