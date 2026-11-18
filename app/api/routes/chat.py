from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.service.llm import get_chat_chain
from app.core.config import settings


router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request:ChatRequest):
    try:
        llm= get_chat_chain()

        response = await llm.ainvoke({"user_message":request.message})

        return ChatResponse(answer=response.content,
        model= settings.GROQ_MODEL)

    except Exception as error:
        print(f"LLM request failed : {type(error).__name__}:{error}")
        raise HTTPException(
            status_code=502,
            detail="failed to generate response from the AI Model"
        )