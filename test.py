
from app.service.code_executor import execute_code

workspace_path = (
    "/home/sonu/DEV AI/devpilot-workspace/"
    ".devpilot/workspaces/sample-project-9510158bbf4f"
)

result = execute_code(
    workspace_path=workspace_path,
    command=[
        "python",
        "-m",
        "pytest",
        "-q",
        "test_devpilot_runner.py"
    ],
    timeout=60
)

print("Status:", result["status"])
print("Exit code:", result["exit_code"])
print("Output:", result["stdout"])
print("Error:", result["stderr"])
