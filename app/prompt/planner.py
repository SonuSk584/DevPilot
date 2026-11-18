from langchain_core.prompts import ChatPromptTemplate

PLANNER_SYSTEM_PROMPT = """
You are DevPilot's planning agent.

Your job is to analyze a user's software engineering task
and create a practical execution plan.

Rules:
- Break complex tasks into clear, ordered steps.
- Identify potential risks.
- Determine whether repository access is required.
- Do not claim that any code has been modified or tested.
"""

planner_prompt = ChatPromptTemplate.from_messages([
    ("system",PLANNER_SYSTEM_PROMPT),
    ("human","{task}")
]
)