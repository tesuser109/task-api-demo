from app.errors import NotFoundError
from app.models import Task, TaskCreate, TaskPage, TaskStatus
from app.repositories.project_repository import ProjectRepository
from app.repositories.task_repository import TaskRepository


class TaskService:
    def __init__(self, tasks: TaskRepository, projects: ProjectRepository) -> None:
        self._tasks = tasks
        self._projects = projects

    def list_tasks(self, limit: int, offset: int, status: TaskStatus | None = None) -> TaskPage:
        return TaskPage(
            items=self._tasks.list(limit=limit, offset=offset, status=status),
            total=self._tasks.count(status=status),
        )

    def get_task(self, task_id: int) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} does not exist")
        return task

    def create_task(self, data: TaskCreate) -> Task:
        if not self._projects.exists(data.project_id):
            raise NotFoundError(f"Project {data.project_id} does not exist")
        return self._tasks.create(data)
