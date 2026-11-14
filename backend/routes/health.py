from fastapi import APIRouter, Request

from backend.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    ready = (
        getattr(request.app.state, "engine", None) is not None
        and getattr(request.app.state, "schedule", None) is not None
    )
    # Don't query the database here: frequent health checks would keep Neon
    # from ever pausing.
    results = getattr(request.app.state, "results", None) is not None
    return HealthResponse(status="ok" if ready else "degraded", puzzle_ready=ready, results=results)
