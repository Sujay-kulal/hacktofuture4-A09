# Local Final Runbook

## 1. Start local dependencies

### Terminal 1
```powershell
cd C:\Users\ranja\Downloads\games\codex
docker compose up -d postgres tempo
```

## 2. Start the backend

### Terminal 2
```powershell
cd C:\Users\ranja\Downloads\games\codex
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/selfheal"
$env:SELFHEAL_KUBE_MODE="mock"
$env:SELFHEAL_TELEMETRY_MODE="mock"
$env:TRACE_URL="http://127.0.0.1:3200"
$env:TRACE_BACKEND="tempo"
$env:OTEL_TRACING_ENABLED="true"
$env:OTEL_SERVICE_NAME="selfheal-api"
$env:OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
$env:GEMINI_API_KEY="your_real_google_ai_api_key"
$env:GEMINI_MODEL="gemini-2.5-flash"
$env:GEMINI_FALLBACK_MODELS="gemini-2.0-flash"
$env:SELFHEAL_AUTOMATION_MODE="hybrid"
uvicorn app.main:app --reload
```

## 3. Open the websites

- Dashboard: `http://127.0.0.1:8000/dashboard`
- Demo app: `http://127.0.0.1:8000/demo-app`
- Health: `http://127.0.0.1:8000/health`

## 4. Strongest demo flow

### Demo website
1. Click `Break Payment Dependency`, `Break Inventory`, or `Break Auth`
2. Click `Place Test Order`
3. Click `Send Failure To Self-Healing Platform`
4. Show `Service Topology`
5. Show `Recent Trace Path`

### Dashboard website
1. Click `Run One Healing Cycle`
2. Show `Gemini AI Brain`
3. Show `Queue Overview`
4. Show `Approvals` if a risky action is pending
5. Show `Impact View`
6. Show `Benchmark Report`
7. Click `Explain Last Incident With Gemini`

### Back to demo website
1. Click `Place Test Order` again
2. Show recovery

## 5. If you want to test approval flow

Use a rollout or rollback-style incident in a protected namespace so the dashboard shows a pending approval. Then use:
- `Approve`
- `Reject`
- `Retry`
- `Escalate`

## 6. If you want to inspect the queue

Open the dashboard and use `Queue Overview`.

- `queued`: waiting for processing
- `claimed`: currently being processed
- `processed`: finished
- `dead_letter`: failed too many times

Use `Requeue` on a dead-letter item to send it back through the system.

## 7. Kubernetes manifests for later cloud deployment

Apply these when you move to a real cluster:
- `deploy\k8s\namespace.yaml`
- `deploy\k8s\serviceaccount.yaml`
- `deploy\k8s\clusterrole.yaml`
- `deploy\k8s\clusterrolebinding.yaml`
- `deploy\k8s\networkpolicy.yaml`
- `deploy\k8s\secret.example.yaml` (copy and replace values first)
- `deploy\k8s\deployment.yaml`
- `deploy\k8s\service.yaml`

## 8. What is now left

The next major step is AWS EKS deployment and validation.
