"""Translate model failures to the existing public JSON error format."""

from fastapi import Request
from fastapi.responses import JSONResponse
from app.models.errors import DomainError


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
