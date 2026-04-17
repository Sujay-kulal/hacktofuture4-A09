<div align="center">
  <img src="https://img.shields.io/badge/Google%20ADK-Agentic%20AI-blue?style=for-the-badge&logo=google" alt="Google ADK">
  <img src="https://img.shields.io/badge/Gemini%202.0-Flash-purple?style=for-the-badge&logo=googlegemini" alt="Gemini">
  <img src="https://img.shields.io/badge/Kubernetes-Self%20Healing-326ce5?style=for-the-badge&logo=kubernetes" alt="Kubernetes">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi" alt="FastAPI">
</div>

<br />

<div align="center">
  <h1 align="center">Agentic Self-Healing Cloud</h1>
  <p align="center">
    <strong>Autonomous Kubernetes Operations Powered by Multi-Agent AI</strong>
  </p>
</div>

---

## 📖 The Challenge

Modern AI-driven cloud applications run on complex microservice architectures orchestrated by Kubernetes. While Kubernetes offers basic self-healing mechanisms (such as container restarts and pod rescheduling), these are entirely **reactive and non-diagnostic**. Kubernetes restarts failing components, but it cannot determine root causes or prevent cascading failures across interconnected services. 

As systems scale, a single degraded component can rapidly propagate failures and cause widespread downtime. Currently, Site Reliability Engineers (SREs) must manually analyze logs, metrics, and distributed traces across massive dashboards to diagnose incidents — a process that can take 30-90 minutes per event and simply does not scale.

## 🎯 Our Solution

**Agentic Self-Healing Cloud** is an autonomous cloud operations platform where AI agents continuously monitor infrastructure telemetry, detect anomalies, determine root causes, and execute safe remediation actions automatically. 

By leveraging the **Google Agent Development Kit (ADK)** and the **Gemini 2.0 Flash model**, this platform reduces Mean Time To Recovery (MTTR) from hours to minutes. It replaces manual SRE intervention with an intelligent, dynamic multi-agent pipeline designed to safeguard environments across AWS EKS, Azure AKS, and GCP GKE.

---

## ⚡ Key Features

* 🤖 **Multi-Agent Orchestration:** Utilizes Google ADK to route tasks between 4 specialized agents: Observer, Incident Responder, Healer, and Judge Narrator.
* 🧠 **LLM-Powered Root Cause Analysis (RCA):** Ingests raw telemetry (logs, metrics, traces, symptoms) and streams them to Gemini for context-aware SRE diagnostics.
* 🛡️ **Kubernetes Safety System:** Real-time Policy Engine that calculates "Blast Radius" and strictly gates unsafe pod/deployment remediations to prevent AI-driven catastrophic cascades.
* 📊 **Real-time Glassmorphism Dashboard:** A stunning storefront and operations UI that visualizes dynamic service topologies, simulated fault injections, and live AI incident patching.
* 💳 **Real-Time Token Budget Tracker:** Integrates directly with Gemini API payloads metadata natively to trace and stream actual token costs to the frontend.
* 📈 **MTTR & Benchmarking:** Built-in calculation of recovery speeds against standard baselines to quantify AI ROI for operations teams.

---

## 🏗️ Architecture

This repository is split into highly decoupled micro-systems tailored for robustness and scale:

* **`adk_selfheal/` (The Brain):** Contains the Google ADK configuration. The `root_agent` delegates tasks. The `incident_response_agent` can inject demo faults. The `healing_agent` loops over the telemetry queue via strict LLM tools.
* **`app/` (The Platform):** A FastAPI backend built on SQLAlchemy. Manages the API layer for telemetry queuing, orchestration, incident storage, and Gemini Client (`gemini_client.py`) integrations.
* **`frontend/` (The Interface):** A beautiful glassmorphism-themed Operations Center (`index.html`) and E-Commerce Mockup (`demo.html`) polling the API to visualize service health transitions (Healthy 🟢 ➔ Degraded 🟠 ➔ Down 🔴 ➔ Fixed 🔵).
* **`k8s_safety_system/` (The Shield):** Acts as the authorization layer before any Kubernetes command is executed; evaluating risk tags, blast radius, and requiring human-in-the-loop approvals for destructive operations.
* **`log_pipeline/` (The Nerves):** Dedicated scripts for scraping, deduplicating, clustering, and normalizing chaotic logs from the cluster before they hit the agent's context window.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Google Gemini API Key
- `pip` package manager

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agentic-self-healing-cloud.git
cd agentic-self-healing-cloud

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Setup

Configure your API keys in the `.env` file (see `.env.example`):
```env
GEMINI_API_KEY=your_gemini_api_key_here
ADK_GEMINI_MODEL=gemini-3.1-flash-lite-preview
```

### 3. Running the Platform

You need to run the backend and the ADK agent concurrently for the magic to happen.

**Terminal 1: Start the FastAPI Backend**
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Your Demo Dashboard is now live at `http://127.0.0.1:8000/demo-app`*

**Terminal 2: Launch the ADK Agent**
```bash
# Start your ADK interface to interact with the multi-agent system
adk web # (or your standard adk launching command)
```

---

## 🎭 The "Hackathon Perfect" Demo Flow

Want to see the platform in action? Once both terminals are running, use this exact conversation flow in the ADK chat:

1. **The Crash:** 
   * *You:* `"Simulate an outage in the payment service for the demo."`
   * *Result:* The frontend Payment dependency pulses **🔴 RED**.
2. **The Verification:** 
   * *You:* `"Place a test order."`
   * *Result:* The dashboard immediately renders a failed checkout response.
3. **The Autonomous Healing:** 
   * *You:* `"Send this failure to the platform and run the healing cycle."`
   * *Result:* The ADK pulls telemetry, Gemini analyzes the root cause, the safety system verifies blast radius, and the service is restored. The dashboard flashes **🔵 BLUE** then returns to **🟢 GREEN**.
4. **The Explanation:** 
   * *You:* `"Explain the latest incident for the judges."`
   * *Result:* The `judge_narrator_agent` synthesizes the exact SRE playbook executed to save the day, along with MTTR metrics. 

---

## 🤝 Built For Operators
This project demonstrates that AI in DevOps is not just a wrapper around shell scripts — it is an intelligent, strictly-gated, and fully observable feedback loop that fundamentally shifts Cloud Operations from *reactive alerts* to *autonomous stability*. 

*Developed with ❤️ for the future of SRE.*
