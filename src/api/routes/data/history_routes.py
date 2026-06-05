"""History routes for recent data import runs."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from src.api.routes.data.directory_routes import DataDirectoryRequest, run_directory_import
from src.api.routes.data.import_run_store import get_import_run, list_recent_import_runs

router = APIRouter(prefix="/api/v1/data", tags=["data"])


@router.get("/import-runs")
async def get_recent_import_runs(limit: int = Query(default=10, ge=1, le=100)):
    """List recent import run summaries."""
    return {
        "success": True,
        "runs": list_recent_import_runs(limit=limit),
    }


@router.post("/import-runs/{run_id}/retry")
async def retry_import_run(run_id: str):
    """Retry one supported import run from stored request metadata."""
    run = get_import_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Import run not found: {run_id}")

    if run.get("run_type") != "directory_import":
        raise HTTPException(
            status_code=400,
            detail=f"Retry is not supported for run type: {run.get('run_type')}",
        )

    retry_request = run.get("retry_request")
    if not isinstance(retry_request, dict):
        raise HTTPException(
            status_code=400,
            detail="Retry is unavailable because this import run does not contain replayable request data",
        )

    try:
        request = DataDirectoryRequest.model_validate(retry_request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Stored retry request is invalid: {exc}",
        ) from exc

    result = await run_directory_import(request, retry_of=run["id"])
    return {
        "success": True,
        "source_run_id": run["id"],
        "result": result,
    }
