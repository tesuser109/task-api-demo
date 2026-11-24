"""Read-only issue tracker over MCP. Synthetic issues only."""

import json
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

ISSUES = json.loads(Path(__file__).with_name("issues.json").read_text(encoding="utf-8"))
server = MCPServer("issue-tracker")


@server.tool()
def list_issues() -> list[dict]:
    """List open issues by number and title."""
    return [{"number": i["number"], "title": i["title"]} for i in ISSUES if i["state"] == "open"]


@server.tool()
def get_issue(number: int) -> dict:
    """Read one issue with its acceptance criteria."""
    for issue in ISSUES:
        if issue["number"] == number:
            return issue
    raise ToolError(f"Issue {number} does not exist")


if __name__ == "__main__":
    server.run("stdio")
