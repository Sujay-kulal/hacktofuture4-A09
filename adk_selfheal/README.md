# Google ADK Integration

This folder turns the existing self-healing platform into a real Google ADK agent package.

## What it does

- uses Google ADK as the agent runtime
- uses Gemini as the reasoning model for the ADK agents
- connects the ADK agents to the existing FastAPI backend through tool functions
- keeps your current dashboard, queue, approvals, benchmark reports, and demo app

## Files

- `agent.py`
  defines the ADK agents and the exported `root_agent`
- `tools.py`
  defines function tools that call the running backend
- `.env.example`
  shows the environment variables needed by ADK

## Agent design

There are 4 specialist agents:

1. `observer_agent`
   inspects platform health, incidents, queue, and demo topology

2. `incident_response_agent`
   injects demo faults, places demo orders, queues incidents, and collects telemetry

3. `healing_agent`
   runs the self-healing cycle and handles approvals/requeue actions

4. `judge_narrator_agent`
   explains the incident and benchmark results for hackathon judges

And one coordinator:

- `root_agent`
  the main ADK agent that delegates to the specialists

## Important

The FastAPI backend must already be running on:

`http://127.0.0.1:8000`

because the ADK tools call the backend over HTTP.
