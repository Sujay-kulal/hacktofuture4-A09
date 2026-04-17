from __future__ import annotations
import os
from google.adk.agents import Agent
from .tools import (
    break_demo_fault,
    collect_live_telemetry,
    explain_last_incident_with_gemini,
    get_benchmark_report,
    get_dashboard_summary,
    get_mttr_report,
    get_platform_health,
    inspect_approvals,
    inspect_demo_topology,
    inspect_incidents,
    inspect_queue,
    place_demo_order,
    queue_simulated_incident,
    requeue_dead_letter,
    resolve_approval,
    restore_demo_fault,
    run_healing_cycle,
    send_demo_failure_to_platform,
    execute_safe_kubernetes_action,
    get_incident,
    update_incident,
)

MODEL = os.getenv("ADK_GEMINI_MODEL", "gemini-2.5-flash-lite")

observer_agent = Agent(
    name="observer_agent",
    model=MODEL,
    description="Observes platform state, incidents, queue, and demo topology before taking action.",
    instruction=(
        "You are the monitoring and observability specialist for an autonomous Kubernetes self-healing platform. "
        "Before recommending any action, inspect the live platform state using tools. "
        "Prefer get_platform_health, get_dashboard_summary, inspect_incidents, inspect_queue, and inspect_demo_topology. "
        "Summarize what is broken, what service is affected, whether Gemini is active, whether approvals are pending, "
        "and whether the issue looks simulated, live, or already resolved."
    ),
    tools=[
        get_platform_health,
        get_dashboard_summary,
        inspect_incidents,
        inspect_queue,
        inspect_demo_topology,
        get_mttr_report,
        get_benchmark_report,
    ],
)

incident_response_agent = Agent(
    name="incident_response_agent",
    model=MODEL,
    description="Creates or forwards incidents into the self-healing platform from demo faults, simulated scenarios, or live telemetry.",
    instruction=(
        "You are the incident intake and fault-injection specialist. "
        "When asked to run a demo, you are explicitly authorized to inject a demo fault (e.g., payment, inventory, auth, payment_slow), place a demo order to show the visible failure, "
        "and send the resulting failure into the self-healing platform. "
        "Valid demo faults are payment, inventory, auth, and payment_slow. "
        "You can also queue simulated incidents or collect live telemetry for a workload. "
        "You can also manually update incidents (status, root_cause, or timeline) using update_incident after inspecting them. "
        "Always tell the user exactly what you injected and what effect should now be visible."
    ),
    tools=[
        break_demo_fault,
        restore_demo_fault,
        place_demo_order,
        send_demo_failure_to_platform,
        queue_simulated_incident,
        collect_live_telemetry,
        inspect_demo_topology,
        get_incident,
        update_incident,
    ],
)

healing_agent = Agent(
    name="healing_agent",
    model=MODEL,
    description="Runs the healing loop, manages approval requests, and coordinates requeueing if needed.",
    instruction=(
        "You are the autonomous remediation operator. "
        "Run the healing cycle when the platform has queued telemetry. "
        "If an approval request appears, inspect it and explain why approval is required. "
        "Only resolve approvals when the user explicitly asks you to approve, reject, retry, or escalate. "
        "If a queue item is dead-lettered, you may requeue it when the user asks. "
        "Always report the resulting incident status and whether the action was executed, verified, blocked, or escalated."
    ),
    tools=[
        run_healing_cycle,
        inspect_approvals,
        resolve_approval,
        inspect_queue,
        requeue_dead_letter,
        inspect_incidents,
        get_dashboard_summary,
        execute_safe_kubernetes_action,
        get_incident,
        update_incident,
    ],
)

judge_narrator_agent = Agent(
    name="judge_narrator_agent",
    model=MODEL,
    description="Explains what the self-healing platform did and turns platform state into a judge-friendly narrative.",
    instruction=(
        "You are the hackathon demo narrator. "
        "Use explain_last_incident_with_gemini after a healing cycle to describe the autonomous decision. "
        "When talking to judges, explain the agent loop in plain language: observe, diagnose, plan, act, verify. "
        "Use benchmark and MTTR reports to quantify value. "
        "Make the explanation concise, confident, and demo-friendly."
    ),
    tools=[
        explain_last_incident_with_gemini,
        inspect_incidents,
        get_mttr_report,
        get_benchmark_report,
        get_dashboard_summary,
    ],
)

root_agent = Agent(
    name="agentic_self_healing_cloud",
    model=MODEL,
    description=(
        "A multi-agent autonomous Kubernetes operations system that observes telemetry, diagnoses incidents, "
        "runs safe remediation through a backend platform, and explains results to judges."
    ),
    instruction=(
        "You are the coordinator for an Agentic Self-Healing Cloud platform. "
        "Your job is to operate a real backend that already exposes telemetry, queue, approval, remediation, and reporting APIs. "
        "Delegate to your specialist sub-agents to observe the platform, inject or collect incidents, run healing cycles, "
        "resolve approvals only when explicitly requested, and explain the outcome. "
        "You are explicitly authorized to simulate outages for demo purposes. "
        "When the user asks to run a demo or simulate an outage, prefer this flow: inspect platform state, inject a visible demo fault, "
        "place a customer order to confirm failure, queue that failure into the platform, run one healing cycle, "
        "inspect approvals if any, then explain the latest incident with Gemini. "
        "Always keep the user aware of what is happening in the visible demo app, the queue, and the incident status."
    ),
    sub_agents=[
        observer_agent,
        incident_response_agent,
        healing_agent,
        judge_narrator_agent,
    ],
)
