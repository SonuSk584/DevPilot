
from langgraph.graph import START, END, StateGraph

from app.graph.state import DevPilotState

from app.graph.nodes import (
    planner_node,
    repository_analyst_node,
    coder_node,
    patch_engine_node,
    diff_manager_node,
    code_executor_node,
    reviewer_node,
    attempt_recorder_node
)

MAX_CODER_ATTEMPT = 3



def review_router(state: DevPilotState):

    revision_count = state.get("revision_count", 0)

    patch_result = state.get("patch_result", {})
    diff_result = state.get("diff_result", {})
    execution_result = state.get("execution_result", {})
    review = state.get("review_result")

    # Patch failure: request another proposal.
    if patch_result.get("status") != "success":
        if revision_count < MAX_CODER_ATTEMPT:
            return "coder"
        return "end"

    # Diff failure: this is an infrastructure problem.
    if diff_result.get("status") != "success":
        return "end"

    # Tests must actually execute successfully.
    if execution_result.get("status") != "success":
        if revision_count < MAX_CODER_ATTEMPT:
            return "coder"
        return "end"

    # Only approve if the LLM reviewer also approves.
    if review is not None and review.approved:
        return "end"

    # Request another revision if attempts remain.
    if revision_count < MAX_CODER_ATTEMPT:
        return "coder"

    return "end"



def build_devpilot_graph():

    graph_builder = StateGraph(DevPilotState)

    graph_builder.add_node("planner", planner_node)
    graph_builder.add_node(
        "repository_analyst",
        repository_analyst_node
    )
    graph_builder.add_node("coder", coder_node)
    graph_builder.add_node("patch_engine", patch_engine_node)
    graph_builder.add_node("diff_manager", diff_manager_node)
    graph_builder.add_node("code_executor", code_executor_node)
    graph_builder.add_node("reviewer", reviewer_node)
    graph_builder.add_node(
    "attempt_recorder",
    attempt_recorder_node
    )

    graph_builder.add_edge(START, "planner")

    graph_builder.add_edge("planner", "repository_analyst")
    graph_builder.add_edge("repository_analyst", "coder")

    graph_builder.add_edge("coder", "patch_engine")
    graph_builder.add_edge("patch_engine", "diff_manager")
    graph_builder.add_edge("diff_manager", "code_executor")
    graph_builder.add_edge("code_executor", "reviewer")
    graph_builder.add_edge("reviewer", "attempt_recorder")

    graph_builder.add_conditional_edges(
    "attempt_recorder",
    review_router,
    {
        "coder": "coder",
        "end": END
    }
)

    return graph_builder.compile()
