
from contextlib import asynccontextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


# Persistent DevPilot checkpoint database
CHECKPOINT_DIR = Path(__file__).resolve().parents[2] / "data"

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DB = CHECKPOINT_DIR / "devpilot_checkpoints.db"


@asynccontextmanager
async def get_checkpointer():
    """
    Create an asynchronous SQLite checkpointer context
    with explicitly allowed DevPilot checkpoint models.
    """

    async with AsyncSqliteSaver.from_conn_string(
        str(CHECKPOINT_DB)
    ) as checkpointer:

        checkpointer.serde = JsonPlusSerializer(
            allowed_msgpack_modules=[
                ("app.schemas.plan", "TaskPlan"),
                ("app.schemas.repository", "RepositoryAnalysis"),
                ("app.schemas.coding", "CodeProposal"),
                ("app.schemas.review", "ReviewResult"),
            ]
        )

        yield checkpointer
