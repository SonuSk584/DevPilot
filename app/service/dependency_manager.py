import hashlib
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path


DOCKER_IMAGE = "python:3.12-slim"
MAX_INSTALL_TIMEOUT = 300
VENV_NAME = ".devpilot-venv"
HASH_FILE = ".req-hash"
REQUIREMENT_NAMES = ("requirements.txt", "requirement.txt")
MAX_REQ_BYTES = 100_000

# Fixed application code, not user-supplied shell input.
# The requirements file name is passed as an argument (sys.argv[1]).
INSTALL_SCRIPT = (
    "import subprocess, sys\n"
    "venv = '/workspace/.devpilot-venv'\n"
    "req = '/workspace/' + sys.argv[1]\n"
    "subprocess.run([sys.executable, '-m', 'venv', venv], check=True)\n"
    "subprocess.run([venv + '/bin/python', '-m', 'pip', 'install', "
    "'--no-cache-dir', '--disable-pip-version-check', '-r', req], "
    "check=True)\n"
)


def _to_text(value) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""


def _find_requirements(root: Path) -> Path | None:
    for name in REQUIREMENT_NAMES:
        candidate = root / name
        if candidate.is_symlink():
            raise ValueError("Symbolic requirements files are not allowed")
        if candidate.is_file():
            return candidate
    return None


def _requirements_hash(requirements_file: Path) -> str:
    digest = hashlib.sha256()
    digest.update(DOCKER_IMAGE.encode())
    digest.update(requirements_file.read_bytes())
    return digest.hexdigest()


def install_project_dependencies(
    workspace_path: str,
    timeout: int = MAX_INSTALL_TIMEOUT,
) -> dict:
    """
    Build .devpilot-venv inside the workspace using a Docker container.

    Statuses: success, cached, skipped, failed, timeout.
    - cached:  venv already exists and the requirements file is unchanged.
    - skipped: the workspace has no requirements file.
    Network access is enabled only for this installation step.
    """

    root = Path(workspace_path).resolve()

    if not root.is_dir():
        raise FileNotFoundError("Workspace does not exist")

    if timeout < 1 or timeout > MAX_INSTALL_TIMEOUT:
        raise ValueError(
            f"Timeout must be between 1 and {MAX_INSTALL_TIMEOUT} seconds"
        )

    requirements_file = _find_requirements(root)

    if requirements_file is None:
        return {
            "status": "skipped",
            "message": "No requirements file found "
                       f"(looked for {', '.join(REQUIREMENT_NAMES)})",
            "venv_path": None,
        }

    if requirements_file.stat().st_size > MAX_REQ_BYTES:
        raise ValueError("Requirements file exceeds the 100 KB limit")

    venv_path = root / VENV_NAME
    current_hash = _requirements_hash(requirements_file)
    hash_path = venv_path / HASH_FILE

    # Reuse the venv if nothing changed, otherwise rebuild it.
    if venv_path.exists():
        python_ok = (venv_path / "bin" / "python").exists()
        hash_ok = (
            hash_path.is_file()
            and hash_path.read_text().strip() == current_hash
        )
        if python_ok and hash_ok:
            return {
                "status": "cached",
                "message": "Existing environment is up to date",
                "venv_path": str(venv_path),
            }
        shutil.rmtree(venv_path, ignore_errors=True)

    container_name = f"devpilot-install-{uuid.uuid4().hex[:12]}"

    docker_command = [
        "docker", "run", "--rm",
        "--name", container_name,
        "--network", "bridge",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--tmpfs", "/tmp:rw,nosuid,size=128m",
        "-e", "HOME=/tmp",
        "--mount", f"type=bind,source={root},target=/workspace",
        "--workdir", "/workspace",
        DOCKER_IMAGE,
        "python", "-c", INSTALL_SCRIPT, requirements_file.name,
    ]

    start_time = time.monotonic()

    try:
        result = subprocess.run(
            docker_command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        duration = round(time.monotonic() - start_time, 3)

        if result.returncode == 0:
            hash_path.write_text(current_hash)
            return {
                "status": "success",
                "exit_code": 0,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
                "duration_seconds": duration,
                "venv_path": str(venv_path),
            }

        # Don't leave a half-built environment behind.
        shutil.rmtree(venv_path, ignore_errors=True)
        return {
            "status": "failed",
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-3000:],
            "duration_seconds": duration,
            "venv_path": None,
        }

    except subprocess.TimeoutExpired as error:
        cleanup = subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        shutil.rmtree(venv_path, ignore_errors=True)
        return {
            "status": "timeout",
            "exit_code": None,
            "stdout": _to_text(error.stdout)[-2000:],
            "stderr": _to_text(error.stderr)[-3000:]
                      or "Dependency installation timed out",
            "duration_seconds": round(time.monotonic() - start_time, 3),
            "venv_path": None,
            "container_cleanup_success": cleanup.returncode == 0,
        }

    except FileNotFoundError:
        raise RuntimeError("Docker executable was not found")

    except OSError as error:
        raise RuntimeError(
            f"Could not start Docker installation: {error}"
        ) from error