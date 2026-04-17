
# Agentic Self-Healing Cloud for Kubernetes

This project is now a fuller MVP with:

- real FastAPI backend
- PostgreSQL incident storage
- PostgreSQL-backed durable telemetry queue
- browser dashboard
- Prometheus live metric collection
- Loki live log collection
- optional trace backend integration plus local Tempo export
- dependency graph and cascading-failure context
- Kubernetes remediation through the Python Kubernetes client
- optional continuous background monitoring
- optional Gemini-assisted RCA and remediation
- MTTR reporting
- safer governance with blast-radius and protected-namespace checks
- automated tests
- optional Google ADK multi-agent integration

The app can run in two modes:

1. `mock` mode
   This is the easiest way to start. You simulate incidents from the dashboard and the platform stores them in PostgreSQL.

2. `live` mode
   The app queries Prometheus and Loki, detects anomalies for a Kubernetes workload, then executes safe remediation actions through Kubernetes APIs.

3. `live + Gemini` mode
   The app keeps the same safety rules and playbooks, but Gemini can help estimate root cause and choose the safest supported remediation.

## Important Files

- [app/main.py](C:\Users\ranja\Downloads\games\codex\app\main.py)
  This is the backend entrypoint.
- [frontend/index.html](C:\Users\ranja\Downloads\games\codex\frontend\index.html)
  This is the dashboard page.
- [integrations/telemetry/provider.py](C:\Users\ranja\Downloads\games\codex\integrations\telemetry\provider.py)
  This collects live Prometheus and Loki data and turns it into incidents.
- [integrations/tracing/client.py](C:\Users\ranja\Downloads\games\codex\integrations\tracing\client.py)
  This connects to Tempo or Jaeger for trace error signals.
- [app/telemetry_queue.py](C:\Users\ranja\Downloads\games\codex\app\telemetry_queue.py)
  This stores telemetry events durably in PostgreSQL until they are processed.
- [integrations/kubernetes/client.py](C:\Users\ranja\Downloads\games\codex\integrations\kubernetes\client.py)
  This performs restart and scale actions against Kubernetes.
- [dependencies/default.yaml](C:\Users\ranja\Downloads\games\codex\dependencies\default.yaml)
  This defines service dependencies and possible cascading impact.
- [deploy/cloud/CLOUD_DEPLOYMENT_GUIDE.md](C:\Users\ranja\Downloads\games\codex\deploy\cloud\CLOUD_DEPLOYMENT_GUIDE.md)
  This explains how to deploy on EKS, AKS, and GKE.
- [ADK_SETUP_GUIDE.md](C:\Users\ranja\Downloads\games\codex\ADK_SETUP_GUIDE.md)
  This explains how to run the project with Google ADK as a real agent layer.
- [adk_selfheal/agent.py](C:\Users\ranja\Downloads\games\codex\adk_selfheal\agent.py)
  This defines the Google ADK root agent and specialist sub-agents.
- [deploy/local/tempo.yaml](C:\Users\ranja\Downloads\games\codex\deploy\local\tempo.yaml)
  This starts a local Tempo backend for trace ingestion and search.
- [deploy/k8s/demo-microservices.yaml](C:\Users\ranja\Downloads\games\codex\deploy\k8s\demo-microservices.yaml)
  This deploys a larger demo topology in Kubernetes.
- [app/repository.py](C:\Users\ranja\Downloads\games\codex\app\repository.py)
  This stores and reads incidents from PostgreSQL.
- [playbooks/default.yaml](C:\Users\ranja\Downloads\games\codex\playbooks\default.yaml)
  This maps incident types to remediation actions.
- [policies/default.yaml](C:\Users\ranja\Downloads\games\codex\policies\default.yaml)
  This decides which actions are allowed.
- [.env.example](C:\Users\ranja\Downloads\games\codex\.env.example)
  This shows the environment variables you can set.

## What You Need Installed

- Python 3.11 or newer
- Docker Desktop
- Optional for real Kubernetes mode:
  - `kubectl`
  - access to a cluster such as EKS, AKS, GKE, `kind`, or `minikube`
  - Prometheus reachable from your machine
  - Loki reachable from your machine
  - optional Tempo reachable from your machine

