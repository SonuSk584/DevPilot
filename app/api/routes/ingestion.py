
from fastapi import APIRouter, HTTPException

from app.schemas.ingestion import (
    RepositoryIngestionRequest,
    RepositoryIngestionResponse
)

from app.service.respository_ingestion import ingest_repository


router = APIRouter()


@router.post(
    "/ingest-repository",
    response_model=RepositoryIngestionResponse
)
async def ingest_repository_endpoint(
    request: RepositoryIngestionRequest
):
    try:
        result = ingest_repository(request.repository_name)

        return {
            key: value
            for key, value in result.items()
            if key != "context"
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Repository not found"
        )

    except (ValueError, NotADirectoryError):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository location"
        )

    except Exception as error:
        print(
            f"Repository ingestion failed: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Repository ingestion failed"
        )
