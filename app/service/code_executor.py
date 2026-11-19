
import os
import subprocess
import time
from pathlib import Path
import uuid

DOCKER_IMAGE = "python:3.12-slim"

DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 120

ALLOWED_COMMANDS = {"python", "python3"}


def execute_code(
    workspace_path: str,
    command: list[str],
    timeout: int = DEFAULT_TIMEOUT
) -> dict:
    """
    Execute an allowed Python command inside a restricted Docker container.

    Automatically uses the project's virtual environment if available.
    The isolated workspace is mounted at /workspace.
    """

    root = Path(workspace_path).resolve()

    if not root.is_dir():
        raise ValueError("Workspace must be an existing directory")

    if not isinstance(command, list) or not command:
        raise ValueError("A Python command must be provided")

    if not all(isinstance(arg, str) for arg in command):
        raise ValueError("Command arguments must be strings")

    if command[0] not in ALLOWED_COMMANDS:
        raise ValueError("Only python and python3 commands are allowed")

    if timeout < 1 or timeout > MAX_TIMEOUT:
        raise ValueError(
            f"Timeout must be between 1 and {MAX_TIMEOUT} seconds"
        )

    # Detect project virtual environment.
    venv_python = root / ".devpilot-venv" / "bin" / "python"

    if venv_python.is_file() or venv_python.is_symlink():
        python_executable = "/workspace/.devpilot-venv/bin/python"
    else:
        python_executable = command[0]

    # Replace the requested interpreter with the selected interpreter.
    execution_command = [
        python_executable,
        *command[1:]
    ]

    uid = os.getuid()
    gid = os.getgid()

    container_name = f"devpilot-{uuid.uuid4().hex[:12]}"

    docker_command = [
        "docker",
        "run",
        "--rm",
        "--name", container_name,
        "--network", "none",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", f"{uid}:{gid}",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
        "--mount",
        f"type=bind,source={root},target=/workspace",
        "--workdir", "/workspace",
        DOCKER_IMAGE,
        *execution_command
    ]

    start_time = time.monotonic()

    try:
        result = subprocess.run(
            docker_command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

        duration = round(time.monotonic() - start_time, 3)

        return {
            "command": execution_command,
            "status": "success" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": duration,
            "timed_out": False
        }

    except subprocess.TimeoutExpired as error:
        duration = round(time.monotonic() - start_time, 3)

        cleanup_result = subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )

        return {
            "command": execution_command,
            "status": "timeout",
            "exit_code": None,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "",
            "duration_seconds": duration,
            "timed_out": True,
            "container_cleanup_success": cleanup_result.returncode == 0
        }

    except FileNotFoundError:
        raise RuntimeError("Docker executable was not found")

    except OSError as error:
        raise RuntimeError(
            f"Could not start Docker execution: {error}"
        ) from error
