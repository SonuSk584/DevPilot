from fastapi import APIRouter, HTTPException

from app.schemas.plan import PlanRequest, TaskPlan
from app.service.llm import get_planner_chain

router = APIRouter()


@router.post("/plan", response_model=TaskPlan)
async def create_plan(request: PlanRequest):

    try:
        planner = get_planner_chain()

        result = await planner.ainvoke({
            "task": request.task
        })

        return result

    except Exception as error:
        print(f"Planner failed: {type(error).__name__}: {error}")

        raise HTTPException(
            status_code=502,
            detail="Failed to generate execution plan."
        )