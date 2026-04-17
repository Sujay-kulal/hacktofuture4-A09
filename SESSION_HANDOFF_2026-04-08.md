# Session Handoff - 2026-04-08

This file is a simple handoff so we can continue tomorrow without losing context.

## What We Built

We created a fuller MVP for the agentic self-healing Kubernetes platform in this folder:

`C:\Users\ranja\Downloads\games\codex`

Main parts added:

- FastAPI backend
- browser dashboard
- PostgreSQL storage
- Prometheus integration
- Loki integration
- Kubernetes executor
- tests

Important files:

- `app/main.py`
- `app/orchestrator.py`
- `app/repository.py`
- `integrations/telemetry/provider.py`
- `integrations/kubernetes/client.py`
- `frontend/index.html`
- `README.md`

## What Is Working

### Local app code

The project code is scaffolded and updated.

### Tests

The tests passed:

- 5 passed

### Mock mode

The app can run in mock mode with PostgreSQL and the dashboard.

### Monitoring stack installation

We installed monitoring components into Kubernetes:

- Prometheus stack
- Loki

Namespace created:

- `monitoring`

## Commands We Ran

### Project setup

Used this folder:

```powershell
cd C:\Users\ranja\Downloads\games\codex
```

### Python dependencies

Installed with:

```powershell
pip install -r requirements.txt
```

### Tests

Ran:

```powershell
python -m pytest
```

Result:

- all tests passed

### Docker / Postgres

Used:

```powershell
docker compose up -d postgres
```

### Helm install

We had to install Helm first because `helm` was missing.

Chocolatey was available, but it required Administrator PowerShell.

### Monitoring install

Commands used:

```powershell
kubectl create namespace monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install kube-prom-stack prometheus-community/kube-prometheus-stack -n monitoring
helm install loki grafana/loki-stack -n monitoring --set promtail.enabled=true --set grafana.enabled=false
```

## Errors We Hit

### 1. Wrong namespace example

At first:

```powershell
kubectl port-forward -n monitoring ...
```

failed because the namespace did not exist yet.

Root cause:

- `monitoring` namespace was not created yet
- Prometheus/Loki were not installed yet

### 2. Helm missing

Error:

- `helm : The term 'helm' is not recognized`

Root cause:

- Helm was not installed on Windows

### 3. Chocolatey install needed admin rights

Error:

- access denied in Chocolatey

Root cause:

- PowerShell was not elevated as Administrator

### 4. Port-forward failed

Error:

- `unable to forward port because pod is not running`

Root cause:

- the Prometheus and Loki pods were not ready yet

### 5. Monitoring pods still not healthy

Current problem:

- Prometheus pod is still not ready
- Alertmanager is still not ready
- Grafana is still creating
- Loki is closer and now shows `Running`, but still needs verification by port-forward

## Current Kubernetes Status At End Of Session

Latest known status:

```text
alertmanager-kube-prom-stack-kube-prome-alertmanager-0   0/2   Init:0/1
kube-prom-stack-grafana-5cc5779d5c-7vxhl                 0/3   ContainerCreating
kube-prom-stack-kube-prome-operator-78c464645c-zz8xd     0/1   Running
kube-prom-stack-kube-state-metrics-75944f5c87-wssrl      0/1   Running
kube-prom-stack-prometheus-node-exporter-5l5gc           1/1   Running
loki-0                                                   0/1   Running
loki-promtail-rfzc9                                      1/1   Running
prometheus-kube-prom-stack-kube-prome-prometheus-0       0/2   Init:0/1
```

Important finding from `kubectl describe`:

- Prometheus is stuck while pulling or starting:
  `quay.io/prometheus-operator/prometheus-config-reloader:v0.90.1`

This suggests:

- slow image pull
- temporary stuck init container
- local cluster startup slowness

It does **not** look like a missing PVC/storage issue.

## Most Important Next Steps For Tomorrow

### First thing to do

Open PowerShell and go to:

```powershell
cd C:\Users\ranja\Downloads\games\codex
```

### Check pod status again

Run:

```powershell
kubectl get pods -n monitoring
```

### If Prometheus is still stuck

Run:

```powershell
kubectl delete pod -n monitoring prometheus-kube-prom-stack-kube-prome-prometheus-0
```

Then watch:

```powershell
kubectl get pods -n monitoring -w
```

Wait for:

- `prometheus-kube-prom-stack-kube-prome-prometheus-0` to become `2/2 Running`

### Test Loki first

Since Loki was closer to ready, try this:

```powershell
kubectl port-forward -n monitoring svc/loki 3100:3100
```

If this works, keep that terminal open.

### Then test Prometheus

Only after Prometheus becomes ready:

```powershell
kubectl port-forward -n monitoring svc/kube-prom-stack-kube-prome-prometheus 9090:9090
```

### Then start the app in live mode

In another terminal:

```powershell
cd C:\Users\ranja\Downloads\games\codex
.venv\Scripts\Activate.ps1
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/selfheal"
$env:SELFHEAL_KUBE_MODE="cluster"
$env:SELFHEAL_TELEMETRY_MODE="live"
$env:PROMETHEUS_URL="http://127.0.0.1:9090"
$env:LOKI_URL="http://127.0.0.1:3100"
uvicorn app.main:app --reload
```

### Then open dashboard

Open:

- `http://127.0.0.1:8000/dashboard`

### In dashboard tomorrow

Try:

1. `Collect Live Telemetry`
2. enter a real deployment name
3. enter its namespace
4. click collect
5. click `Run One Healing Cycle`

## If Prometheus Is Still Broken Tomorrow

Use these commands and send the outputs:

```powershell
kubectl get pods -n monitoring
kubectl describe pod -n monitoring prometheus-kube-prom-stack-kube-prome-prometheus-0
kubectl get events -n monitoring --sort-by=.lastTimestamp
```

## Easiest Backup Plan

If live mode is still not stable tomorrow, use mock mode so development can continue:

### Terminal 1

```powershell
cd C:\Users\ranja\Downloads\games\codex
docker compose up -d postgres
```

### Terminal 2

```powershell
cd C:\Users\ranja\Downloads\games\codex
.venv\Scripts\Activate.ps1
$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/selfheal"
$env:SELFHEAL_KUBE_MODE="mock"
$env:SELFHEAL_TELEMETRY_MODE="mock"
uvicorn app.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/dashboard`

## Reminder For Tomorrow

The folder is correct.

These commands are **not** failing because of the folder.

They are failing because:

- Helm was initially missing
- monitoring stack was not installed
- Prometheus is not fully ready yet

