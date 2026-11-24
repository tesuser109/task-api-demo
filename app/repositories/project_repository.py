import sqlite3

from app.models import Project


class ProjectRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, archived: bool | None = None) -> list[Project]:
        sql, params = "SELECT * FROM projects", []
        if archived is not None:
            sql += " WHERE archived = ?"
            params.append(int(archived))
        rows = self._conn.execute(sql + " ORDER BY id", params)
        return [Project(**dict(row)) for row in rows]

    def exists(self, project_id: int) -> bool:
        row = self._conn.execute("SELECT 1 FROM projects WHERE id = ?", [project_id]).fetchone()
        return row is not None
