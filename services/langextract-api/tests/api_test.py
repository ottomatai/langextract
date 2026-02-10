from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app


client = TestClient(app)


def _payload() -> dict:
  return {
      "text": "ROMEO meets JULIET.",
      "prompt_description": "Extract characters.",
      "examples": [
          {
              "text": "ROMEO says hi.",
              "extractions": [
                  {"extraction_class": "character", "extraction_text": "ROMEO"}
              ],
          }
      ],
  }


def test_healthz() -> None:
  res = client.get("/healthz")
  assert res.status_code == 200
  assert res.json() == {"ok": True}


def test_readyz() -> None:
  res = client.get("/readyz")
  assert res.status_code == 200
  assert res.json() == {"ready": True}


def test_extract_success(monkeypatch: pytest.MonkeyPatch) -> None:
  class _DummyResult:
    def __init__(self) -> None:
      self.document_id = "doc_123"
      self.text = "ROMEO meets JULIET."
      self.extractions = []

  def fake_extract(**kwargs):  # type: ignore[no-untyped-def]
    assert kwargs["model_id"]
    return _DummyResult()

  monkeypatch.setattr("app.main.lx.extract", fake_extract)
  res = client.post(
      "/v1/extract", headers={"x-api-key": "test-service-key"}, json=_payload()
  )
  assert res.status_code == 200
  body = res.json()
  assert "request_id" in body
  assert "timing_ms" in body
  assert "result" in body
  assert "document" in body["result"]


def test_extract_invalid_language_model_params_key() -> None:
  payload = _payload()
  payload["language_model_params"] = {"not_allowed": True}
  res = client.post(
      "/v1/extract", headers={"x-api-key": "test-service-key"}, json=payload
  )
  assert res.status_code == 400
