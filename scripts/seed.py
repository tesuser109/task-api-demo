import os

from app.db import connect, seed

if __name__ == "__main__":
    seed(connect(os.getenv("TASK_DB", "tasks.db")))
    print("Seeded synthetic projects and tasks")
