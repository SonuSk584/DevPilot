from langgraph.graph import START, END, StateGraph

from app.graph.state import DevPilotState

from app.graph.nodes import(
    planner_node,
    repository_analyst_node,
    coder_node,
    reviewer_node
)

MAX_CODER_ATTEMPT = 3

def review_router(state: DevPilotState):
    review = state["review_result"]

    revision_count = state.get("revision_count",0)

    if review.approved:
        return "end"

    if revision_count >= MAX_CODER_ATTEMPT:
        return "end"

    return "coder"



def build_devpilot_graph():

    graph_builder = StateGraph(DevPilotState)

    graph_builder.add_node("planner",planner_node)
    graph_builder.add_node("repository_analyst",repository_analyst_node)
    graph_builder.add_node("coder",coder_node)
    graph_builder.add_node("reviewer",reviewer_node)

    graph_builder.add_edge(START, "planner")
    graph_builder.add_edge("planner","repository_analyst")
    graph_builder.add_edge("repository_analyst","coder")
    graph_builder.add_edge("coder","reviewer")
    graph_builder.add_conditional_edges("reviewer",review_router,{"coder":"coder","end":END})

    graph = graph_builder.compile()

    return graph


