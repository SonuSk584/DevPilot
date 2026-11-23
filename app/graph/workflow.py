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
    verification_node,
    human_approval_node,
    apply_approved_changes_node,
    repository_reindex_node,
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

    revision_count = state.get("revision_count", 0)

    if revision_count >= MAX_CODER_ATTEMPT:
        print("[ROUTER] Patch failed and no automated attempts remain. Ending workflow.")
        return "end"

    print(
        f"[ROUTER] Patch failed: {patch.get('error')}. "
        "Re-indexing repository before retry."
    )
    return "repository_reindex"



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
    """Send Reviewer-approved changes to human approval."""

    review = state.get("review_result")

    if review is not None and review.approved:
        print("[ROUTER] Reviewer approved. Requesting human approval.")
        return "approval"

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
        revision_count = state.get("revision_count", 0)

        if revision_count >= MAX_CODER_ATTEMPT:
            print("[ROUTER] Maximum automated revision attempts reached.")
            return "end"

        if not retry_analysis.should_retry:
            print("[ROUTER] Invalid retry decision. Ending workflow.")
            return "end"

        print("[ROUTER] Retry approved. Re-indexing repository before retry.")
        return "repository_reindex"

    print("[ROUTER] Unknown retry decision. Ending workflow.")
    return "end"


def route_after_human_approval(state: DevPilotState):
    """Route according to the human's decision."""

    decision = state.get("human_decision")

    if decision == "approve":
        print("[ROUTER] Human approved changes. Applying changes.")
        return "apply"

    if decision == "reject":
        print("[ROUTER] Human rejected changes.")
        return "end"

    if decision == "request_changes":
        print("[ROUTER] Human requested revisions.")
        return "retry_intelligence"

    print("[ROUTER] Invalid human decision. Ending workflow.")
    return "end"

# --------------------------------------------------
# Graph
# --------------------------------------------------

def build_devpilot_graph(checkpointer=None):

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
    g.add_node("human_approval", human_approval_node)
    g.add_node("apply_changes", apply_approved_changes_node)
    g.add_node("repository_reindex", repository_reindex_node)

    g.add_edge(START, "planner")
    g.add_edge("planner", "repository_analyst")
    g.add_edge("repository_analyst", "coder")
    g.add_edge("coder", "patch_engine")
    g.add_edge("repository_reindex", "coder")

    g.add_conditional_edges(
        "patch_engine", route_after_patch,
        {
        "diff": "diff_manager",
        "repository_reindex": "repository_reindex",
        "end": END,
        },
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
    "reviewer",
    route_after_review,
    {
        "approval": "human_approval",
        "recorder": "attempt_recorder",
    },
)
    g.add_conditional_edges(
    "human_approval",
    route_after_human_approval,
    {
        "apply": "apply_changes",
        "retry_intelligence": "retry_intelligence",
        "end": END,
    },
)

    g.add_edge("attempt_recorder", "retry_intelligence")

    g.add_conditional_edges(
    "retry_intelligence",
    retry_router,
        {
    "repository_reindex": "repository_reindex",
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

    g.add_edge("apply_changes", END)

    return g.compile(checkpointer=checkpointer)