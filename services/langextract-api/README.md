# LangExtract API Service (Railway)

FastAPI wrapper around `langextract` for authenticated HTTP extraction requests.

## Endpoints

- `GET /healthz`
- `GET /readyz`
- `POST /v1/extract` (requires `x-api-key`)

## Required environment variables

- `SERVICE_API_KEY`: inbound auth key for clients
- `LANGEXTRACT_API_KEY`: model provider key (Gemini default)

## Optional environment variables

- `DEFAULT_MODEL_ID` (default: `gemini-2.5-flash`)
- `REQUEST_TIMEOUT_SECONDS` (default: `120`)
- `MAX_CONCURRENCY` (default: `4`)
- `MAX_TEXT_CHARS` (default: `100000`)
- `MAX_EXAMPLES` (default: `50`)
- `MAX_WORKERS` (default: `20`)

## Local run

```bash
cd services/langextract-api
pip install -r requirements.txt
SERVICE_API_KEY=local-dev LANGEXTRACT_API_KEY=your-key uvicorn app.main:app --reload
```

## Example request

```bash
curl -X POST "http://localhost:8000/v1/extract" \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-dev" \
  -d '{
    "text":"ROMEO meets JULIET.",
    "prompt_description":"Extract characters.",
    "examples":[
      {
        "text":"ROMEO says hi.",
        "extractions":[
          {"extraction_class":"character","extraction_text":"ROMEO"}
        ]
      }
    ]
  }'
```

## Railway deploy through GitHub

1. Create a Railway service connected to this repo.
2. Set the service root to `services/langextract-api`.
3. Keep config file as `services/langextract-api/railway.toml`.
4. Set `SERVICE_API_KEY` and `LANGEXTRACT_API_KEY` in Railway Variables.
5. Enable autodeploy from your target branch.
