
from fastapi import APIRouter, HTTPException

from app.schemas.devpilot import (
    DevPilotRequest,
    DevPilotResponse
)

from app.service.respository_ingestion import ingest_repository
from app.graph.workflow import build_devpilot_graph


router = APIRouter()


@router.post(
    "/run-devpilot",
    response_model=DevPilotResponse
)
async def run_devpilot(request: DevPilotRequest):

    try:
        # 1. Ingest repository
        repository = ingest_repository(request.repository_name)

        # 2. Get repository context
        repository_context = repository["context"]

        # 3. Build LangGraph workflow
        graph = build_devpilot_graph()

        # 4. Prepare initial graph state
        initial_state = {
            "task": request.task,
            "repository_context": repository_context
        }

        # 5. Execute the complete workflow
        final_state = await graph.ainvoke(initial_state)

        # 6. Return structured results
        return {
            "repository_name": request.repository_name,
            "task": request.task,
            "plan": final_state["plan"],
            "repository_analysis": final_state["repository_analysis"],
            "code_proposal": final_state["code_proposal"],
            "review_result": final_state["review_result"],
            "revision_count": final_state.get("revision_count", 0),
            "message": "DevPilot execution completed"
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Repository not found"
        )

    except Exception as error:
        print(
            f"DevPilot execution failed: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="DevPilot execution failed"
        )
