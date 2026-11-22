
from pathlib import Path

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


# Persistent DevPilot checkpoint database
CHECKPOINT_DIR = Path(__file__).resolve().parents[2] / "data"

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DB = CHECKPOINT_DIR / "devpilot_checkpoints.db"


def get_checkpointer():
    """
    Create an asynchronous SQLite checkpointer context.
    """

    return AsyncSqliteSaver.from_conn_string(
        str(CHECKPOINT_DB)
    )
