import logging
import sqlite3

from app.models import Task, TaskCreate, TaskStatus

logger = logging.getLogger(__name__)


class TaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, limit: int, offset: int, status: TaskStatus | None = None) -> list[Task]:
        sql, params = "SELECT * FROM tasks", []
        if status is not None:
            sql += " WHERE status = ?"
            params.append(status.value)
        sql += " ORDER BY id LIMIT ? OFFSET ?"
        params += [limit, offset]
        logger.info("query sql=%r params=%s", sql, params)
        return [Task(**dict(row)) for row in self._conn.execute(sql, params)]

    def count(self, status: TaskStatus | None = None) -> int:
        sql, params = "SELECT COUNT(*) FROM tasks", []
        if status is not None:
            sql += " WHERE status = ?"
            params.append(status.value)
        return self._conn.execute(sql, params).fetchone()[0]

    def get(self, task_id: int) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", [task_id]).fetchone()
        return Task(**dict(row)) if row else None

    def create(self, data: TaskCreate) -> Task:
        cursor = self._conn.execute(
            "INSERT INTO tasks (project_id, title, priority) VALUES (?, ?, ?)",
            [data.project_id, data.title, data.priority],
        )
        self._conn.commit()
        return self.get(cursor.lastrowid)
