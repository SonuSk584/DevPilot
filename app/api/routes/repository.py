from fastapi import APIRouter, HTTPException

from app.schemas.repository import (RepositoryAnalysis, repositoryAnalysisRequest, RepositoryTaskRequest)
from app.service.respository_ingestion import ingest_repository

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


@router.post(
    "/analyze-workspace-repository",
    response_model=RepositoryAnalysis
)
async def analyze_workspace_repository(
    request: RepositoryTaskRequest
):
    try:
        # Step 1: Ingest the requested repository
        repository = ingest_repository(request.repository_name)

        # Step 2: Extract generated repository context
        repository_context = repository["context"]

        # Step 3: Initialize Repository Analyst
        analyst = get_repository_analyst_chain()

        # Step 4: Analyze actual repository code
        result = await analyst.ainvoke({
            "task": request.task,
            "repository_context": repository_context
        })

        return result

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Repository not found"
        )

    except Exception as error:
        print(
            f"Repository analysis failed: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=502,
            detail="Repository analysis failed"
        )
