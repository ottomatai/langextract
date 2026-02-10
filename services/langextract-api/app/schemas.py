"""Request/response schemas for the LangExtract API."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class ExtractionExample(BaseModel):
  text: str = Field(..., min_length=1)
  extractions: List[Dict[str, Any]] = Field(default_factory=list)


class ExtractRequest(BaseModel):
  text: str = Field(..., min_length=1)
  prompt_description: str = Field(..., min_length=1)
  examples: List[ExtractionExample] = Field(..., min_length=1)
  model_id: str = Field(default="gemini-2.5-flash", min_length=1)
  extraction_passes: Optional[int] = Field(default=1, ge=1, le=5)
  max_workers: Optional[int] = Field(default=10, ge=1, le=20)
  max_char_buffer: Optional[int] = Field(default=1000, ge=100, le=5000)
  language_model_params: Optional[Dict[str, Any]] = Field(default=None)
  output_format: str = Field(default="json")


class ExtractResponse(BaseModel):
  request_id: str
  timing_ms: int
  result: Dict[str, Any]
  markdown: Optional[str] = None
