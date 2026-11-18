import asyncio

from app.graph.workflow import build_devpilot_graph


async def main():

    # Build the workflow
    graph = build_devpilot_graph()

    # Initial input
    initial_state = {
        "task": "Fix the login authentication bug.",

        "repository_context": """
        File: app/auth.py

        def authenticate_user(username, password):

            user = get_user_by_username(username)

            if not user:
                return None

            if user.password_hash != password:
                return None

            return user
        """
    }

    print("\nStarting DevPilot workflow...\n")

    # Execute all four agents
    result = await graph.ainvoke(initial_state)

    print("\nWORKFLOW COMPLETED")

    print("\nPLANNER OUTPUT:")
    print(result["plan"].model_dump_json(indent=2))

    print("\nREPOSITORY ANALYSIS:")
    print(result["repository_analysis"].model_dump_json(indent=2))

    print("\nCODE PROPOSAL:")
    print(result["code_proposal"].model_dump_json(indent=2))

    print("\nREVIEW RESULT:")
    print(result["review_result"].model_dump_json(indent=2))


asyncio.run(main())