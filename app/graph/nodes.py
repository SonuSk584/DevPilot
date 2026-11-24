import json
import re
import shlex
from pathlib import Path
from app.core.config import settings
from app.service.dependency_manager import install_project_dependencies
from langchain_core.messages import SystemMessage, HumanMessage

from app.graph.state import DevPilotState
from app.service.patch_engine import apply_code_proposal
from app.service.diff_manager import get_workspace_diff
from app.service.code_executor import execute_code
from langgraph.types import interrupt
from app.service.change_applier import apply_approved_changes
from app.service.rag.rag_pipeline import retrieve_relevant_chunks

from langchain.agents import create_agent
from app.mcp.client_manager import MCPClientManager
from langgraph.prebuilt import ToolNode
from app.mcp.registry import get_mcp_tools
from app.service.llm import get_llm
from app.prompt.repository_analyst import repository_analyst_prompt
from app.service.mcp_agent import request_mcp_tools
from langchain_core.messages import ToolMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from app.service.mcp_agent import (
    request_mcp_tools,
    AGENT_MCP_TOOLS,
)


from app.service.llm import (
    get_planner_chain,
    get_repository_analyst_chain,
    get_coder_chain,
    get_reviewer_chain,
    get_retry_intelligence_chain,
)
from app.service.rag.repository_indexer import index_repository

ANALYST_MCP_SERVERS = {"github"}


ROUTE_SMOKE_SCRIPT = (
    "import sys, importlib\n"
    "app = getattr(importlib.import_module(sys.argv[1]), 'app', None)\n"
    "if app is None:\n"
    "    print('no app object found'); sys.exit(0)\n"
    "from fastapi.testclient import TestClient\n"
    "client = TestClient(app)\n"
    "skip = {'/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc'}\n"
    "failed = 0\n"
    "for route in app.routes:\n"
    "    path = getattr(route, 'path', '')\n"
    "    if 'GET' in (getattr(route, 'methods', None) or ()) and '{' not in path and path not in skip:\n"
    "        r = client.get(path)\n"
    "        print('GET', path, r.status_code, r.text[:200])\n"
    "        failed |= r.status_code >= 500\n"
    "sys.exit(1 if failed else 0)\n"
)
# ---------------------------------------------------------------------------
# Token-budget helpers
# Rough rule: 1 token ~= 4 characters. Groq on_demand limit for
# gpt-oss-120b is 8000 tokens/minute PER REQUEST, so every prompt must stay
# well under that. Tune these budgets if you still hit limits.
# ---------------------------------------------------------------------------

MAX_REPO_CONTEXT_CHARS = 100_000
MAX_INVENTORY_CHARS = 2000
MAX_PROPOSAL_CHARS = 5000
MAX_DIFF_CHARS = 3000
MAX_EXECUTION_CHARS = 1500
MAX_ATTEMPTS_IN_RETRY = 3
PYTEST_NO_TESTS_EXIT_CODE = 5
TEST_TIMEOUT = 60
SMOKE_TIMEOUT = 30



def truncate(value, max_chars: int = 2000, tail_bias: float = 0.5) -> str:
    """
    Convert any value to a string and, if too long, keep the head and tail.
    tail_bias is the fraction of the budget given to the END of the text
    (test errors usually appear at the end).
    """
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, default=str)

    if len(text) <= max_chars:
        return text

    tail = int(max_chars * tail_bias)
    head = max_chars - tail
    return f"{text[:head]}\n...[truncated]...\n{text[-tail:]}"



def extract_failures(
    execution_result: dict,
    max_chars: int = MAX_EXECUTION_CHARS
) -> str:
    """
    Summarize execution results while preserving both successful
    verification evidence and failures.

    This information is consumed by the Reviewer, Coder,
    Retry Intelligence, and attempt recorder.
    """

    if not execution_result:
        return "No execution result available."

    parts = [
        f"Overall status: {execution_result.get('status', 'unknown')}",
        f"Verification type: {execution_result.get('verification', 'unknown')}",
        f"Total checks: {execution_result.get('total_tests', 'unknown')}",
        f"Passed: {execution_result.get('passed', 'unknown')}",
        f"Failed: {execution_result.get('failed', 'unknown')}",
    ]

    if execution_result.get("message"):
        parts.append(f"Message: {execution_result['message']}")

    results = execution_result.get("results", [])

    if not results:
        parts.append("No individual command results available.")

    for index, item in enumerate(results, start=1):

        status = item.get("status", "unknown")

        output = (
            item.get("stdout")
            or item.get("stderr")
            or item.get("error")
            or item.get("output")
            or ""
        )

        parts.append(
            f"\nCheck {index}:"
            f"\nStatus: {status}"
            f"\nCommand: {item.get('command', 'unknown')}"
            f"\nOutput: {truncate(str(output), 500, tail_bias=0.7)}"
        )

    summary = truncate(
    "\n".join(parts),
    max_chars,
    tail_bias=0.6
)

    print("\n[EXECUTION SUMMARY]")
    print(summary)

    return summary



# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def planner_node(state: DevPilotState):
    print("[DEBUG] Planner received:", list(state.keys()))

    planner = get_planner_chain()
    inputs = {
    "task": state["task"],
    "file_inventory": state["file_inventory"],
    "repository_context": state["repository_context"],
}

    try:
        plan = await planner.ainvoke(inputs)
    except Exception as e:
        print(f"[PLANNER] First attempt failed: {e}")
        plan = await planner.ainvoke(inputs)  # one retry, then let it raise

    print(plan.model_dump_json(indent=2))  # remove after testing

    return {
        "plan": plan,  # compact string for downstream prompts
        "plan_obj": plan,                # object for the scope check
    }


async def repository_analyst_node(state: DevPilotState):
    print("[DEBUG] Analyst received:", list(state.keys()))

    analyst = get_repository_analyst_chain()

    # Retrieve relevant code chunks from the indexed workspace.
    repository_id = str(
        Path(state["workspace_path"]).resolve()
    )

    try:
        relevant_chunks = retrieve_relevant_chunks(
            query=(
                state["task"]
                + "\n"
                + state["plan"].model_dump_json()
            ),
            repository_id=repository_id,
            top_k=5,
        )

        print(
            f"[RAG] Analyst retrieved {len(relevant_chunks)} relevant chunks."
        )

        if relevant_chunks:
            rag_context = "\n\n".join(
                (
                    f"FILE: {chunk['file_path']}\n"
                    f"SYMBOL: {chunk.get('symbol_name') or 'N/A'}\n"
                    f"LINES: {chunk['line_start']}-{chunk['line_end']}\n"
                    f"CODE:\n{chunk['content']}"
                )
                for chunk in relevant_chunks
            )
        else:
            rag_context = state["repository_context"]
            print("[RAG] No chunks found. Using original repository context.")

    except Exception as e:
        print(f"[RAG] Retrieval failed: {e}")
        rag_context = state["repository_context"]

    mcp_context = "\n\n".join(
        str(message.content)
        for message in state.get("messages", [])
        if isinstance(message, ToolMessage)
    )

    if mcp_context:
        rag_context += (
            "\n\nEXTERNAL MCP RESEARCH RESULTS:\n"
            + mcp_context
        )
    inputs = {
        "task": state["task"],
        "plan": state["plan"].model_dump_json(),
        "file_inventory": state["file_inventory"],
        "repository_context": truncate(
            rag_context, MAX_REPO_CONTEXT_CHARS
        ),
    }

    try:
        result = await analyst.ainvoke(inputs)
    except Exception as e:
        print(f"[ANALYST] First attempt failed: {e}")
        result = await analyst.ainvoke(inputs)

    output = {"repository_analysis": result}

    if state.get("messages"):
        output["messages"] = [
            RemoveMessage(id=REMOVE_ALL_MESSAGES)
        ]

    return output



