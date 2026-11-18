from langchain_groq import ChatGroq
from app.core.config import settings

from app.prompt.system import chat_prompt
from app.schemas.plan import TaskPlan
from app.prompt.planner import planner_prompt
from app.prompt.repository_analyst import repository_analyst_prompt
from app.schemas.repository import RepositoryAnalysis
from app.schemas.coding import CodeProposal
from app.prompt.coder import coder_prompt
from app.schemas.review import ReviewResult
from app.prompt.reviewer import reviewer_prompt


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

def get_planner():
    llm= get_llm()
    structured_llm = llm.with_structured_output(TaskPlan)
    return structured_llm

def get_planner_chain():
    planner = get_planner()

    return planner_prompt | planner

def get_repository_analyst():
    llm = get_llm()

    structured_llm = llm.with_structured_output(RepositoryAnalysis)

    return structured_llm

def get_repository_analyst_chain():
    analyst = get_repository_analyst()

    return repository_analyst_prompt | analyst


def get_coder():
    llm = get_llm()

    structured_llm = llm.with_structured_output(CodeProposal)

    return structured_llm

def get_coder_chain():
    coder= get_coder()

    return coder_prompt | coder


def get_reviewer():
    llm = get_llm()

    structured_llm = llm.with_structured_output(ReviewResult)

    return structured_llm

def get_reviewer_chain():

    reviewer = get_reviewer()

    return reviewer_prompt | reviewer