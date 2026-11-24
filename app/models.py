from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(BaseModel):
    id: int
    project_id: int
    title: str
    status: TaskStatus
    priority: Priority


class TaskCreate(BaseModel):
    project_id: int
    title: str = Field(min_length=1, max_length=120)
    priority: Priority = Priority.MEDIUM


class TaskPage(BaseModel):
    items: list[Task]
    total: int


class Project(BaseModel):
    id: int
    name: str
    archived: bool


class ProjectPage(BaseModel):
    items: list[Project]
    total: int


class ListTasksArgs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    status: Literal["open"]
    limit: int = Field(ge=1, le=100)


class SummaryTask(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: int
    title: str
    reason: str


class TaskSummary(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    headline: str
    total_open: int
    top_tasks: list[SummaryTask]
