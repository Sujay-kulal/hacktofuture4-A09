# Google ADK Setup Guide

This guide shows how to connect Google Agent Development Kit (ADK) to this project so you can show a real AI agent at the hackathon.

## What you are building

You already have a working backend platform:

- FastAPI dashboard
- queue
- approvals
- Kubernetes executor
- Gemini explanation and RCA support

ADK adds a real multi-agent layer on top of that platform.

The ADK agents do not replace your backend. They operate it.

## Step 1. Get your Google API key

1. Open Google AI Studio
2. Create or select a project
3. Generate an API key
4. Keep that key ready

The same key can be used in two places:

- `GEMINI_API_KEY` for your FastAPI backend
- `GOOGLE_API_KEY` for Google ADK

## Step 2. Keep the backend running

Open a PowerShell terminal:

```powershell
cd C:\Users\ranja\Downloads\games\codex
.venv\Scripts\Activate.ps1
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/selfheal"
$env:SELFHEAL_KUBE_MODE="mock"
$env:SELFHEAL_TELEMETRY_MODE="mock"
$env:TRACE_URL="http://127.0.0.1:3200"
$env:TRACE_BACKEND="tempo"
$env:OTEL_TRACING_ENABLED="true"
$env:OTEL_SERVICE_NAME="selfheal-api"
$env:OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
$env:GEMINI_API_KEY="your_real_google_ai_api_key"
$env:GEMINI_MODEL="gemini-2.5-flash-lite"
$env:GEMINI_FALLBACK_MODELS="gemini-2.0-flash"
$env:SELFHEAL_AUTOMATION_MODE="hybrid"
uvicorn app.main:app --reload
```

## Step 3. Install Google ADK

Open another PowerShell terminal:

```powershell
cd C:\Users\ranja\Downloads\games\codex
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-adk.txt
```

If `pip install google-adk` fails because of index issues, try:

```powershell
python -m pip install --index-url https://pypi.org/simple google-adk
```

## Step 4. Configure the ADK agent package

Create a file:

`C:\Users\ranja\Downloads\games\codex\adk_selfheal\.env`

with:

```text
GOOGLE_API_KEY=your_real_google_ai_api_key
SELFHEAL_BACKEND_URL=http://127.0.0.1:8000
ADK_GEMINI_MODEL=gemini-2.5-flash-lite
```

## Step 5. Start ADK Web

From the project root:

```powershell
cd C:\Users\ranja\Downloads\games\codex
.venv\Scripts\Activate.ps1
adk web --port 8001
```

## Step 6. Open the ADK interface

Open:

- `http://127.0.0.1:8000/dashboard`
- `http://127.0.0.1:8000/demo-app`
- `http://127.0.0.1:8001`

In the ADK web UI, choose the `adk_selfheal` agent package.

## Step 7. Best demo prompt for judges

In the ADK chat UI, use a prompt like:

```text
Run a full visible self-healing demo. Break the payment dependency, confirm the storefront failure, queue the failure into the platform, run one healing cycle, inspect approvals if any, and explain the result for hackathon judges.
```

## Step 8. What ADK is doing

The ADK agents call these backend tools:

- platform health
- demo topology
- queue inspection
- incident inspection
- approval inspection and resolution
- telemetry collection
- healing cycle execution
- Gemini explanation
- benchmark reporting

So the ADK layer is a real AI agent operating the platform, not just a text generator.

## Step 9. Best hackathon explanation

Say this:

> We use Google ADK to build a real multi-agent control layer for our self-healing cloud platform. Gemini provides the reasoning, while our tools connect the agent to telemetry, approvals, queue management, Kubernetes remediation, and post-incident reporting.

## Step 10. Current limitation

This machine did not fully verify `pip install google-adk` during my run because the install command timed out, so the ADK folder is implemented and ready, but you may still need to complete the package installation locally before running `adk web`.
