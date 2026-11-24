# Closed tasks appear when filtering for open tasks

**Request:** `GET /tasks?status=open`

**Expected:** only tasks with status `open`.

**Actual:** closed tasks are in the list too. No error is returned.

**Started:** after the status filter was merged. All checks passed on that change.
