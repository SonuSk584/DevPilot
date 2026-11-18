from langchain_groq import ChatGroq
from app.core.config import settings

from app.prompt.system import chat_prompt

def get_llm():
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY.get_secret_value(),
        temperature=0
        
    )
    return llm

def get_chat_chain():
    llm= get_llm()

    chain = chat_prompt | llm

    return chain