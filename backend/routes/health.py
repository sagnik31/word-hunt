from fastapi import APIRouter, Request

from backend.schemas import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    engine = getattr(request.app.state, "engine", None)
    return HealthResponse(
        status="ok" if engine is not None else "degraded",
        target_word_loaded=engine is not None,
    )
