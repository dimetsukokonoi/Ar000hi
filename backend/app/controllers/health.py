"""Application health endpoint; no persistence or business workflow."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Arooohi API", "version": "1.0.0"}
