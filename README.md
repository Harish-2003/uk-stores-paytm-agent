# UK Stores, Srikakulam: dashboard + Paytm voice agent

## Run the backend (uv)
```
cd backend
cp .env.example .env        # add GROQ_API_KEY
uv sync                     # creates .venv and installs from pyproject.toml
uv run uvicorn main:app --reload --port 8000
```
Add a package later with `uv add <name>`.

## Run the frontend
```
cd frontend
npm install
npm run dev                 # http://localhost:5173 (proxies /api to port 8000)
```

## Paytm MCP
Paytm's remote MCP needs access requested from Paytm (they issue a Client ID and token). Put them in `.env` as
PAYTM_MCP_CLIENT_ID / PAYTM_MCP_TOKEN. Until then the Paytm buttons run in demo mode on mock data.
Groq calls the MCP server for you through its Responses API.

## Deploy for free on Render
1. Push this project to a private GitHub repository. Do not commit `backend/.env`; `.gitignore` excludes it.
2. In Render, choose **New → Blueprint**, connect the repository, and deploy the `render.yaml` Blueprint.
3. Open the deployed service URL. The dashboard runs with demo data; the voice agent stays disabled until `GROQ_API_KEY` is configured.

The free web service may spin down after inactivity, so the first visit can take a little while to load. The app currently has no login. Do not add a billable Groq key to a public deployment until access is protected.

## Untested
Not run against live Groq or Paytm. Check that Groq accepts Paytm's /sse/ URL; if not, run Paytm's local MCP server
(github.com/paytm/payment-mcp-server) behind an HTTPS endpoint and set PAYTM_MCP_URL.
