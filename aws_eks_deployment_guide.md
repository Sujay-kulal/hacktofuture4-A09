# Complete AWS EKS Deployment Guide — Absolute Beginner Edition

> This guide assumes you have **never used AWS before**. Every single step is explained.

---

## Table of Contents

1. [Get AWS Free Credits ($100)](#step-1-get-aws-free-credits)
2. [Install Required Tools](#step-2-install-required-tools)
3. [Configure AWS CLI](#step-3-configure-aws-cli)
4. [Create an ECR Repository (Image Storage)](#step-4-create-ecr-repository)
5. [Build and Push Your Docker Image](#step-5-build-and-push-your-docker-image)
6. [Create the EKS Cluster](#step-6-create-the-eks-cluster)
7. [Connect kubectl to the Cluster](#step-7-connect-kubectl-to-the-cluster)
8. [Set Up PostgreSQL Inside the Cluster](#step-8-set-up-postgresql)
9. [Install Prometheus + Loki + Tempo](#step-9-install-prometheus--loki--tempo)
10. [Create Kubernetes Secrets](#step-10-create-kubernetes-secrets)
11. [Update deployment.yaml for AWS](#step-11-update-deploymentyaml-for-aws)
12. [Deploy the Application](#step-12-deploy-the-application)
13. [Access Your Dashboard](#step-13-access-your-dashboard)
14. [Clean Up (IMPORTANT — Stop Billing)](#step-14-clean-up-when-done)

---

## Step 1: Get AWS Free Credits

You have two paths to get $100 free:

### Path A: AWS Educate (Recommended)

1. Go to: **https://aws.amazon.com/education/awseducate/**
2. Click **"Join AWS Educate"**
3. Select **"Student"**
4. Fill in:
   - Your name
   - Your **college email** (`.edu` or institutional email)
   - Your school/university name
   - Graduation date
5. Verify your email
6. Once approved → you get **$100 AWS credits**

### Path B: Through GitHub Student Developer Pack

1. Go to: **https://education.github.com/pack**
2. Get the Student Pack approved (student ID photo)
3. Find **"AWS"** in the list of offers
4. Activate → you get **$100 credits**

### After Getting Credits — Create Your AWS Account

1. Go to: **https://aws.amazon.com/**
2. Click **"Create an AWS Account"**
3. Enter your email and a password
4. Choose **"Personal"** account type
5. Fill in your details
6. Apply your student credits / educate credits

> [!IMPORTANT]
> Once your account is ready, go to the **AWS Console**: https://console.aws.amazon.com/
> You should see your credits under **Billing → Credits**.

---

## Step 2: Install Required Tools

Open **PowerShell** (regular, not admin needed for most).

### Tool 1: AWS CLI

```powershell
winget install Amazon.AWSCLI
```

**Close and reopen PowerShell**, then verify:

```powershell
aws --version
```

Expected output: `aws-cli/2.x.x Python/3.x.x Windows/...`

### Tool 2: eksctl (EKS cluster manager)

Since Chocolatey needed admin, let's install **without admin**:

```powershell
# Download eksctl
Invoke-WebRequest -Uri "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Windows_amd64.zip" -OutFile "$HOME\eksctl.zip"

# Extract it
Expand-Archive -Path "$HOME\eksctl.zip" -DestinationPath "$HOME\eksctl" -Force

# Add to PATH permanently
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*\eksctl*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$HOME\eksctl", "User")
}
$env:PATH += ";$HOME\eksctl"

# Clean up zip
Remove-Item "$HOME\eksctl.zip"
```

Verify:

```powershell
eksctl version
```

### Tool 3: kubectl

```powershell
winget install Kubernetes.kubectl
```

**Close and reopen PowerShell**, then verify:

```powershell
kubectl version --client
```

### Tool 4: Helm

```powershell
winget install Helm.Helm
```

**Close and reopen PowerShell**, then verify:

```powershell
helm version
```

### Tool 5: Docker Desktop

You should already have this. Make sure it's **running** (open from Start Menu).

```powershell
docker --version
```

> [!TIP]
> After installing all tools, **close and reopen PowerShell one final time** so all PATH changes take effect.

---

## Step 3: Configure AWS CLI

You need an **Access Key** to let the CLI talk to AWS.

### 3a. Create an Access Key in the AWS Console

1. Open: **https://console.aws.amazon.com/**
2. Click your **username** (top right corner) → **"Security credentials"**
3. Scroll down to **"Access keys"**
4. Click **"Create access key"**
5. Select **"Command Line Interface (CLI)"**
6. Check the confirmation box → Click **"Create access key"**
7. **COPY BOTH VALUES** — you'll never see the secret key again:
   - `Access Key ID` → looks like: `AKIAIOSFODNN7EXAMPLE`
   - `Secret Access Key` → looks like: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`

### 3b. Configure the CLI

```powershell
aws configure
```

It will ask you 4 things. Enter them one by one:

```
AWS Access Key ID [None]: PASTE_YOUR_ACCESS_KEY_HERE
AWS Secret Access Key [None]: PASTE_YOUR_SECRET_KEY_HERE
Default region name [None]: ap-south-1
Default output format [None]: json
```

> [!NOTE]
> We use `ap-south-1` (Mumbai, India) for lowest latency from India. You can also use `us-east-1` if you prefer.

### 3c. Verify it works

```powershell
aws sts get-caller-identity
```

You should see your Account ID and username. **If this works, you're connected to AWS!**

---

## Step 4: Create ECR Repository

**ECR** (Elastic Container Registry) stores your Docker image so EKS can pull it.

```powershell
aws ecr create-repository --repository-name selfheal-api --region ap-south-1
```

**Expected output:** JSON with `"repositoryUri": "123456789012.dkr.ecr.ap-south-1.amazonaws.com/selfheal-api"`

Save your **Account ID** for later:

```powershell
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$REGION = "ap-south-1"
echo "Your Account ID: $ACCOUNT_ID"
echo "Your Region: $REGION"
```

**Write these down!** You'll need them multiple times.

---

## Step 5: Build and Push Your Docker Image

### 5a. Log Docker into ECR

```powershell
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
```

Expected output: `Login Succeeded`

### 5b. Build the image

```powershell
cd C:\Users\ranja\Downloads\games\codex

docker build -t selfheal-api:latest .
```

Wait for it to finish. You'll see `Successfully built` and `Successfully tagged`.

### 5c. Tag it for ECR

```powershell
docker tag selfheal-api:latest "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/selfheal-api:latest"
```

### 5d. Push to ECR

```powershell
docker push "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/selfheal-api:latest"
```

This uploads your image to AWS. Takes 3–5 minutes.

### 5e. Verify

```powershell
aws ecr list-images --repository-name selfheal-api --region $REGION
```

You should see your image with tag `latest`.

---

## Step 6: Create the EKS Cluster

This is the **big step** — creating your Kubernetes cluster on AWS.

```powershell
eksctl create cluster --name selfheal-cluster --region $REGION --version 1.31 --nodegroup-name selfheal-nodes --node-type t3.medium --nodes 2 --nodes-min 1 --nodes-max 3 --managed
```

**What each part means:**

| Part | Meaning |
|------|---------|
| `--name selfheal-cluster` | Your cluster's name |
| `--region ap-south-1` | Deploy in Mumbai |
| `--version 1.31` | Kubernetes version |
| `--node-type t3.medium` | Each VM: 2 vCPUs, 4 GB RAM |
| `--nodes 2` | Start with 2 VMs |
| `--managed` | AWS manages the node updates |

> [!IMPORTANT]
> **This takes 15–20 minutes.** Don't close PowerShell! You'll see progress messages like:
> ```
> 2026-04-12 00:30:00 [ℹ]  creating cluster "selfheal-cluster" in "ap-south-1"
> 2026-04-12 00:30:05 [ℹ]  building managed nodegroup stack
> ...
> 2026-04-12 00:45:00 [✔]  EKS cluster "selfheal-cluster" in "ap-south-1" region is ready
> ```

### Cost info:
- EKS control plane: ~$0.10/hr ($2.40/day)
- 2× t3.medium nodes: ~$0.07/hr each ($3.36/day)
- **Total: ~$5.76/day** → your $100 lasts about **17 days**

---

## Step 7: Connect kubectl to the Cluster

After the cluster is created:

```powershell
aws eks update-kubeconfig --name selfheal-cluster --region $REGION
```

**Verify the connection:**

```powershell
kubectl get nodes
```

**You should see:**

```
NAME                                           STATUS   ROLES    AGE   VERSION
ip-192-168-xx-xx.ap-south-1.compute.internal   Ready    <none>   5m    v1.31.x
ip-192-168-xx-xx.ap-south-1.compute.internal   Ready    <none>   5m    v1.31.x
```

**Two nodes, both `Ready`. Your cluster is alive! 🎉**

---

## Step 8: Set Up PostgreSQL

We'll run PostgreSQL inside the cluster (free — uses your existing nodes).

```powershell
cd C:\Users\ranja\Downloads\games\codex

# Create the selfheal namespace
kubectl apply -f deploy\k8s\namespace.yaml
```

Expected: `namespace/selfheal created`

```powershell
# Deploy PostgreSQL
kubectl -n selfheal run postgres --image=postgres:16 --env="POSTGRES_DB=selfheal" --env="POSTGRES_USER=postgres" --env="POSTGRES_PASSWORD=postgres" --port=5432
```

Expected: `pod/postgres created`

```powershell
# Wait for it to be ready
kubectl -n selfheal wait --for=condition=Ready pod/postgres --timeout=120s
```

Expected: `pod/postgres condition met`

```powershell
# Create a service so your app can find it
kubectl -n selfheal expose pod postgres --port=5432 --name=postgres
```

Expected: `service/postgres exposed`

**Verify:**

```powershell
kubectl get pods -n selfheal
```

```
NAME       READY   STATUS    RESTARTS   AGE
postgres   1/1     Running   0          30s
```

---

## Step 9: Install Prometheus + Loki + Tempo

These are the monitoring tools your app needs.

### 9a. Add Helm repos

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

### 9b. Create monitoring namespace

```powershell
kubectl create namespace monitoring
```

### 9c. Install Prometheus (metrics)

```powershell
helm install prometheus prometheus-community/kube-prometheus-stack --namespace monitoring --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false --set grafana.enabled=true
```

Wait 2–3 minutes.

### 9d. Install Loki (logs)

```powershell
helm install loki grafana/loki-stack --namespace monitoring --set promtail.enabled=true --set loki.persistence.enabled=false
```

### 9e. Install Tempo (traces)

```powershell
helm install tempo grafana/tempo --namespace monitoring
```

### 9f. Verify everything is running

```powershell
kubectl get pods -n monitoring
```

Wait until all pods show `Running`. This may take **3–5 minutes**. Some pods restart once — that's normal.

### 9g. Find the exact service names

```powershell
kubectl get svc -n monitoring
```

Note down the Prometheus service name. It's usually one of these:
- `prometheus-kube-prometheus-prometheus`
- `prometheus-operated`

---

## Step 10: Create Kubernetes Secrets

This stores your database password and Gemini API key securely.

```powershell
kubectl create secret generic selfheal-secrets --namespace selfheal --from-literal=DATABASE_URL="postgresql+psycopg://postgres:postgres@postgres.selfheal.svc.cluster.local:5432/selfheal" --from-literal=GEMINI_API_KEY="not-configured"
```

Expected: `secret/selfheal-secrets created`

> [!TIP]
> Replace `"not-configured"` with your actual Gemini API key if you have one. The app works without it — it uses rule-based RCA instead.

---

## Step 11: Update deployment.yaml for AWS

You need to change 2 things in [deployment.yaml](file:///c:/Users/ranja/Downloads/games/codex/deploy/k8s/deployment.yaml):

### Change 1: Image reference (line 23-24)

**From:**
```yaml
          image: selfheal-api:latest
          imagePullPolicy: IfNotPresent
```

**To (replace ACCOUNT_ID and REGION with your values):**
```yaml
          image: YOUR_ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com/selfheal-api:latest
          imagePullPolicy: Always
```

To get your exact image URI, run:

```powershell
echo "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/selfheal-api:latest"
```

Copy that output and paste it as the `image` value.

### Change 2: Prometheus URL (line 44-45)

Check your actual Prometheus service name:

```powershell
kubectl get svc -n monitoring | Select-String "prometheus"
```

Then update line 45 in deployment.yaml to match. For example:

**From:**
```yaml
              value: "http://prometheus-operated.monitoring.svc.cluster.local:9090"
```

**To (if your service is named differently):**
```yaml
              value: "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090"
```

---

## Step 12: Deploy the Application

Run these commands **in this exact order**:

```powershell
cd C:\Users\ranja\Downloads\games\codex

# 1. ServiceAccount (app identity)
kubectl apply -f deploy\k8s\serviceaccount.yaml

# 2. ClusterRole (permissions to manage pods)
kubectl apply -f deploy\k8s\clusterrole.yaml

# 3. ClusterRoleBinding (connect permissions to identity)
kubectl apply -f deploy\k8s\clusterrolebinding.yaml

# 4. NetworkPolicy (security)
kubectl apply -f deploy\k8s\networkpolicy.yaml

# 5. Deployment (your app)
kubectl apply -f deploy\k8s\deployment.yaml

# 6. Service (expose the app)
kubectl apply -f deploy\k8s\service.yaml
```

Each command should say `created` or `configured`.

### Watch it come up:

```powershell
kubectl get pods -n selfheal --watch
```

Wait until you see:

```
NAME                            READY   STATUS    RESTARTS   AGE
postgres                        1/1     Running   0          10m
selfheal-api-xxxxxxxxxx-xxxxx   1/1     Running   0          30s
```

Press `Ctrl+C` to stop watching.

> [!WARNING]
> If the pod shows `ImagePullBackOff`, the cluster can't pull your image. Run:
> ```powershell
> # Check what went wrong
> kubectl describe pod -n selfheal -l app=selfheal-api
> ```
> You may need to create an ECR pull policy. See [Troubleshooting](#troubleshooting) at the bottom.

---

## Step 13: Access Your Dashboard

### Option A: Port-Forward (Quick — for testing/demo)

```powershell
kubectl port-forward -n selfheal svc/selfheal-api 8000:80
```

Open in browser: **http://localhost:8000/dashboard** 🎉

Keep this PowerShell window open.

### Option B: LoadBalancer (Public URL — anyone can access)

```powershell
kubectl patch svc selfheal-api -n selfheal -p '{\"spec\": {\"type\": \"LoadBalancer\"}}'
```

Wait for the external URL:

```powershell
kubectl get svc -n selfheal --watch
```

When `EXTERNAL-IP` shows an address (not `<pending>`):

```
NAME           TYPE           CLUSTER-IP     EXTERNAL-IP                                       PORT(S)
selfheal-api   LoadBalancer   10.100.x.x     a1b2c3-1234567890.ap-south-1.elb.amazonaws.com    80:xxxxx/TCP
```

Open: **http://a1b2c3-1234567890.ap-south-1.elb.amazonaws.com/dashboard**

### Test it works:

1. Open the dashboard
2. Choose `crashloop` in "Simulate Incident"
3. Click **Queue Simulated Incident**
4. Click **Run One Healing Cycle**
5. See the incident, RCA, and remediation appear ✅

### Also try the demo app:

Open: **http://localhost:8000/demo-app** (or the LoadBalancer URL + `/demo-app`)

1. Click "Break Payment Dependency"
2. Click "Place Test Order"
3. Click "Send Failure To Self-Healing Platform"
4. Go to dashboard → Click "Run One Healing Cycle"

---

## Step 14: Clean Up (IMPORTANT — Stop Billing!)

> [!CAUTION]
> **EKS costs ~$5.76/day.** Delete everything after your hackathon is over to save credits!

### Delete the entire cluster:

```powershell
# Delete all Kubernetes resources first
kubectl delete -f deploy\k8s\demo-microservices.yaml 2>$null
kubectl delete -f deploy\k8s\service.yaml
kubectl delete -f deploy\k8s\deployment.yaml
kubectl delete -f deploy\k8s\networkpolicy.yaml
kubectl delete -f deploy\k8s\clusterrolebinding.yaml
kubectl delete -f deploy\k8s\clusterrole.yaml
kubectl delete -f deploy\k8s\serviceaccount.yaml
kubectl delete -f deploy\k8s\namespace.yaml

# Uninstall Helm charts
helm uninstall prometheus -n monitoring
helm uninstall loki -n monitoring
helm uninstall tempo -n monitoring
kubectl delete namespace monitoring

# DELETE THE CLUSTER (this stops all billing)
eksctl delete cluster --name selfheal-cluster --region ap-south-1
```

> [!IMPORTANT]
> The `eksctl delete cluster` command takes **10–15 minutes**. Don't close PowerShell. Wait for it to finish completely.

### Also delete the ECR repository:

```powershell
aws ecr delete-repository --repository-name selfheal-api --region ap-south-1 --force
```

### Verify nothing is left:

```powershell
# Check no clusters exist
eksctl get cluster --region ap-south-1

# Check no ECR repos exist
aws ecr describe-repositories --region ap-south-1
```

Both should return empty results.

---

## Quick Reference Card

| What | Command |
|------|---------|
| Check nodes | `kubectl get nodes` |
| Check all pods | `kubectl get pods --all-namespaces` |
| Check your app | `kubectl get pods -n selfheal` |
| See app logs | `kubectl logs -n selfheal -l app=selfheal-api --tail=50` |
| Open dashboard | `kubectl port-forward -n selfheal svc/selfheal-api 8000:80` |
| Restart app | `kubectl rollout restart deployment/selfheal-api -n selfheal` |
| Delete everything | `eksctl delete cluster --name selfheal-cluster --region ap-south-1` |

---

## Budget Tracker

| Resource | Cost per Day | Cost for 3 Days (hackathon) |
|----------|-------------|----------------------------|
| EKS Control Plane | $2.40 | $7.20 |
| 2× t3.medium Nodes | $3.36 | $10.08 |
| ECR Storage | $0.01 | $0.03 |
| LoadBalancer (if used) | $0.60 | $1.80 |
| **Total** | **~$6.37/day** | **~$19.11** |
| **Your Credits** | | **$100** |
| **Remaining after hackathon** | | **~$81** |

> [!TIP]
> After the hackathon, immediately run `eksctl delete cluster` to stop billing. Your $100 is more than enough for a multi-day hackathon.

---

## Troubleshooting

### "ImagePullBackOff" — cluster can't pull the image

Your EKS nodes need permission to pull from ECR:

```powershell
# Get the node role name
$ROLE_NAME = (aws iam list-roles --query "Roles[?contains(RoleName, 'nodegroup')].RoleName" --output text)
echo "Node role: $ROLE_NAME"

# Attach ECR pull permissions
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
```

Then restart the pod:

```powershell
kubectl rollout restart deployment/selfheal-api -n selfheal
```

### "CrashLoopBackOff" — app starts but crashes

```powershell
kubectl logs -n selfheal -l app=selfheal-api --tail=100
```

Usually means wrong `DATABASE_URL`. Fix:

```powershell
kubectl delete secret selfheal-secrets -n selfheal
kubectl create secret generic selfheal-secrets --namespace selfheal --from-literal=DATABASE_URL="postgresql+psycopg://postgres:postgres@postgres.selfheal.svc.cluster.local:5432/selfheal" --from-literal=GEMINI_API_KEY="not-configured"
kubectl rollout restart deployment/selfheal-api -n selfheal
```

### "Pending" pod — not enough resources

```powershell
kubectl describe pod -n selfheal -l app=selfheal-api
# Look at Events → "Insufficient cpu" or "Insufficient memory"
```

Fix — use smaller resource requests. Edit deployment.yaml:

```yaml
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
```

Then reapply:

```powershell
kubectl apply -f deploy\k8s\deployment.yaml
```

### eksctl takes forever / fails

Make sure your AWS credentials are correct:

```powershell
aws sts get-caller-identity
```

If this fails, re-run `aws configure` with your access key and secret key.