async def coder_node(state: DevPilotState):

    coder = get_coder_chain()

    # Retrieve relevant code chunks for the Coder.
    repository_id = str(
        Path(state["workspace_path"]).resolve()
    )
    combined_context = state["repository_context"]
    try:
        relevant_chunks = retrieve_relevant_chunks(
            query=(
                state["task"]
                + "\n"
                + state["plan"].model_dump_json()
                + "\n"
                + state["repository_analysis"].model_dump_json()
                + "\n"
                + state.get("review_feedback", "")
            ),
            repository_id=repository_id,
            top_k=5,
        )

        print(
            f"[RAG] Coder retrieved {len(relevant_chunks)} relevant chunks."
        )

        
        base_context = state["repository_context"]

        if relevant_chunks:
            rag_context = "\n\n".join(
                (
                    f"FILE: {chunk['file_path']}\n"
                    f"SYMBOL: {chunk.get('symbol_name') or 'N/A'}\n"
                    f"LINES: {chunk['line_start']}-{chunk['line_end']}\n"
                    f"CODE:\n{chunk['content']}"
                )
                for chunk in relevant_chunks
            )

            combined_context = (
                "COMPLETE ORIGINAL REPOSITORY CONTEXT:\n"
                f"{base_context}\n\n"
                "ADDITIONAL RAG RETRIEVAL CONTEXT:\n"
                f"{rag_context}"
            )
        else:
            combined_context = base_context
            print("[RAG] No chunks found. Using original repository context.")


    except Exception as e:
        print(f"[RAG] Coder retrieval failed: {e}")
        combined_context = state["repository_context"]

    
    coder_inputs = {
        "task": state["task"],
        "execution_plan": state["plan"].model_dump_json(),
        "allowed_files": state["plan"].allowed_files,
        "repository_analysis": (
            state["repository_analysis"].model_dump_json()
        ),
        "repository_context": truncate(
            combined_context, MAX_REPO_CONTEXT_CHARS
        ),
        "review_feedback": truncate(
            state.get(
                "review_feedback",
                "No previous review feedback. This is the initial proposal"
            ),
            1500
        ),
        "file_inventory": truncate(
            state["file_inventory"], MAX_INVENTORY_CHARS
        ),
        "previous_diff": truncate(
            state.get("diff_result", {}), MAX_DIFF_CHARS
        ),
        "previous_execution_result": extract_failures(
            state.get("execution_result", {})
        ),
        "retry_analysis": (
            truncate(state["retry_analysis"].model_dump_json(), 2000)
            if state.get("retry_analysis")
            else "No retry analysis available. This is the initial attempt."
        ),
    }

    log_payload_sizes("CODER INPUT", coder_inputs)

    print("[DIAGNOSTIC] Coder invocation starting...")

    try:
        result = await coder.ainvoke(coder_inputs)

        print("[DIAGNOSTIC] Coder invocation completed.")
        print(
            "[DIAGNOSTIC] Coder proposal size:",
            len(result.model_dump_json()),
            "characters"
        )
        print(
            "[DIAGNOSTIC] Proposed files:",
            [change.file_path for change in result.changes]
        )

    except Exception as exc:
        print(f"[DIAGNOSTIC] Coder invocation failed: {type(exc).__name__}")
        print(f"[DIAGNOSTIC] Error: {str(exc)[:2000]}")
        raise


    print("[DEBUG] Coder received:", list(state.keys()))

    return {
        "code_proposal": result,
        "revision_count": state.get("revision_count", 0) + 1
    }



async def reviewer_node(state: DevPilotState):

    reviewer = get_reviewer_chain()

    result = await reviewer.ainvoke({

        "task": state["task"],
        "plan": state["plan"].model_dump_json(),

        "repository_analysis": (
            state["repository_analysis"].model_dump_json()
        ),

        "repository_context": truncate(
            state["repository_context"], MAX_REPO_CONTEXT_CHARS
        ),

        "code_proposal": truncate(
            state["code_proposal"].model_dump_json(), MAX_PROPOSAL_CHARS
        ),

        "patch_result": truncate(
            state.get("patch_result", {}), 500
        ),

        "diff_result": truncate(
            state.get("diff_result", {}), MAX_DIFF_CHARS
        ),

        "execution_result": extract_failures(
            state.get("execution_result", {})
        )
    })

    # Execution results are intentionally NOT embedded here anymore.
    # The coder already receives them separately as
    # previous_execution_result, so including them would duplicate them.

    feedback = (
        f"Review approved: {result.approved}\n"
        f"Review summary: {result.summary}\n"
        f"Findings: "
        f"{[finding.model_dump() for finding in result.findings]}\n"
        f"Required changes: {result.required_changes}\n"
        f"Recommended tests: {result.tests_to_run}"
        )


    return {
        "review_result": result,
        "review_feedback": feedback,
        "mcp_round_count": 0,
    }


def patch_engine_node(state: DevPilotState):
    """
    Apply the coder's proposal to the isolated workspace.
    """

    workspace_path = state["workspace_path"]
    proposal = state["code_proposal"]

    try:
        results = apply_code_proposal(
            workspace_path=workspace_path,
            proposal=proposal
        )

        return {
            "patch_result": {
                "status": "success",
                "results": results
            }
        }

    except Exception as error:
        return {
            "patch_result": {
                "status": "failed",
                "error": str(error)
            }
        }


