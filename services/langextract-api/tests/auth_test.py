from __future__ import annotations

from fastapi.testclient import TestClient

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


def test_missing_api_key_returns_401() -> None:
  res = client.post("/v1/extract", json=_payload())
  assert res.status_code == 401


def test_invalid_api_key_returns_401() -> None:
  res = client.post(
      "/v1/extract",
      headers={"x-api-key": "wrong"},
      json=_payload(),
  )
  assert res.status_code == 401
