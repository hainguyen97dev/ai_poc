# Agent Console

Standalone local web UI for exercising role-based agents in this repository.
It is intentionally separate from `agent-sa/` so additional agent services can
be registered later without embedding a UI in each backend.

## Run locally

Start the ADA backend in one terminal:

```bash
cd agent-sa
source .venv312/bin/activate
python -m uvicorn ada-service.main:app --reload --port 8000
```

Serve the console from the repository root in another terminal:

```bash
python3 -m http.server 5173 --directory agent-console
```

Open <http://127.0.0.1:5173>.

## Register another agent

Add an entry to `agents.json` with its display metadata, base URL, and endpoint
paths. The current request builder implements the `ada-v1` protocol. A backend
with a different request/response contract should add a protocol adapter in
`app.js`; the agent selector, health state, result inspector, and registry do
not need to change.

The backend must allow the console origin through CORS during local development.
ADA currently allows it through its existing FastAPI CORS configuration.
