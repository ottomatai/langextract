"""Configuration for the LangExtract API service."""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
  raw = os.getenv(name)
  if raw is None:
    return default
  try:
    return int(raw)
  except ValueError:
    return default


SERVICE_API_KEY = os.getenv("SERVICE_API_KEY", "")
LANGEXTRACT_API_KEY = os.getenv("LANGEXTRACT_API_KEY", "")

DEFAULT_MODEL_ID = os.getenv("DEFAULT_MODEL_ID", "gemini-2.5-flash")
REQUEST_TIMEOUT_SECONDS = _int_env("REQUEST_TIMEOUT_SECONDS", 120)
MAX_CONCURRENCY = _int_env("MAX_CONCURRENCY", 4)
MAX_TEXT_CHARS = _int_env("MAX_TEXT_CHARS", 100000)
MAX_EXAMPLES = _int_env("MAX_EXAMPLES", 50)
MAX_WORKERS = _int_env("MAX_WORKERS", 20)