def diff_manager_node(state: DevPilotState):
    """
    Inspect the workspace after applying code changes.
    """

    patch_result = state["patch_result"]

    if patch_result["status"] != "success":
        return {
            "diff_result": {
                "status": "skipped",
                "message": "Patch application failed."
            }
        }

    try:
        result = get_workspace_diff(
            workspace_path=state["workspace_path"]
        )

        return {
    "diff_result": {
        "status": "success",
        **result
    }
}

    except Exception as error:
        return {
            "diff_result": {
                "status": "failed",
                "error": str(error)
            }
        }



def repository_reindex_node(state: DevPilotState) -> dict:
    """
    Refresh the repository's RAG index before retrying code generation.
    """

    repository_path = state.get("workspace_path")

    if not repository_path:
        raise ValueError("Workspace path is missing from workflow state.")

    result = index_repository(repository_path)

    print(
        f"[RAG] Repository re-indexed: "
        f"{result['stored_chunks']} chunks stored."
    )

    return {
        "rag_index_result": result,
    }


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def log_payload_sizes(label: str, payload: dict) -> None:
    print(f"\n[DIAGNOSTIC] {label}")

    total_chars = 0

    for key, value in payload.items():
        if isinstance(value, str):
            size = len(value)
        else:
            size = len(json.dumps(value, default=str))

        total_chars += size
        print(f"  {key}: {size:,} characters")

    print(f"  TOTAL: {total_chars:,} characters")



def _changed_python_files(diff_result: dict) -> list[str]:
    files = diff_result.get("files", [])

    return [
        f["file_path"]
        for f in files
        if f["file_path"].endswith(".py")
        and f["change_type"] != "deleted"
    ]


def _smoke_commands(diff_result: dict) -> list[list[str]]:
    """
    Used when no real tests ran. Syntax-check every changed Python file,
    then import the changed top-level modules. -B avoids writing
    __pycache__ into the workspace.
    """
    py_files = _changed_python_files(diff_result)
    if not py_files:
        return []

    commands = [[
        "python", "-B", "-c",
        "import ast, sys\n"
        "for f in sys.argv[1:]:\n"
        "    ast.parse(open(f).read(), f)\n"
        "print('syntax ok')",
        *py_files,
    ]]

    modules = [
        Path(f).stem for f in py_files
        if "/" not in f
        and Path(f).stem.isidentifier()
        and not Path(f).stem.startswith("test_")
    ]
    for module in modules:
        commands.append(["python", "-B", "-c", ROUTE_SMOKE_SCRIPT, module])
    return commands

def _requirement_names(workspace_path: str) -> set[str]:
    for name in ("requirements.txt", "requirement.txt"):
        path = Path(workspace_path) / name
        if path.is_file():
            names = set()
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    pkg = re.split(r"[<>=!~\[;\s]", line, maxsplit=1)[0]
                    names.add(pkg.lower().replace("-", "_"))
            return names
    return set()


def _missing_module(result: dict) -> str | None:
    text = (result.get("stdout") or "") + (result.get("stderr") or "")
    match = re.search(r"No module named '?([\w.\-]+)'?", text)
    return match.group(1).split(".")[0] if match else None


def _failure_kind(results: list[dict], workspace_path: str) -> str | None:
    """
    A missing module is an ENVIRONMENT problem only if it is a declared
    dependency. Otherwise the Coder imported something that doesn't exist,
    which is a code problem.
    """
    declared = _requirement_names(workspace_path)
    for result in results:
        if result.get("status") == "success":
            continue
        module = _missing_module(result)
        if module:
            if module.lower().replace("-", "_") in declared:
                return "environment_dependency"
            return "code_import_error"
    return None


# --------------------------------------------------
# Node
# --------------------------------------------------

