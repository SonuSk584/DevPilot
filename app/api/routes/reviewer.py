from fastapi import APIRouter, HTTPException

from app.schemas.review import ReviewRequest, ReviewResult
from app.service.llm import get_reviewer_chain

router = APIRouter()


@router.post("/review", response_model=ReviewResult)
async def review_code(request: ReviewRequest):

    try:
        reviewer = get_reviewer_chain()

        result = await reviewer.ainvoke({
            "task": request.task,
            "repository_analysis": request.repository_analysis,
            "repository_context": request.repository_context,
            "code_proposal": request.code_proposal
        })

        return result

    except Exception as error:
        print(f"Review failed: {type(error).__name__}: {error}")

        raise HTTPException(
            status_code=502,
            detail="Code review failed."
        )