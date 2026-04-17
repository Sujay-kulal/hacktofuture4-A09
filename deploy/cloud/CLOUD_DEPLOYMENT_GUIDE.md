# Cloud Deployment Guide

This guide explains how to move the project from a local cluster to managed Kubernetes on AWS EKS, Azure AKS, and GCP GKE.

## Shared Architecture

Recommended platform components:

- Kubernetes cluster
- Prometheus for metrics
- Loki for logs
- Tempo or Jaeger for traces
- PostgreSQL for incidents and audit data
- This FastAPI app deployed as a Kubernetes Deployment

The application is cloud-agnostic at the remediation layer because it uses Kubernetes APIs for restart and scale actions.

## Common Environment Variables

Set these in your deployment:

```text
DATABASE_URL=postgresql+psycopg://...
SELFHEAL_KUBE_MODE=cluster
SELFHEAL_TELEMETRY_MODE=live
PROMETHEUS_URL=http://prometheus.monitoring.svc.cluster.local:9090
LOKI_URL=http://loki.monitoring.svc.cluster.local:3100
TRACE_URL=http://tempo.monitoring.svc.cluster.local:3200
TRACE_BACKEND=tempo
SELFHEAL_BACKGROUND_MONITORING=true
SELFHEAL_MONITOR_INTERVAL_SECONDS=30
```

## AWS EKS

Suggested sequence:

1. Create an EKS cluster
2. Configure `kubectl`
3. Install Prometheus, Loki, and Tempo into a `monitoring` namespace
4. Deploy PostgreSQL or use a managed database such as Amazon RDS
5. Deploy this application and set cluster-local telemetry URLs

Official AWS references:

- [Create an Amazon EKS cluster](https://docs.aws.amazon.com/eks/latest/userguide/getting-started-eksctl.html)
- [Deploy sample applications to Amazon EKS](https://docs.aws.amazon.com/eks/latest/userguide/sample-deployment.html)

## Azure AKS

Suggested sequence:

1. Create an AKS cluster with Azure CLI
2. Get cluster credentials with `az aks get-credentials`
3. Install Prometheus, Loki, and Tempo
4. Provision Azure Database for PostgreSQL or another reachable PostgreSQL instance
5. Deploy this application with the proper environment variables

Official Azure references:

- [Create an AKS cluster](https://learn.microsoft.com/en-us/azure/aks/learn/quick-kubernetes-deploy-cli)
- [Deploy an application to AKS](https://learn.microsoft.com/en-us/azure/aks/learn/quick-kubernetes-deploy-cli)

## GCP GKE

Suggested sequence:

1. Create a GKE cluster
2. Fetch credentials with `gcloud container clusters get-credentials`
3. Install Prometheus, Loki, and Tempo
4. Provision Cloud SQL for PostgreSQL or another reachable PostgreSQL instance
5. Deploy this application

Official GCP references:

- [Create a GKE cluster](https://cloud.google.com/kubernetes-engine/docs/quickstarts/create-cluster)
- [Deploy an app to GKE](https://cloud.google.com/kubernetes-engine/docs/quickstarts/deploy-app-container-image)

## Tracing

This project supports an optional trace backend. Recommended starting point:

- Tempo for `TRACE_BACKEND=tempo`
- Jaeger for `TRACE_BACKEND=jaeger`

Official Grafana Tempo reference:

- [Tempo API and TraceQL search documentation](https://grafana.com/docs/tempo/latest/api_docs/)

## Suggested Production Hardening

- Put the API behind an internal ingress or authenticated gateway
- Store incidents in managed PostgreSQL
- Use Kubernetes Secrets for credentials
- Add RBAC so the app can only restart/scale specific namespaces
- Start with low-blast-radius playbooks and approval gates for risky remediations
- Enable background monitoring only after validating your Prometheus, Loki, and trace queries
