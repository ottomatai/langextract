"""Authentication helpers for API key auth."""

from __future__ import annotations

import secrets

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from app import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
  if not settings.SERVICE_API_KEY:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="SERVICE_API_KEY is not configured.",
    )

  if not x_api_key or not secrets.compare_digest(
      x_api_key, settings.SERVICE_API_KEY
  ):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )
