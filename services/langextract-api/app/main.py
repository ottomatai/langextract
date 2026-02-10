"""FastAPI app exposing LangExtract via HTTP."""

from __future__ import annotations

import asyncio
import dataclasses
import io
import json
import logging
import time
import traceback
import uuid
from typing import Any
from typing import Dict
from typing import List

from fastapi import Depends
from fastapi import File
from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi import status
from fastapi.responses import JSONResponse
import langextract as lx

from app.auth import require_api_key
from app.schemas import ExtractRequest
from app.schemas import ExtractResponse
from app.schemas import ExtractionExample
from app import settings

app = FastAPI(title="LangExtract API", version="1.0.0")
_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENCY)
logger = logging.getLogger("langextract_api")
if not logger.handlers:
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s %(levelname)s %(name)s %(message)s",
  )


def _validate_language_model_params(
    params: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
  if params is None:
    return None

  allowed_keys = {
      "temperature",
      "vertexai",
      "batch",
      "http_options",
      "top_p",
      "max_output_tokens",
      "candidate_count",
      "safety_settings",
  }
  unknown = set(params.keys()) - allowed_keys
  if unknown:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported language_model_params keys: {sorted(unknown)}",
    )
  return params


def _to_json(value: Any) -> Any:
  if dataclasses.is_dataclass(value):
    return dataclasses.asdict(value)
  if isinstance(value, list):
    return [_to_json(v) for v in value]
  if isinstance(value, dict):
    return {k: _to_json(v) for k, v in value.items()}
  if hasattr(value, "__dict__"):
    return _to_json(vars(value))
  return value


def _normalize_result(result: Any) -> Dict[str, Any]:
  if isinstance(result, list):
    return {"documents": _to_json(result)}
  return {"document": _to_json(result)}


def _build_examples(payload_examples: Any) -> list[Any]:
  built_examples = []
  for example in payload_examples:
    raw_extractions = []
    for extraction in example.extractions:
      extraction_class = extraction.get("extraction_class")
      extraction_text = extraction.get("extraction_text")
      if not extraction_class or not extraction_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Each extraction in examples must include "
                "'extraction_class' and 'extraction_text'."
            ),
        )
      raw_extractions.append(
          lx.data.Extraction(
              extraction_class=extraction_class,
              extraction_text=extraction_text,
              attributes=extraction.get("attributes"),
              description=extraction.get("description"),
          )
      )
    built_examples.append(
      lx.data.ExampleData(text=example.text, extractions=raw_extractions)
    )
  return built_examples


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
  try:
    from pypdf import PdfReader
  except Exception as exc:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="PDF support dependency unavailable.",
    ) from exc

  reader = PdfReader(io.BytesIO(pdf_bytes))
  parts = []
  for page in reader.pages:
    parts.append(page.extract_text() or "")
  return "\n\n".join(parts).strip()


@app.get("/healthz")
def healthz() -> Dict[str, bool]:
  return {"ok": True}


@app.get("/readyz")
def readyz() -> JSONResponse:
  missing: List[str] = []
  if not settings.SERVICE_API_KEY:
    missing.append("SERVICE_API_KEY")
  if not settings.LANGEXTRACT_API_KEY:
    missing.append("LANGEXTRACT_API_KEY")

  if missing:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"ready": False, "missing": missing},
    )
  return JSONResponse(status_code=status.HTTP_200_OK, content={"ready": True})


@app.post("/v1/extract", response_model=ExtractResponse)
async def extract_endpoint(
    payload: ExtractRequest, _: None = Depends(require_api_key)
) -> ExtractResponse:
  request_id = str(uuid.uuid4())
  logger.info(
      "extract_request_started request_id=%s model_id=%s text_len=%s examples=%s",
      request_id,
      payload.model_id,
      len(payload.text),
      len(payload.examples),
  )
  if len(payload.text) > settings.MAX_TEXT_CHARS:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"text exceeds MAX_TEXT_CHARS={settings.MAX_TEXT_CHARS}",
    )
  if len(payload.examples) > settings.MAX_EXAMPLES:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"examples exceed MAX_EXAMPLES={settings.MAX_EXAMPLES}",
    )
  if payload.max_workers and payload.max_workers > settings.MAX_WORKERS:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"max_workers exceeds MAX_WORKERS={settings.MAX_WORKERS}",
    )

  lm_params = _validate_language_model_params(payload.language_model_params)
  started = time.perf_counter()
  examples_payload = _build_examples(payload.examples)

  async with _semaphore:
    try:
      result = await asyncio.wait_for(
          asyncio.to_thread(
              lx.extract,
              text_or_documents=payload.text,
              prompt_description=payload.prompt_description,
              examples=examples_payload,
              model_id=payload.model_id or settings.DEFAULT_MODEL_ID,
              api_key=settings.LANGEXTRACT_API_KEY,
              extraction_passes=payload.extraction_passes,
              max_workers=payload.max_workers,
              max_char_buffer=payload.max_char_buffer,
              language_model_params=lm_params,
              show_progress=False,
          ),
          timeout=settings.REQUEST_TIMEOUT_SECONDS,
      )
    except asyncio.TimeoutError as exc:
      logger.error(
          "extract_request_timeout request_id=%s timeout_seconds=%s",
          request_id,
          settings.REQUEST_TIMEOUT_SECONDS,
      )
      raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail=f"Request timed out. request_id={request_id}",
      ) from exc
    except HTTPException:
      logger.exception("extract_request_http_exception request_id=%s", request_id)
      raise
    except Exception as exc:
      logger.error(
          "extract_request_failed request_id=%s error=%s traceback=%s",
          request_id,
          repr(exc),
          traceback.format_exc(),
      )
      raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail=f"Extraction failed. request_id={request_id}",
      ) from exc

  timing_ms = int((time.perf_counter() - started) * 1000)
  logger.info(
      "extract_request_succeeded request_id=%s timing_ms=%s", request_id, timing_ms
  )
  return ExtractResponse(
      request_id=request_id, timing_ms=timing_ms, result=_normalize_result(result)
  )


@app.post("/v1/extract-pdf", response_model=ExtractResponse)
async def extract_pdf_endpoint(
    file: UploadFile = File(...),
    prompt_description: str = Form(...),
    examples_json: str = Form(...),
    model_id: str = Form(default=settings.DEFAULT_MODEL_ID),
    extraction_passes: int = Form(default=1),
    max_workers: int = Form(default=10),
    max_char_buffer: int = Form(default=1000),
    _: None = Depends(require_api_key),
) -> ExtractResponse:
  request_id = str(uuid.uuid4())
  logger.info(
      "extract_pdf_request_started request_id=%s model_id=%s filename=%s",
      request_id,
      model_id,
      file.filename,
  )

  if not file.filename or not file.filename.lower().endswith(".pdf"):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Only PDF files are supported.",
    )

  if max_workers > settings.MAX_WORKERS:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"max_workers exceeds MAX_WORKERS={settings.MAX_WORKERS}",
    )

  try:
    examples_raw = json.loads(examples_json)
  except json.JSONDecodeError as exc:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="examples_json must be valid JSON.",
    ) from exc

  if not isinstance(examples_raw, list) or not examples_raw:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="examples_json must be a non-empty JSON array.",
    )

  try:
    examples_models = [ExtractionExample.model_validate(x) for x in examples_raw]
  except Exception as exc:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid examples_json format: {exc}",
    ) from exc

  pdf_bytes = await file.read()
  if not pdf_bytes:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
    )

  text = _extract_text_from_pdf_bytes(pdf_bytes)
  if not text:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Could not extract text from PDF.",
    )
  if len(text) > settings.MAX_TEXT_CHARS:
    text = text[: settings.MAX_TEXT_CHARS]

  examples_payload = _build_examples(examples_models)
  started = time.perf_counter()

  async with _semaphore:
    try:
      result = await asyncio.wait_for(
          asyncio.to_thread(
              lx.extract,
              text_or_documents=text,
              prompt_description=prompt_description,
              examples=examples_payload,
              model_id=model_id or settings.DEFAULT_MODEL_ID,
              api_key=settings.LANGEXTRACT_API_KEY,
              extraction_passes=extraction_passes,
              max_workers=max_workers,
              max_char_buffer=max_char_buffer,
              show_progress=False,
          ),
          timeout=settings.REQUEST_TIMEOUT_SECONDS,
      )
    except Exception as exc:
      logger.error(
          "extract_pdf_request_failed request_id=%s error=%s traceback=%s",
          request_id,
          repr(exc),
          traceback.format_exc(),
      )
      raise HTTPException(
          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
          detail=f"Extraction failed. request_id={request_id}",
      ) from exc

  timing_ms = int((time.perf_counter() - started) * 1000)
  logger.info(
      "extract_pdf_request_succeeded request_id=%s timing_ms=%s text_len=%s",
      request_id,
      timing_ms,
      len(text),
  )
  return ExtractResponse(
      request_id=request_id, timing_ms=timing_ms, result=_normalize_result(result)
  )
