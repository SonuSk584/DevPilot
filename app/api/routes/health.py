from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return{
        "status":"healthy",
        "application":"DevPilot",
        "message":"DevPilot backend is running"
    }