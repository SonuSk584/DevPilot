from app.graph.state import DevPilotState
from app.service.patch_engine import apply_code_proposal
from app.service.diff_manager import get_workspace_diff
from app.service.code_executor import execute_code

from app.service.llm import (
    get_planner_chain,
    get_repository_analyst_chain,
    get_coder_chain,
    get_reviewer_chain
)


async def planner_node(state: DevPilotState):

    planner = get_planner_chain()

    result = await planner.ainvoke({
        "task": state["task"]
    })
    print("[DEBUG] Planner received:", list(state.keys()))

    return {
        "plan": result
    }


async def repository_analyst_node(state: DevPilotState):

    analyst = get_repository_analyst_chain()

    result = await analyst.ainvoke({
        "task": state["task"],
        "repository_context": state["repository_context"]
    })
    print("[DEBUG] Analyst received:", list(state.keys()))

    return {
        "repository_analysis": result
    }



async def coder_node(state: DevPilotState):

    coder = get_coder_chain()

    result = await coder.ainvoke({

        "task": state["task"],

        "execution_plan": state["plan"].model_dump_json(),

        "repository_analysis": (
            state["repository_analysis"].model_dump_json()
        ),

        "repository_context": state["repository_context"],

        "review_feedback": state.get(
            "review_feedback",
            "No previous review feedback. This is the initial proposal"
        ),
        "file_inventory": state["file_inventory"],

        "previous_diff": str(
            state.get("diff_result", {})
        ),

        "previous_execution_result": str(
            state.get("execution_result", {})
        )
    })
    print("[DEBUG] Coder received:", list(state.keys()))

    return {
        "code_proposal": result,
        "revision_count": state.get("revision_count", 0) + 1
    }




async def reviewer_node(state: DevPilotState):

    reviewer = get_reviewer_chain()

    result = await reviewer.ainvoke({

        "task": state["task"],

        "repository_analysis": (
            state["repository_analysis"].model_dump_json()
        ),

        "repository_context": state["repository_context"],

        "code_proposal": (
            state["code_proposal"].model_dump_json()
        ),

        "patch_result": str(
            state.get("patch_result", {})
        ),

        "diff_result": str(
            state.get("diff_result", {})
        ),

        "execution_result": str(
            state.get("execution_result", {})
        )
    })

    feedback = (
        f"Review summary: {result.summary}\n"
        f"Findings: "
        f"{[finding.model_dump() for finding in result.findings]}\n"
        f"Required changes: {result.required_changes}\n"
        f"Execution results: {state.get('execution_result', {})}"
    )

    return {
        "review_result": result,
        "review_feedback": feedback
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
                "data": result
            }
        }

    except Exception as error:
        return {
            "diff_result": {
                "status": "failed",
                "error": str(error)
            }
        }



def code_executor_node(state: DevPilotState):

    """
    Execute proposed tests inside the restricted Docker container.
    """

    patch_result = state["patch_result"]

    if patch_result["status"] != "success":
        return {
            "execution_result": {
                "status": "skipped",
                "message": "Patch application failed. Tests were not executed."
            }
        }
    diff_result = state.get("diff_result", {})

    if diff_result.get("status") != "success":
        return {
        "execution_result": {
            "status": "skipped",
            "message": "Diff generation failed. Tests were not executed."
        }
    }

    test_commands = state["code_proposal"].tests_to_run

    if not test_commands:
        return {
            "execution_result": {
                "status": "skipped",
                "message": "No test commands were provided."
            }
        }

    results = []

    for test_command in test_commands:

        # Accept only simple Python test commands.
        parts = test_command.split()

        if not parts or parts[0] not in ("python", "python3"):
            results.append({
                "command": test_command,
                "status": "rejected",
                "error": "Only Python commands are allowed."
            })
            continue

        result = execute_code(
            workspace_path=state["workspace_path"],
            command=parts,
            timeout=60
        )

        results.append(result)

    all_passed = all(
        result["status"] == "success"
        for result in results
    )

    return {
        "execution_result": {
            "status": "success" if all_passed else "failed",
            "total_tests": len(results),
            "passed": sum(
                result["status"] == "success"
                for result in results
            ),
            "failed": sum(
                result["status"] != "success"
                for result in results
            ),
            "results": results
        }
    }


def attempt_recorder_node(state: DevPilotState):
    """
    Record the results of the current coding attempt.
    """

    attempt_number = state.get("revision_count", 0)

    proposal = state.get("code_proposal")
    patch_result = state.get("patch_result", {})
    diff_result = state.get("diff_result", {})
    execution_result = state.get("execution_result", {})
    review_result = state.get("review_result")

    attempt = {
        "attempt_number": attempt_number,

        "code_proposal": (
            proposal.model_dump()
            if proposal else None
        ),

        "patch_result": patch_result,

        "diff_result": diff_result,

        "execution_result": execution_result,

        "review_result": (
            review_result.model_dump()
            if review_result else None
        )
    }

    history = list(state.get("attempt_history", []))

    return {
        "attempt_history": history + [attempt]
    }