def code_executor_node(state: "DevPilotState"):
    """
    Install dependencies, then run the proposed test commands inside the
    restricted Docker container. If no real tests run, fall back to a
    smoke check so a correct change isn't reported as a failure.
    """

    patch_result = state["patch_result"]

    if patch_result["status"] != "success":
        return {
            "execution_result": {
                "status": "skipped",
                "message": "Patch application failed. Tests were not executed."
            }
        }

    diff_result = state.get("diff_result") or {}

    if diff_result.get("status") != "success":
        return {
            "execution_result": {
                "status": "skipped",
                "message": "Diff generation failed. Tests were not executed."
            }
        }

    workspace_path = state["workspace_path"]


    # 1. Build the sandbox environment, unless a prebuilt image is used.
    if not settings.USE_PREBUILT_IMAGE:
        install = install_project_dependencies(workspace_path)

        if install["status"] in ("failed", "timeout"):
            return {
                "execution_result": {
                    "status": "environment_error",
                    "stage": "install",
                    "message": "Dependency installation failed.",
                    "detail": install,
                }
            }
    # success, cached and skipped all continue.

    # 2. Collect the commands to run.
    test_commands = state["code_proposal"].tests_to_run or []

    results = []

    for test_command in test_commands:
        try:
            parts = shlex.split(test_command)
        except ValueError:
            results.append({
                "command": test_command,
                "status": "rejected",
                "error": "Command could not be parsed."
            })
            continue

        # Normalize bare "pytest ..." into "python -m pytest ...".
        if parts and parts[0] == "pytest":
            parts = ["python", "-m", "pytest"] + parts[1:]

        if not parts or parts[0] not in ("python", "python3"):
            results.append({
                "command": test_command,
                "status": "rejected",
                "error": "Only Python commands are allowed."
            })
            continue

        # Keep pytest from writing cache and bytecode into the workspace.
        if parts[1:3] == ["-m", "pytest"]:
            parts = (
                [parts[0], "-B", "-m", "pytest", "-p", "no:cacheprovider"]
                + parts[3:]
            )

        try:
            result = execute_code(
                workspace_path=workspace_path,
                command=parts,
                timeout=TEST_TIMEOUT,
                read_only=True
            )
        except ValueError as error:
            results.append({
                "command": test_command,
                "status": "rejected",
                "error": str(error),
            })
            continue

        # pytest exit code 5 means "no tests collected", not a failure.
        if (
            "pytest" in parts
            and result.get("exit_code") == PYTEST_NO_TESTS_EXIT_CODE
        ):
            result["status"] = "no_tests"

        results.append(result)

    # 3. If no real test ran, verify with a smoke check instead.
    real_runs = [
        r for r in results if r.get("status") not in ("no_tests", "rejected")
    ]
    verification = "tests"

    if not real_runs:
        verification = "smoke_only"
        for command in _smoke_commands(diff_result):
            try:
                results.append(
                    execute_code(
                        workspace_path=workspace_path,
                        command=command,
                        timeout=SMOKE_TIMEOUT,
                        read_only=True
                    )
                )
            except ValueError as error:
                results.append({
                    "command": command,
                    "status": "rejected",
                    "error": str(error),
                })

    # 4. Aggregate. no_tests results don't count against the run.
    counted = [r for r in results if r.get("status") != "no_tests"]
    all_passed = bool(counted) and all(
        r.get("status") == "success" for r in counted
    )

    execution_result = {
        "status": "success" if all_passed else "failed",
        "verification": verification,
        "total_tests": len(counted),
        "passed": sum(r.get("status") == "success" for r in counted),
        "failed": sum(r.get("status") != "success" for r in counted),
        "results": results,
    }

    if not all_passed:
        kind = _failure_kind(results, workspace_path)
        if kind:
            execution_result["failure_kind"] = kind

    return {"execution_result": execution_result}



def attempt_recorder_node(state: DevPilotState):
    """
    Record a compact summary of the current coding attempt.
    """

    patch_result = state.get("patch_result", {})
    execution_result = state.get("execution_result", {})
    review_result = state.get("review_result")
    diff_result = state.get("diff_result") or {}

    # Coder has already incremented this counter.
    current_count = state.get("revision_count", 0)

    changed_files = [
        item["file_path"]
        for item in diff_result.get("files", [])
    ]

    attempt = {
        "attempt_number": current_count,
        "files_changed": changed_files,
        "patch_status": patch_result.get("status"),
        "patch_error": truncate(
            patch_result.get("error", ""), 300
        ),
        "execution_status": execution_result.get("status"),
        "failure_output": extract_failures(
            execution_result, 800
        ),
        "review_summary": (
            truncate(review_result.summary, 400)
            if review_result else None
        ),
        "required_changes": (
            review_result.required_changes
            if review_result else None
        ),
    }

    history = list(state.get("attempt_history", []))

    return {
        "attempt_history": history + [attempt]
    }