## Folder Structure

```text
app/                    backend API, orchestration, database layer
agents/                 monitor, RCA, remediation, verification
integrations/           Prometheus, Loki, Kubernetes integrations
frontend/               dashboard HTML, CSS, JS
policies/               safety rules
playbooks/              remediation mappings
deploy/k8s/             example Kubernetes manifests
deploy/local/           local tracing configs
tests/                  pytest test cases
```

## Easiest Run Path: Mock Mode

Use this first if you mainly want to see the platform working.

### Terminal 1: Start PostgreSQL

Open PowerShell in:

```powershell
C:\Users\ranja\Downloads\games\codex
```

Run:

```powershell
docker compose up -d postgres
```

What this does:

- starts PostgreSQL
- opens database port `5432`
- creates database `selfheal`
- creates username `postgres`
- creates password `postgres`

### Optional: Start Local Tempo For Tracing

If you want real local trace export and search:

```powershell
docker compose up -d tempo
```

### Terminal 2: Start the Backend

Open another PowerShell in:

```powershell
C:\Users\ranja\Downloads\games\codex
```

Run these commands one by one:

```powershell
python -m venv .venv
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
uvicorn app.main:app --reload
```

What this terminal is doing:

- creates the Python environment
- installs FastAPI, SQLAlchemy, psycopg, Kubernetes client, and pytest
- connects the app to PostgreSQL
- starts the backend on `http://127.0.0.1:8000`
- stores telemetry durably in PostgreSQL
- exports traces to Tempo if tracing is enabled

### Browser

Open:

