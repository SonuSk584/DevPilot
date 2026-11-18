from app.graph.state import DevPilotState

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

    return {
        "plan": result
    }


async def repository_analyst_node(state: DevPilotState):

    analyst = get_repository_analyst_chain()

    result = await analyst.ainvoke({
        "task": state["task"],
        "repository_context": state["repository_context"]
    })

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
        )
    })

    return {
        "code_proposal": result,
        "revision_count": state.get("revision_count", 0)+1
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

    })

    feedback = (
        f"Review summary: {result.summary}\n"
        f"Findings: "
        f"{[finding.model_dump() for finding in result.findings]}\n"
        f"Required changes: {result.required_changes}"
    )

    return {
        "review_result": result,
        "review_feedback": feedback
    }