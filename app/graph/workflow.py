from langgraph.graph import START, END, StateGraph


from app.graph.state import DevPilotState
from app.graph.patch_guard import guard_patch_node
from app.graph.nodes import (
    planner_node,
    repository_analyst_node,
    coder_node,
    patch_engine_node,
    diff_manager_node,
    code_executor_node,
    reviewer_node,
    attempt_recorder_node,
    retry_intelligence_node,
    verification_node
)

MAX_CODER_ATTEMPT = 3


# --------------------------------------------------
# Routers
# --------------------------------------------------

def route_after_patch(state: DevPilotState):
    """A failed patch is cheap to fix: send the exact error back to the Coder."""
    patch = state.get("patch_result") or {}

    if patch.get("status") == "success":
        return "diff"

    if state.get("revision_count", 0) >= MAX_CODER_ATTEMPT:
        print("[ROUTER] Patch failed and no attempts remain. Ending workflow.")
        return "end"

    print(f"[ROUTER] Patch failed: {patch.get('error')}. Returning to Coder.")
    return "coder"


def route_after_diff(state: DevPilotState):
    diff = state.get("diff_result") or {}

    if diff.get("status") != "success":
        print("[ROUTER] Diff failure. Ending workflow.")
        return "end"

    return "executor"


def route_after_execution(state: DevPilotState):
    """Environment problems can't be fixed by changing code."""
    result = state.get("execution_result") or {}

    if (
        result.get("status") == "environment_error"
        or result.get("failure_kind") == "environment_dependency"
    ):
        print("[ROUTER] Environment problem. Ending workflow.")
        return "end"

    return "reviewer"


def route_after_review(state: DevPilotState):
    """Approved runs skip the recorder and the Retry Intelligence LLM call."""
    review = state.get("review_result")

    if review is not None and review.approved:
        print("[ROUTER] Review approved. Ending workflow.")
        return "end"

    return "recorder"



def route_after_verification(state: DevPilotState):
    """Finish successful verification; re-analyze failed verification."""

    result = state.get("verification_result") or {}

    if result.get("status") == "success":
        print("[ROUTER] Verification successful. Ending workflow.")
        return "end"

    print("[ROUTER] Verification failed. Returning to Retry Intelligence.")
    return "retry_intelligence"

def retry_router(state: DevPilotState):
    """
    Route according to Retry Intelligence's decision.
    """

    retry_analysis = state.get("retry_analysis")

    if retry_analysis is None:
        print("[ROUTER] Missing retry analysis. Ending workflow.")
        return "end"

    if retry_analysis.decision == "stop":
        print("[ROUTER] Retry Intelligence recommends stopping.")
        return "end"

    if retry_analysis.decision == "verify":
        print("[ROUTER] Additional verification requested.")
        return "verify"

    if retry_analysis.decision == "retry":
        if state.get("revision_count", 0) >= MAX_CODER_ATTEMPT:
            print("[ROUTER] Maximum attempts reached.")
            return "end"

        if not retry_analysis.should_retry:
            print("[ROUTER] Invalid retry decision. Ending workflow.")
            return "end"

        print("[ROUTER] Retry approved. Returning to Coder.")
        return "coder"

    print("[ROUTER] Unknown retry decision. Ending workflow.")
    return "end"



# --------------------------------------------------
# Graph
# --------------------------------------------------

def build_devpilot_graph():

    g = StateGraph(DevPilotState)

    g.add_node("planner", planner_node)
    g.add_node("repository_analyst", repository_analyst_node)
    g.add_node("coder", coder_node)
    g.add_node("patch_engine", guard_patch_node(patch_engine_node))
    g.add_node("diff_manager", diff_manager_node)
    g.add_node("code_executor", code_executor_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("attempt_recorder", attempt_recorder_node)
    g.add_node("retry_intelligence", retry_intelligence_node)
    g.add_node("verification", verification_node)

    g.add_edge(START, "planner")
    g.add_edge("planner", "repository_analyst")
    g.add_edge("repository_analyst", "coder")
    g.add_edge("coder", "patch_engine")

    g.add_conditional_edges(
        "patch_engine", route_after_patch,
        {"diff": "diff_manager", "coder": "coder", "end": END},
    )
    g.add_conditional_edges(
        "diff_manager", route_after_diff,
        {"executor": "code_executor", "end": END},
    )
    g.add_conditional_edges(
        "code_executor", route_after_execution,
        {"reviewer": "reviewer", "end": END},
    )
    g.add_conditional_edges(
        "reviewer", route_after_review,
        {"recorder": "attempt_recorder", "end": END},
    )

    g.add_edge("attempt_recorder", "retry_intelligence")

    g.add_conditional_edges(
    "retry_intelligence",
    retry_router,
    {
        "coder": "coder",
        "verify": "verification",
        "end": END,
    },
)

    g.add_conditional_edges(
    "verification",
    route_after_verification,
    {
        "retry_intelligence": "retry_intelligence",
        "end": END,
    },
        )

    return g.compile()