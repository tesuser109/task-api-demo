import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium'
);
"""

PROJECTS = [(1, "Harbor Portal", 0), (2, "Lantern Mobile", 0), (3, "Old Intranet", 1)]

TASKS = [
    (1, 1, "Fix login redirect loop", "open", "high"),
    (2, 1, "Update password help text", "closed", "low"),
    (3, 2, "Crash when opening an empty inbox", "open", "high"),
    (4, 2, "Add dark mode toggle", "in_progress", "medium"),
    (5, 1, "Document the export endpoint", "open", "medium"),
    (6, 2, "Remove unused icons", "closed", "low"),
    (7, 1, "Migrate avatar storage", "in_progress", "high"),
    (8, 2, "Tidy settings screen spacing", "open", "low"),
    (9, 3, "Archive intranet pages", "closed", "medium"),
]


def connect(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def seed(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM tasks")
    conn.execute("DELETE FROM projects")
    conn.executemany("INSERT INTO projects VALUES (?, ?, ?)", PROJECTS)
    conn.executemany("INSERT INTO tasks VALUES (?, ?, ?, ?, ?)", TASKS)
    conn.commit()
