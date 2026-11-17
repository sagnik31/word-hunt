from fastapi import APIRouter, Request, Response

from backend.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request, response: Response) -> HealthResponse:
    ready = (
        getattr(request.app.state, "engine", None) is not None
        and getattr(request.app.state, "schedule", None) is not None
    )
    # 503 when degraded, so Render's health check fails a broken deploy and
    # keeps the previous one running.
    if not ready:
        response.status_code = 503
    # Don't query the database here: frequent health checks would keep Neon
    # from ever pausing.
    results = getattr(request.app.state, "results", None) is not None
    return HealthResponse(status="ok" if ready else "degraded", puzzle_ready=ready, results=results)
