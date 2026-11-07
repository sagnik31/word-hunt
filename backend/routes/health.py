from fastapi import APIRouter, Request

from backend.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    ready = (
        getattr(request.app.state, "engine", None) is not None
        and getattr(request.app.state, "schedule", None) is not None
    )
    return HealthResponse(status="ok" if ready else "degraded", puzzle_ready=ready)