async def retry_intelligence_node(state: DevPilotState):
    """
    Analyze current and historical failures, including
    human-requested revisions, and generate a correction strategy.
    """

    intelligence = get_retry_intelligence_chain()

    recent_history = state.get("attempt_history", [])[-MAX_ATTEMPTS_IN_RETRY:]

    result = await intelligence.ainvoke({

        "task": truncate(state["task"], 500),

        "review_feedback": truncate(
            state.get(
                "review_feedback",
                "No reviewer feedback available."
            ),
            800
        ),

        "human_feedback": truncate(
            state.get(
                "human_feedback",
                "None"
            ),
            1000
        ),

        "diff_result": truncate(
            state.get("diff_result", {}),
            1200
        ),

        "execution_result": extract_failures(
            state.get("execution_result", {})
        ),

        "attempt_history": json.dumps(
            recent_history,
            default=str
        ),

        "verification_result": truncate(
            state.get(
                "verification_result",
                "No additional verification performed."
            ),
            1200
        )
    })

    print("\n[RETRY INTELLIGENCE]")
    print("Failure type:", result.failure_type)
    print("Root cause:", result.root_cause)
    print("Repeated failure:", result.repeated_failure)
    print("Retry recommendation:", result.should_retry)
    print("Correction strategy:", result.correction_strategy)

    return {
        "retry_analysis": result
    }


def verification_node(state: DevPilotState):
    """
    Run additional verification without modifying repository source files.

    Only Python commands are allowed.
    Dependencies are not installed.
    """

    retry_analysis = state.get("retry_analysis")

    if retry_analysis is None:
        return {
            "verification_result": {
                "status": "error",
                "message": "Retry analysis is unavailable."
            }
        }

    if retry_analysis.decision != "verify":
        return {
            "verification_result": {
                "status": "error",
                "message": "Verification was not requested."
            }
        }

    instructions = retry_analysis.correction_strategy or []

    if not instructions:
        return {
            "verification_result": {
                "status": "error",
                "message": "No verification instructions were provided."
            }
        }

    workspace_path = state["workspace_path"]
    results = []

    for instruction in instructions:

        try:
            parts = shlex.split(instruction)
        except ValueError:
            results.append({
                "command": instruction,
                "status": "rejected",
                "error": "Command could not be parsed."
            })
            continue

        # Only allow Python commands.
        if not parts or parts[0] not in ("python", "python3"):
            results.append({
                "command": instruction,
                "status": "rejected",
                "error": "Only Python verification commands are allowed."
            })
            continue

        try:
            result = execute_code(
                workspace_path=workspace_path,
                command=parts,
                timeout=TEST_TIMEOUT,
                read_only=True
            )

            results.append(result)

        except ValueError as error:
            results.append({
                "command": instruction,
                "status": "rejected",
                "error": str(error),
            })

    counted = [
        result for result in results
        if result.get("status") != "no_tests"
    ]

    all_passed = bool(counted) and all(
        result.get("status") == "success"
        for result in counted
    )

    verification_result = {
        "status": "success" if all_passed else "failed",
        "total_checks": len(counted),
        "passed": sum(
            result.get("status") == "success"
            for result in counted
        ),
        "failed": sum(
            result.get("status") != "success"
            for result in counted
        ),
        "results": results,
    }

    print("\n[VERIFICATION SUMMARY]")
    print(verification_result)

    return {"verification_result": verification_result}


def human_approval_node(state: DevPilotState):
    """
    Pause DevPilot and request a human decision
    after the AI Reviewer approves the implementation.
    """

    diff_result = state.get("diff_result") or {}

    approval_request = {
        "message": "Human approval required before applying changes.",
        "task": state["task"],
        "review_summary": (
            state["review_result"].summary
            if state.get("review_result")
            else "No review summary available."
        ),
        "changed_files": diff_result.get("files", []),
        "diff": diff_result.get("diff", ""),
        "total_changed_files": diff_result.get(
            "total_changed_files", 0
        ),
        "available_decisions": [
            "approve",
            "reject",
            "request_changes"
        ]
    }

    decision = interrupt(approval_request)

    if not isinstance(decision, dict):
        raise ValueError("Human approval must be a dictionary.")

    action = decision.get("decision")

    if action not in {"approve", "reject", "request_changes"}:
        raise ValueError("Invalid human approval decision.")

    feedback = decision.get("feedback", "")

    if action == "request_changes" and (
        not isinstance(feedback, str) or not feedback.strip()
    ):
        raise ValueError(
            "Feedback is required when requesting changes."
        )

    print(f"[HUMAN APPROVAL] Decision: {action}")

    return {
        "human_decision": action,
        "human_feedback": (
            feedback.strip()
            if isinstance(feedback, str)
            else ""
        ),
        "human_revision_count": (
            state.get("human_revision_count", 0)
            + (1 if action == "request_changes" else 0)
        )
    }


