from app.core.config import settings
import sys
from pathlib import Path


MCP_SERVER_CONFIGS = {
    "github": {
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {
            "Authorization": (
                f"Bearer {settings.GITHUB_TOKEN.get_secret_value()}"
            ),
            "X-MCP-Readonly": "true",
        },
    },

    "terminal": {
    "command": sys.executable,
    "args": [
            str(Path(__file__).with_name("terminal_server.py"))
        ],
    "env": {
        "DEVPILOT_TERMINAL_ROOT": (
        "/home/sonu/DEV AI/devpilot-workspace"
            ),
        },
    },
}