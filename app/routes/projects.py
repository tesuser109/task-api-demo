from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_project_service
from app.models import ProjectPage
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(
    service: Annotated[ProjectService, Depends(get_project_service)],
    archived: bool | None = None,
) -> ProjectPage:
    return service.list_projects(archived=archived)
