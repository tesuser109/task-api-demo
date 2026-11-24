from fastapi import Request

from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_service import ProjectService
from app.services.task_service import TaskService


def get_task_service(request: Request) -> TaskService:
    conn = request.app.state.conn
    return TaskService(TaskRepository(conn), ProjectRepository(conn))


def get_project_service(request: Request) -> ProjectService:
    return ProjectService(ProjectRepository(request.app.state.conn))
