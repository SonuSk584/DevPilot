
import asyncio

from app.graph.nodes import retry_intelligence_node


async def main():

    state = {
        "task": "Create a FastAPI health endpoint",

        "review_feedback": """
        Execution failed.
        Missing dependency: httpx2.
        Previous attempt also encountered this problem.
        """,

        "code_proposal": None,

        "patch_result": {
            "status": "success"
        },

        "diff_result": {
            "status": "success"
        },

        "execution_result": {
            "status": "failed",
            "results": [
                {
                    "status": "failed",
                    "error": "ModuleNotFoundError: httpx2"
                }
            ]
        },

        "attempt_history": [
            {
                "attempt_number": 1,
                "execution_result": {
                    "status": "failed",
                    "error": "ModuleNotFoundError: httpx2"
                }
            }
        ]
    }

    result = await retry_intelligence_node(state)

    analysis = result["retry_analysis"]

    print("\nFULL ANALYSIS:")
    print(analysis.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