- [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)
- [http://127.0.0.1:8000/demo-app](http://127.0.0.1:8000/demo-app)

What to click:

1. In `Simulate Incident`, choose `crashloop`
2. Click `Queue Simulated Incident`
3. Click `Run One Healing Cycle`
4. Scroll down to `Incidents`

You should see:

- the incident saved in PostgreSQL
- root cause analysis
- remediation action
- verification result

For the visible break-and-recover demo:

1. Open [http://127.0.0.1:8000/demo-app](http://127.0.0.1:8000/demo-app)
2. Click `Break Payment Dependency`
3. Click `Place Test Order`
4. Click `Send Failure To Self-Healing Platform`
5. Open the dashboard and click `Run One Healing Cycle`
6. Go back to the demo app and click `Place Test Order` again

## Real Mode: Prometheus + Loki + Kubernetes

Use this after mock mode is working.

The app needs:

- Prometheus URL
- Loki URL
- optional Tempo or Jaeger URL
- Kubernetes access from your machine

### Before Starting

Make sure these are true:

- `kubectl get pods -A` works on your machine
- Prometheus is reachable
- Loki is reachable

If Prometheus and Loki are already exposed inside your cluster but not on your laptop, use port-forwarding.

### Optional: Deploy A Larger Demo Topology

If you want a bigger local microservice environment before EKS:

```powershell
kubectl apply -f deploy\k8s\demo-microservices.yaml
kubectl get deployments -n demo
```

### Terminal 1: Keep PostgreSQL Running

If it is not already running:

```powershell
cd C:\Users\ranja\Downloads\games\codex
docker compose up -d postgres
```

### Terminal 2: Port-Forward Prometheus

Example command:

```powershell
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```

If your service name is different, use your actual Prometheus service name.

### Terminal 3: Port-Forward Loki

Example command:

```powershell
kubectl port-forward -n monitoring svc/loki 3100:3100
```

If your Loki service name is different, use your actual Loki service name.

### Terminal 4: Start the Backend in Live Mode

Open PowerShell in:

```powershell
C:\Users\ranja\Downloads\games\codex
```

Run:

```powershell
.venv\Scripts\Activate.ps1
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/selfheal"
$env:SELFHEAL_KUBE_MODE="cluster"
$env:SELFHEAL_TELEMETRY_MODE="live"
$env:PROMETHEUS_URL="http://127.0.0.1:9090"
$env:LOKI_URL="http://127.0.0.1:3100"
$env:TRACE_URL="http://127.0.0.1:3200"
$env:TRACE_BACKEND="tempo"
$env:SELFHEAL_BACKGROUND_MONITORING="true"
$env:SELFHEAL_MONITOR_INTERVAL_SECONDS="30"
$env:SELFHEAL_MONITOR_MAX_EVENTS_PER_SCAN="5"
$env:SELFHEAL_MONITOR_MAX_QUEUE_DEPTH="25"
$env:OTEL_TRACING_ENABLED="true"
$env:OTEL_SERVICE_NAME="selfheal-api"
$env:OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318"
uvicorn app.main:app --reload
```

What changes in live mode:

- the dashboard can call Prometheus and Loki through the backend
- the backend can optionally query Tempo or Jaeger traces
- the backend can talk to your Kubernetes cluster
- the background monitor can scan workloads continuously
- the background monitor now has queue-depth and per-scan safety limits
- remediation actions become real Kubernetes API calls

### Optional: Turn On Gemini Automation

If you want Gemini to help with root-cause analysis and remediation choice, set these before starting the backend:

```powershell
$env:GEMINI_API_KEY="your_google_ai_api_key"
$env:GEMINI_MODEL="gemini-2.5-flash"
$env:GEMINI_FALLBACK_MODELS="gemini-2.0-flash"
$env:GEMINI_MAX_RETRIES="3"
```

Notes:

- if Gemini is configured, the backend still falls back to local rule-based logic if the API call fails
- policies still run after Gemini, so blocked actions stay blocked
- this project uses Google AI Studio style API access through the Gemini `generateContent` endpoint
- the app now retries temporary Gemini failures and can try fallback models if the primary model is overloaded

### Browser in Live Mode

Open:

- [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)

In `Collect Live Telemetry`:

1. type the deployment name in `Service`
2. type the namespace in `Namespace`
3. click `Pull From Prometheus/Loki`
4. click `Run One Healing Cycle`

If an anomaly is detected, the app will:

- create an incident
- estimate a root cause
- include dependency and trace context when available
- choose an action from [playbooks/default.yaml](C:\Users\ranja\Downloads\games\codex\playbooks\default.yaml)
- check [policies/default.yaml](C:\Users\ranja\Downloads\games\codex\policies\default.yaml)
- run the action through [integrations/kubernetes/client.py](C:\Users\ranja\Downloads\games\codex\integrations\kubernetes\client.py)
- save the incident to PostgreSQL

### Continuous Monitoring

If you want the system to scan workloads in the background instead of only when you click buttons, set:

```powershell
$env:SELFHEAL_BACKGROUND_MONITORING="true"
$env:SELFHEAL_MONITOR_INTERVAL_SECONDS="30"
$env:SELFHEAL_MONITOR_NAMESPACES="default,monitoring"
$env:SELFHEAL_MONITOR_MAX_EVENTS_PER_SCAN="5"
$env:SELFHEAL_MONITOR_MAX_QUEUE_DEPTH="25"
```

When this is enabled:

- the backend periodically scans workloads from the cluster
- any detected anomaly is queued automatically
- the backend can immediately run the healing loop in the background
- the queue survives backend restarts because it is stored in PostgreSQL
- the dashboard shows monitor status in the `Monitoring Status` panel

## Available API Endpoints

- `GET /dashboard`
  Opens the web dashboard.
- `GET /health`
  Shows app health, telemetry mode, and Kubernetes mode.
- `GET /incidents`
  Lists saved incidents from PostgreSQL.
- `GET /reports/mttr`
  Shows MTTR and recovery statistics.
- `GET /dependencies`
  Lists the loaded service dependency graph.
- `GET /monitoring/status`
  Shows continuous monitor status.
- `POST /incidents/simulate`
  Queues a fake incident.
- `POST /telemetry/collect/demo`
  Queues the visible storefront failure into the self-healing pipeline.
- `POST /telemetry/collect/live`
  Pulls telemetry from Prometheus and Loki for a service and queues an incident if an anomaly is found.
- `POST /loop/run-once`
  Runs one full self-healing cycle.
- `GET /dashboard/summary`
  Returns counts and workload status for the dashboard.

## Which Actions Are Real Right Now

Implemented in [integrations/kubernetes/client.py](C:\Users\ranja\Downloads\games\codex\integrations\kubernetes\client.py):

- `restart_deployment`
- `scale_deployment`

Not fully automated yet:

- `rollback_deployment`

In the current MVP, rollback is intentionally not executed automatically because it needs more safety logic.

## Playbooks and Policies

Playbooks are in:

- [playbooks/default.yaml](C:\Users\ranja\Downloads\games\codex\playbooks\default.yaml)

Examples:

- `crashloop -> restart_deployment`
- `oomkill -> scale_deployment`
- `high-latency -> scale_deployment`
- `failed-rollout -> restart_deployment`

Policies are in:

- [policies/default.yaml](C:\Users\ranja\Downloads\games\codex\policies\default.yaml)

Examples:

- block destructive actions
- limit max scale-up replicas
- allow only known safe actions
- restrict namespaces by RBAC scope
- require approval for protected namespaces or large blast radius

## Running Tests

Open PowerShell in:

```powershell
C:\Users\ranja\Downloads\games\codex
```

Run:

```powershell
.venv\Scripts\Activate.ps1
python -m pytest
```

Tests included:

- [tests/test_policy_engine.py](C:\Users\ranja\Downloads\games\codex\tests\test_policy_engine.py)
- [tests/test_repository.py](C:\Users\ranja\Downloads\games\codex\tests\test_repository.py)
- [tests/test_live_telemetry.py](C:\Users\ranja\Downloads\games\codex\tests\test_live_telemetry.py)
- [tests/test_orchestrator.py](C:\Users\ranja\Downloads\games\codex\tests\test_orchestrator.py)

## One-Command Docker Option

If you want Docker to run both PostgreSQL and the backend:

```powershell
docker compose up --build
```

Then open:

- [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)

This Docker path uses:

- PostgreSQL container
- Tempo container
- backend container
- mock telemetry mode by default

## Troubleshooting

### Problem: `connection refused` to PostgreSQL

Check:

```powershell
docker compose ps
```

Make sure `postgres` is running.

### Problem: traces are not showing up

Check:

```powershell
docker compose ps
Test-NetConnection 127.0.0.1 -Port 4318
Test-NetConnection 127.0.0.1 -Port 3200
```

Make sure `tempo` is running and both ports are open.

### Problem: dashboard opens but live collection says no anomaly detected

Possible reasons:

- Prometheus query did not match your metric names
- Loki labels do not match `namespace` and `app`
- the service is healthy so nothing triggered

If needed, adjust these in [app/config.py](C:\Users\ranja\Downloads\games\codex\app\config.py):

- `PROM_RESTART_QUERY`
- `PROM_READY_QUERY`
- `PROM_DESIRED_QUERY`
- `PROM_ERROR_RATE_QUERY`
- `PROM_LATENCY_QUERY`
- `LOKI_ERROR_QUERY`
- `TEMPO_TRACEQL_QUERY`
- `TRACE_ERROR_THRESHOLD`

### Problem: Kubernetes remediation is not happening

Check:

```powershell
kubectl get deploy -A
```

Make sure:

- `SELFHEAL_KUBE_MODE=cluster`
- your `Service` field matches a real Kubernetes deployment name
- your kube context is pointing to the correct cluster

## Current Limitations

- rollback is still not executed automatically by the Kubernetes executor
- Prometheus metric names are different across teams, so you may need to customize query templates
- Loki log labels vary by environment, so the default query may need adjustment
- traces require a running Tempo or Jaeger backend plus instrumented workloads for a full trace-driven RCA demo
- incidents and the telemetry queue are both stored durably in PostgreSQL
- dependency graph quality depends on how well you maintain [dependencies/default.yaml](C:\Users\ranja\Downloads\games\codex\dependencies\default.yaml)
- the default Gemini model in `.env.example` may need updating if Google changes model names
