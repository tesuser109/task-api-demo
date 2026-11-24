# Resolution: closed tasks in the open filter

**Root cause:** `TaskService.list_tasks` accepted `status` but did not pass it to the repository. Both the page query and the total ignored it.

**Why checks passed:** the original test only checked that open tasks were present, not that others were absent.

**Change:** pass `status` to both repository calls in `app/services/task_service.py`.

**Evidence:** the reported test passes. New tests cover every status, the total, the absent filter and pagination.

**Limits:** filtering accepts one status at a time.
