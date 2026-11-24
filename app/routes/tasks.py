import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_task_service
from app.models import Task, TaskCreate, TaskPage, TaskStatus
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["tasks"])
Service = Annotated[TaskService, Depends(get_task_service)]


@router.get("")
def list_tasks(
    service: Service,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: TaskStatus | None = None,
) -> TaskPage:
    logger.info("list_tasks limit=%s offset=%s status=%s", limit, offset, status)
    return service.list_tasks(limit=limit, offset=offset, status=status)


@router.get("/{task_id}")
def get_task(task_id: int, service: Service) -> Task:
    return service.get_task(task_id)


@router.post("", status_code=201)
def create_task(data: TaskCreate, service: Service) -> Task:
    return service.create_task(data)