def apply_approved_changes_node(state: DevPilotState):

    """
    Apply changes to the original repository after human approval.
    """

    if state.get("human_decision") != "approve":
        return {
            "application_result": {
                "status": "rejected",
                "message": "Human approval is required."
            }
        }

    try:
        backup_root = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "backups"
        )

        result = apply_approved_changes(
            repository_path=state["original_project_path"],
            workspace_path=state["workspace_path"],
            diff_result=state["diff_result"],
            original_head_commit=state["original_head_commit"],
            backup_root=str(backup_root)
        )

        print("[APPLICATION] Approved changes applied successfully.")

        return {
            "application_result": result
        }

    except Exception as error:
        print(f"[APPLICATION] Failed: {error}")

        return {
            "application_result": {
                "status": "failed",
                "message": str(error)
            }
        }

# ---------------------------------------------------------------------------
#               MCP
# ---------------------------------------------------------------------------



MAX_MCP_ROUNDS = 4
MAX_MCP_TOOL_CALLS = 10


async def repository_analyst_mcp_node(state: DevPilotState):
    """Allow the Repository Analyst to request GitHub/docs tools."""

    round_count = state.get("mcp_round_count", 0)

    inputs = {
        "task": state["task"],
        "plan": state["plan"].model_dump_json(),
        "file_inventory": state["file_inventory"],
        "repository_context": truncate(
            state["repository_context"],
            MAX_REPO_CONTEXT_CHARS,
        ),
    }

    prompt_messages = repository_analyst_prompt.invoke(
        inputs
    ).to_messages()

    history = state.get("messages", [])

    if history:
        history = history[-2:]

    if round_count >= MAX_MCP_ROUNDS:
        response = await get_llm().ainvoke(
            prompt_messages + history
        )
    else:
        response = await request_mcp_tools(
            prompt_messages + history,
            allowed_tools=AGENT_MCP_TOOLS["repository_analyst"],
        )

    return {
        "messages": [response],
        "mcp_return_to": "repository_analyst_mcp",
        "mcp_round_count": round_count + 1,
    }




async def mcp_tool_executor_node(state: DevPilotState) -> dict:
    tools = await get_mcp_tools()

    allowed_tools_by_agent = {
        "repository_analyst_mcp": AGENT_MCP_TOOLS["repository_analyst"],
        "planner_mcp": AGENT_MCP_TOOLS["planner"],
        "coder_mcp": AGENT_MCP_TOOLS["coder"],
        "reviewer_mcp": AGENT_MCP_TOOLS["reviewer"],
    }

    return_to = state.get("mcp_return_to")
    allowed_tools = allowed_tools_by_agent.get(return_to)

    if not allowed_tools:
        raise RuntimeError(
            f"Unknown MCP requesting agent: {return_to}"
        )

    selected_tools = {
        tool.name: tool
        for tool in tools
        if tool.name in allowed_tools
    }

    last_message = state["messages"][-1]
    tool_messages = []
    tool_call_count = state.get("mcp_tool_call_count", 0)
    mcp_disabled = state.get("mcp_disabled", False)

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]

        if tool_name not in selected_tools:
            raise RuntimeError(
                f"Tool is not permitted: {tool_name}"
            )

        if mcp_disabled or tool_call_count >= MAX_MCP_TOOL_CALLS:
            mcp_disabled = True
            content = (
                f"MCP tool execution limit reached "
                f"({MAX_MCP_TOOL_CALLS}). MCP is now disabled "
                "for the remainder of this workflow."
            )

        else:
            tool_call_count += 1
            if tool_call_count >= MAX_MCP_TOOL_CALLS:
                mcp_disabled = True

            try:
                result = await selected_tools[tool_name].ainvoke(
                    tool_call["args"]
                )
                content = str(result)

            except Exception as exc:
                content = f"Tool execution failed: {exc}"

        tool_messages.append(
            ToolMessage(
                content=content,
                tool_call_id=tool_call["id"],
                name=tool_name,
            )
        )

    return {
        "messages": tool_messages,
        "mcp_tool_call_count": tool_call_count,
        "mcp_disabled": mcp_disabled,
    }

