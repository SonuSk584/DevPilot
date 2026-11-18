from fastapi import APIRouter, HTTPException
from app.schemas.repository import (RepositoryAnalysis, repositoryAnalysisRequest)

from app.service.llm import get_repository_analyst_chain
router = APIRouter()

@router.post("/analyze-repository", response_model=RepositoryAnalysis)
async def analyze_repository(request:repositoryAnalysisRequest ):
    try:
        analyst = get_repository_analyst_chain()

        result = await analyst.ainvoke({
            "task":request.task,
            "repository_context":request.repository_context
        })
        return result
    except Exception as error :
        print(f"repository analysis failed :"
        f"{type(error).__name__}:{error}"
        )

        raise HTTPException(
            status_code=502,
            detail = "repository analysis failed"
        )