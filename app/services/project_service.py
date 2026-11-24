from app.models import ProjectPage
from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, projects: ProjectRepository) -> None:
        self._projects = projects

    def list_projects(self, archived: bool | None = None) -> ProjectPage:
        items = self._projects.list(archived=archived)
        return ProjectPage(items=items, total=len(items))