async def planner_mcp_node(state: DevPilotState):
    """Allow the Planner to research GitHub when needed."""

    round_count = state.get("mcp_round_count", 0)

    messages = [
        SystemMessage(
            content=(
                "You are a repository research assistant for DevPilot's Planner. "
                "Analyze the coding task and available repository context. "
                "Use GitHub MCP tools only when external repository information "
                "or implementation history would materially improve the plan. "
                "Do not create the implementation plan yourself. "
                "Do not modify repositories. "
                "When you have sufficient information, summarize your findings."
            )
        ),
        HumanMessage(
            content=(
                f"Task:\n{state['task']}\n\n"
                f"File inventory:\n{state['file_inventory']}\n\n"
                f"Repository context:\n"
                f"{truncate(state['repository_context'], MAX_REPO_CONTEXT_CHARS)}"
            )
        ),
    ]

    history = state.get("messages", [])

    if state.get("mcp_disabled", False) or round_count >= MAX_MCP_ROUNDS:
        response = await get_llm().ainvoke(messages + history)
    else:
        response = await request_mcp_tools(
            messages + history,
            allowed_tools=AGENT_MCP_TOOLS["planner"],
        )

    return {
        "messages": [response],
        "mcp_return_to": "planner_mcp",
        "mcp_round_count": round_count + 1,
    }



async def coder_mcp_node(state: DevPilotState):
    """Allow the Coder to request restricted terminal diagnostics."""

    round_count = state.get("mcp_round_count", 0)

    messages = [
        SystemMessage(
            content=(
                "You are a diagnostic assistant for DevPilot's Coder. "
                "Analyze the task, implementation plan, and repository context. "
                "Use permitted Terminal MCP diagnostics only when they are "
                "needed to understand the development environment. "
                "Do not modify files or execute arbitrary commands. "
                "Do not write the implementation. "
                "When sufficient, summarize relevant diagnostic findings."
            )
        ),
        HumanMessage(
            content=(
                f"Task:\n{state['task']}\n\n"
                f"Plan:\n{state['plan'].model_dump_json()}\n\n"
                f"Repository context:\n"
                f"{truncate(state['repository_context'], MAX_REPO_CONTEXT_CHARS)}"
            )
        ),
    ]

    history = state.get("messages", [])

    if state.get("mcp_disabled", False) or round_count >= MAX_MCP_ROUNDS:
        response = await get_llm().ainvoke(messages + history)
    else:
        response = await request_mcp_tools(
            messages + history,
            allowed_tools=AGENT_MCP_TOOLS["coder"],
        )

    return {
        "messages": [response],
        "mcp_return_to": "coder_mcp",
        "mcp_round_count": round_count + 1,
    }




async def reviewer_mcp_node(state: DevPilotState):
    """Allow the Reviewer to inspect GitHub and workspace context."""

    round_count = state.get("mcp_round_count", 0)

    messages = [
        SystemMessage(
            content=(
                "You are a research assistant for DevPilot's Code Reviewer. "
                "Inspect the proposed changes and identify relevant context "
                "that could help evaluate their correctness and safety. "
                "Use GitHub MCP tools to inspect existing implementations "
                "or repository history when useful. Use read-only Terminal "
                "tools to inspect workspace files and Git status. "
                "Do not modify files or approve/reject the proposal. "
                "Do not perform the review yourself. "
                "When sufficient, summarize relevant findings."
            )
        ),
        HumanMessage(
            content=(
                f"Task:\n{state['task']}\n\n"
                f"Plan:\n{state['plan'].model_dump_json()}\n\n"
                f"Repository analysis:\n"
                f"{state['repository_analysis'].model_dump_json()}\n\n"
                f"Code proposal:\n"
                f"{truncate(state['code_proposal'].model_dump_json(), MAX_PROPOSAL_CHARS)}\n\n"
                f"Diff:\n"
                f"{truncate(state.get('diff_result', {}), MAX_DIFF_CHARS)}\n\n"
                f"Execution failures:\n"
                f"{extract_failures(state.get('execution_result', {}))}"
            )
        ),
    ]

    history = state.get("messages", [])

    if history:
        history = history[-2:]

    if state.get("mcp_disabled", False) or round_count >= MAX_MCP_ROUNDS:
        response = await get_llm().ainvoke(messages + history)
    else:
        response = await request_mcp_tools(
            messages + history,
            allowed_tools=AGENT_MCP_TOOLS["reviewer"],
        )

    return {
        "messages": [response],
        "mcp_return_to": "reviewer_mcp",
        "mcp_round_count": round_count + 1,
    }
