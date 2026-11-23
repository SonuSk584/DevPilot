
import uuid

from fastapi import APIRouter, HTTPException

from app.schemas.devpilot import (
    DevPilotRequest,
    DevPilotResponse
)
from pathlib import Path

from app.service.respository_ingestion import (
    ingest_repository,
    WORKSPACE_ROOT
)
from app.service.workspace_manager import create_workspace


from app.core.checkpoint import get_checkpointer
from app.graph.workflow import build_devpilot_graph
from langgraph.types import Command

from app.schemas.devpilot import HumanApprovalRequest
from app.service.rag.repository_indexer import index_repository

router = APIRouter()


@router.post(
    "/run-devpilot",
    response_model=DevPilotResponse
)
async def run_devpilot(request: DevPilotRequest):

    try:
        # 1. Create an isolated Git workspace.
        workspace = create_workspace(request.repository_name)

        # 2. Resolve the workspace path relative to WORKSPACE_ROOT.
        workspace_relative_path = Path(
            workspace["workspace_path"]
        ).relative_to(WORKSPACE_ROOT)

        # 3. Ingest the workspace, not the original repository.
        repository = ingest_repository(
            str(workspace_relative_path)
        )
        # 3. Index the isolated workspace for RAG retrieval.
        index_result = index_repository(
        workspace["workspace_path"]
        )

        print("[RAG] Repository indexing:", index_result)

        # 4. Generate a persistent execution ID.
        thread_id = uuid.uuid4().hex

        # 5. Prepare the initial graph state.
        initial_state = {
            "task": request.task,
            "repository_context": repository["context"],
            "file_inventory": repository["file_inventory"],
            "workspace_path": workspace["workspace_path"],
            "original_project_path": workspace["original_project_path"],
            "workspace_id": workspace["workspace_id"],
            "repository_name": request.repository_name,
            "original_head_commit": workspace["original_head_commit"],
        }

        # 5. Open persistent SQLite checkpoint storage.
        async with get_checkpointer() as checkpointer:

            await checkpointer.setup()

            graph = build_devpilot_graph(
                checkpointer=checkpointer
            )

            config = {
                "configurable": {
                    "thread_id": thread_id
                }
            }

            # 6. Execute the workflow.
            final_state = await graph.ainvoke(
                initial_state,
                config=config
            )

        # 7. Detect whether human approval is required.
        interrupts = final_state.get("__interrupt__", [])

        if interrupts:
            approval_request = interrupts[0].value

            return {
                "repository_name": request.repository_name,
                "task": request.task,
                "thread_id": thread_id,
                "status": "awaiting_human_approval",
                "plan": final_state.get("plan"),
                "repository_analysis": final_state.get("repository_analysis"),
                "code_proposal": final_state.get("code_proposal"),
                "review_result": final_state.get("review_result"),
                "revision_count": final_state.get("revision_count", 0),
                "approval_request": approval_request,
                "diff_result": final_state.get("diff_result"),
                "message": "Changes are ready for human approval."
            }

        # 8. Determine why the graph finished.
        human_decision = final_state.get("human_decision")

        if human_decision == "reject":
            status = "rejected"
            message = "Changes were rejected by the human reviewer."

        elif human_decision == "approve":
            application_result = final_state.get("application_result") or {}

            if application_result.get("status") == "success":
                status = "completed"
                message = "Approved changes successfully applied."

            else:
                status = "stopped"
                message = (
                "Changes were approved, but application failed: "
                + application_result.get(
                "message",
                "No application result was returned."
            )
        )

        else:
            status = "stopped"
            message = "DevPilot workflow finished without pending approval."

        return {
            "repository_name": request.repository_name,
            "task": request.task,
            "thread_id": thread_id,
            "status": status,
            "plan": final_state.get("plan"),
            "repository_analysis": final_state.get("repository_analysis"),
            "code_proposal": final_state.get("code_proposal"),
            "review_result": final_state.get("review_result"),
            "revision_count": final_state.get("revision_count", 0),
            "approval_request": None,
            "diff_result": final_state.get("diff_result"),
            "application_result": final_state.get("application_result"),
            "message": message
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Repository not found"
        )

    except (ValueError, NotADirectoryError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        print(
            f"DevPilot execution failed: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="DevPilot execution failed"
        )



@router.post(
    "/run-devpilot/{thread_id}/approval",
    response_model=DevPilotResponse
)
async def submit_human_approval(
    thread_id: str,
    request: HumanApprovalRequest
):
    try:
        # Require feedback for revision requests.
        if (
            request.decision == "request_changes"
            and not request.feedback.strip()
        ):
            raise HTTPException(
                status_code=422,
                detail="Feedback is required when requesting changes."
            )

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        async with get_checkpointer() as checkpointer:
            await checkpointer.setup()

            graph = build_devpilot_graph(
                checkpointer=checkpointer
            )

            # Confirm that this thread exists and is paused.
            snapshot = await graph.aget_state(config)

            if not snapshot.values:
                raise HTTPException(
                    status_code=404,
                    detail="DevPilot execution not found."
                )

            if not snapshot.tasks or not any(
                task.interrupts for task in snapshot.tasks
            ):
                raise HTTPException(
                    status_code=409,
                    detail="This execution is not waiting for human approval."
                )

            # Resume the interrupted workflow.
            result = await graph.ainvoke(
                Command(
                    resume={
                        "decision": request.decision,
                        "feedback": request.feedback.strip()
                    }
                ),
                config=config
            )

        # Check whether another approval is required.
        interrupts = result.get("__interrupt__", [])

        if interrupts:
            approval_request = interrupts[0].value
            status = "awaiting_human_approval"
            message = "Revised changes are ready for human approval."

        elif request.decision == "reject":
            approval_request = None
            status = "rejected"
            message = "Changes were rejected."

        elif request.decision == "approve":
            approval_request = None
            application_result = result.get("application_result") or {}

            if application_result.get("status") == "success":
                status = "completed"
                message = "Changes approved and successfully applied to the original repository."

            else:
                status = "stopped"
                message = (
                "Changes were approved, but application failed: "
                + application_result.get(
                "message",
                "No application result was returned."
            )
        )

        else:
            approval_request = None
            status = "stopped"
            message = "Revision workflow finished."

        return {
            "repository_name": result.get("repository_name", ""),
            "task": result.get("task", ""),
            "thread_id": thread_id,
            "status": status,
            "plan": result.get("plan"),
            "repository_analysis": result.get("repository_analysis"),
            "code_proposal": result.get("code_proposal"),
            "review_result": result.get("review_result"),
            "revision_count": result.get("revision_count", 0),
            "approval_request": approval_request,
            "diff_result": result.get("diff_result"),
            "application_result": result.get("application_result"),
            "message": message
        }

    except HTTPException:
        raise

    except Exception as error:
        print(
            f"Human approval failed: "
            f"{type(error).__name__}: {error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to resume DevPilot execution."
        )
