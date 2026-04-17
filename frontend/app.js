async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }

  return data;
}

function setMessage(text) {
  document.getElementById("message").textContent = text;
}

function setRefreshStatus(text) {
  document.getElementById("refresh-status").textContent = text;
}

function renderAutomationStatus(status) {
  const node = document.getElementById("automation-status");
  const configuredClass = status.configured ? "source-chip chip-gemini" : "source-chip chip-failed";
  node.innerHTML = `
    <div class="gemini-card">
      <p><strong>Provider:</strong> ${status.provider}</p>
      <p><strong>Configured:</strong> <span class="${configuredClass}">${status.configured}</span></p>
      <p><strong>Model:</strong> ${status.model || "not configured"}</p>
      <p><strong>Mode:</strong> ${status.automation_mode}</p>
      <p><strong>AI-assisted incidents:</strong> ${status.total_ai_assisted_incidents}</p>
      <p><strong>Gemini RCA count:</strong> ${status.gemini_rca_incidents}</p>
      <p><strong>Gemini remediation count:</strong> ${status.gemini_remediation_incidents}</p>
      <p><strong>Last Gemini error:</strong> ${status.last_error || "none"}</p>
    </div>
  `;
}

function renderStats(summary) {
  const stats = [
    ["Total Incidents", summary.total_incidents],
    ["Remediated", summary.remediated_incidents],
    ["Pending Approval", summary.pending_approval_incidents],
    ["Blocked", summary.blocked_incidents],
    ["Escalated", summary.escalated_incidents],
    ["Queue Depth", summary.queue_depth],
  ];

  document.getElementById("stats").innerHTML = stats
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <span>${label}</span>
          <strong>${value}</strong>
        </article>
      `
    )
    .join("");
}

function renderWorkloads(workloads) {
  if (!workloads.length) {
    document.getElementById("workloads").innerHTML = "<p>No workloads found.</p>";
    return;
  }

  document.getElementById("workloads").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Namespace</th>
          <th>Desired</th>
          <th>Available</th>
          <th>Updated</th>
        </tr>
      </thead>
      <tbody>
        ${workloads
          .map(
            (item) => `
              <tr>
                <td>${item.name}</td>
                <td>${item.namespace}</td>
                <td>${item.desired_replicas}</td>
                <td>${item.available_replicas}</td>
                <td>${item.updated_replicas}</td>
              </tr>
            `
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderIncidents(incidents) {
  if (!incidents.length) {
    document.getElementById("incidents").innerHTML = "<p>No incidents stored yet.</p>";
    return;
  }

  document.getElementById("incidents").innerHTML = incidents
    .map(
      (incident, index) => `
        <details class="incident-card" ${index < 2 ? "open" : ""}>
          <summary class="incident-summary">
            <h3>${incident.service} - ${incident.scenario}</h3>
            <div class="meta">
              namespace=${incident.namespace} | status=${incident.status} | latest action=${incident.latest_action || "n/a"} (${incident.latest_action_status || "n/a"})
            </div>
            <div class="source-row">
              <span class="source-chip ${sourceClass(incident.rca_source)}">RCA: ${incident.rca_source || "unknown"}</span>
              <span class="source-chip ${sourceClass(incident.remediation_source)}">Remediation: ${incident.remediation_source || "unknown"}</span>
            </div>
            <p><strong>Root cause:</strong> ${incident.root_cause || "not analyzed yet"}</p>
          </summary>
          <div class="incident-detail">
            <p><strong>Symptoms:</strong> ${(incident.symptoms || []).join(", ")}</p>
            <p><strong>Metrics:</strong> ${Object.entries(incident.metrics || {})
              .map(([key, value]) => `${key}=${value}`)
              .join(", ") || "none"}</p>
            <p><strong>Traces:</strong> ${(incident.traces || []).join(" | ") || "none"}</p>
            <ul>
              ${(incident.timeline || []).map((step) => `<li>${step}</li>`).join("")}
            </ul>
          </div>
        </details>
      `
    )
    .join("");
}

function sourceClass(source) {
  if (source === "gemini") {
    return "chip-gemini";
  }
  if (source === "rules" || source === "playbook") {
    return "chip-rules";
  }
  if (source === "gemini_failed") {
    return "chip-failed";
  }
  return "chip-neutral";
}

function renderMonitoringStatus(status) {
  document.getElementById("monitor-status").innerHTML = `
    <div class="monitor-card">
      <p><strong>Enabled:</strong> ${status.enabled}</p>
      <p><strong>Running:</strong> ${status.running}</p>
      <p><strong>Interval:</strong> ${status.interval_seconds}s</p>
      <p><strong>Last Scan:</strong> ${status.last_scan_time || "n/a"}</p>
      <p><strong>Last Remediation:</strong> ${status.last_remediation_time || "n/a"}</p>
      <p><strong>Targets Scanned:</strong> ${status.targets_scanned}</p>
      <p><strong>Message:</strong> ${status.last_message || "n/a"}</p>
    </div>
  `;
}

function renderQueueOverview(queue) {
  const node = document.getElementById("queue-overview");
  const items = queue.items || [];
  node.innerHTML = `
    <div class="queue-card">
      <p><strong>Queued:</strong> ${queue.queued}</p>
      <p><strong>Claimed:</strong> ${queue.claimed}</p>
      <p><strong>Processed:</strong> ${queue.processed}</p>
      <p><strong>Dead letters:</strong> ${queue.dead_letter}</p>
      ${
        items.length
          ? `<table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Event</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Error</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                ${items
                  .map(
                    (item) => `
                      <tr>
                        <td>${item.id}</td>
                        <td>${item.service} / ${item.scenario}</td>
                        <td>${item.status}</td>
                        <td>${item.attempts}/${item.max_attempts}</td>
                        <td>${item.dead_letter_reason || item.last_error || "none"}</td>
                        <td>${
                          item.status === "dead_letter"
                            ? `<button class="mini-button" data-requeue-queue="${item.id}">Requeue</button>`
                            : "n/a"
                        }</td>
                      </tr>
                    `
                  )
                  .join("")}
              </tbody>
            </table>`
          : "<p>No queue activity yet.</p>"
      }
    </div>
  `;
}

function renderApprovals(approvals) {
  const node = document.getElementById("approvals");
  if (!approvals.length) {
    node.innerHTML = "<p>No approval requests are pending.</p>";
    return;
  }

  node.innerHTML = approvals
    .map(
      (approval) => `
        <div class="approval-card">
          <div class="meta">#${approval.id} | ${approval.service} | ${approval.scenario} | status=${approval.status}</div>
          <p><strong>Requested action:</strong> ${approval.action} on ${approval.target_kind}/${approval.target_name}</p>
          <p><strong>Reason:</strong> ${approval.reason}</p>
          <p><strong>Risk:</strong> ${approval.risk_level} | <strong>Blast radius:</strong> ${approval.blast_radius}</p>
          <p><strong>Policy tags:</strong> ${(approval.policy_tags || []).join(", ") || "none"}</p>
          <div class="button-row">
            <button class="mini-button" data-approval-action="approve" data-approval-id="${approval.id}">Approve</button>
            <button class="mini-button alt-button" data-approval-action="reject" data-approval-id="${approval.id}">Reject</button>
            <button class="mini-button alt-button" data-approval-action="retry" data-approval-id="${approval.id}">Retry</button>
            <button class="mini-button alt-button" data-approval-action="escalate" data-approval-id="${approval.id}">Escalate</button>
          </div>
        </div>
      `
    )
    .join("");
}

function renderBenchmark(report) {
  const node = document.getElementById("benchmark-report");
  if (!report || !report.total_incidents) {
    node.innerHTML = "<p>Benchmark data will appear after a few incidents are processed.</p>";
    return;
  }

  node.innerHTML = `
    <div class="gemini-card">
      <p><strong>Average MTTR:</strong> ${report.average_mttr_seconds}s</p>
      <p><strong>Baseline MTTR:</strong> ${report.baseline_mttr_seconds}s</p>
      <p><strong>Improvement:</strong> ${report.improvement_percent}%</p>
      <p><strong>Remediation success rate:</strong> ${report.remediation_success_rate}%</p>
      <p><strong>Incidents by status:</strong> ${Object.entries(report.incidents_by_status || {}).map(([key, value]) => `${key}=${value}`).join(" | ") || "none"}</p>
      <div class="benchmark-bars">
        ${(report.scenarios || [])
          .map(
            (item) => `
              <div class="benchmark-bar">
                <div class="benchmark-label">${item.scenario}</div>
                <div class="benchmark-track">
                  <div class="benchmark-fill" style="width:${Math.min(item.improvement_percent, 100)}%"></div>
                </div>
                <div class="benchmark-value">${item.improvement_percent}% better than baseline</div>
              </div>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderMttrReport(report) {
  const node = document.getElementById("mttr-report");
  if (!report || !report.resolved_incidents) {
    node.innerHTML = "<p>Recovery metrics will appear after incidents are processed.</p>";
    return;
  }

  node.innerHTML = `
    <div class="gemini-card">
      <p><strong>Resolved incidents:</strong> ${report.resolved_incidents}</p>
      <p><strong>Average MTTR:</strong> ${report.average_mttr_seconds}s</p>
      <p><strong>Median MTTR:</strong> ${report.median_mttr_seconds}s</p>
      <p><strong>P95 MTTR:</strong> ${report.p95_mttr_seconds}s</p>
      <p><strong>Recovered in last 24h:</strong> ${report.recovered_last_24h}</p>
      <p><strong>By scenario:</strong> ${(report.scenarios || []).map((item) => `${item.scenario}=${item.average_mttr_seconds}s`).join(" | ") || "none"}</p>
    </div>
  `;
}

function renderDependencies(nodes) {
  if (!nodes.length) {
    document.getElementById("dependencies").innerHTML = "<p>No dependency graph loaded.</p>";
    return;
  }

  document.getElementById("dependencies").innerHTML = nodes
    .map(
      (node) => `
        <div class="dependency-card">
          <strong>${node.service}</strong> <span>(${node.namespace})</span>
          <div class="meta">Criticality: ${node.criticality} | Cascading risk: ${node.cascading_risk_score}</div>
          <div class="meta">Depends on: ${(node.depends_on || []).join(", ") || "none"}</div>
          <div class="meta">Potential impact: ${(node.impacted_services || []).join(", ") || "none"}</div>
          <div class="meta">Transitive impact: ${(node.transitive_impacted_services || []).join(", ") || "none"}</div>
        </div>
      `
    )
    .join("");
}

function renderActivity(entries) {
  if (!entries.length) {
    document.getElementById("activity").innerHTML = "<p>No activity yet.</p>";
    return;
  }

  document.getElementById("activity").innerHTML = entries
    .map(
      (entry) => `
        <div class="activity-entry level-${entry.level}">
          <div class="activity-time">${entry.timestamp}</div>
          <div class="activity-level">${entry.level}</div>
          <div class="activity-message">${entry.message}</div>
        </div>
      `
    )
    .join("");
}

function renderLogs(entries) {
  if (!entries.length) {
    document.getElementById("logs").innerHTML = "<div>No backend logs yet.</div>";
    return;
  }

  document.getElementById("logs").innerHTML = entries
    .slice()
    .reverse()
    .map(
      (entry) => `
        <div class="log-line">
          <div class="log-time">${entry.timestamp}</div>
          <div class="log-level">${entry.level}</div>
          <div class="log-source">${entry.source}</div>
          <div class="log-message">${entry.message}</div>
        </div>
      `
    )
    .join("");

  const consoleNode = document.getElementById("logs");
  consoleNode.scrollTop = consoleNode.scrollHeight;
}

function renderGeminiExplanation(explanation) {
  const node = document.getElementById("gemini-explanation");
  if (!explanation) {
    node.innerHTML = "<p>Run a healing cycle, then click \"Explain Last Incident With Gemini\".</p>";
    return;
  }

  node.innerHTML = `
    <div class="gemini-card">
      <div class="meta">incident=${explanation.incident_id || "n/a"} | service=${explanation.service} | scenario=${explanation.scenario}</div>
      <p><strong>Root cause:</strong> ${explanation.root_cause || "n/a"}</p>
      <p><strong>Action:</strong> ${explanation.action || "n/a"}</p>
      <p><strong>How Gemini reasoned:</strong> ${explanation.explanation}</p>
      <p><strong>Evidence used:</strong> ${(explanation.evidence || []).join(" | ") || "none"}</p>
      <p><strong>Leader summary:</strong> ${explanation.leader_summary}</p>
    </div>
  `;
}

function renderImpactView(impact) {
  const node = document.getElementById("impact-view");
  if (!impact || !impact.service) {
    node.innerHTML = "<p>Run a healing cycle to see what workload was affected.</p>";
    return;
  }

  const workload = impact.workload;
  const events = impact.events || [];
  node.innerHTML = `
    <div class="impact-card">
      <div class="meta">incident=${impact.incident_id || "n/a"} | service=${impact.service} | namespace=${impact.namespace} | scenario=${impact.scenario}</div>
      <p><strong>What happened:</strong> ${impact.summary}</p>
      <p><strong>Latest action:</strong> ${impact.latest_action || "n/a"} (${impact.latest_action_status || "n/a"})</p>
      ${
        workload
          ? `
            <p><strong>Deployment state:</strong> desired=${workload.desired_replicas}, available=${workload.available_replicas}, updated=${workload.updated_replicas}, ready=${workload.ready_replicas ?? "n/a"}</p>
            <p><strong>Conditions:</strong> ${(workload.conditions || []).join(" | ") || "none"}</p>
            <p><strong>Last restart annotation:</strong> ${workload.restarted_at || "none"}</p>
          `
          : "<p><strong>Deployment state:</strong> deployment not found in cluster.</p>"
      }
      <div class="impact-events">
        <strong>Recent Kubernetes events</strong>
        ${
          events.length
            ? `<ul>${events.map((event) => `<li>${event.timestamp} | ${event.type} | ${event.reason} | ${event.message}</li>`).join("")}</ul>`
            : "<p>No recent deployment events found.</p>"
        }
      </div>
    </div>
  `;
}

async function refreshDashboard() {
  const [health, summary, incidents, activity, logs, monitorStatus, dependencies, impact, mttr, automationStatus, queue, approvals, benchmark] = await Promise.all([
    fetchJson("/health"),
    fetchJson("/dashboard/summary"),
    fetchJson("/incidents"),
    fetchJson("/activity"),
    fetchJson("/logs"),
    fetchJson("/monitoring/status"),
    fetchJson("/dependencies"),
    fetchJson("/impact"),
    fetchJson("/reports/mttr"),
    fetchJson("/automation/status"),
    fetchJson("/queue"),
    fetchJson("/approvals?status=pending"),
    fetchJson("/reports/benchmark"),
  ]);

  document.getElementById("health").textContent = JSON.stringify(health, null, 2);
  renderAutomationStatus(automationStatus);
  renderStats(summary);
  renderMttrReport(mttr);
  renderBenchmark(benchmark);
  renderMonitoringStatus(monitorStatus);
  renderQueueOverview(queue);
  renderApprovals(approvals);
  renderDependencies(dependencies);
  renderImpactView(impact);
  renderWorkloads(summary.workloads || []);
  renderIncidents(incidents);
  renderActivity(activity);
  renderLogs(logs);
  setRefreshStatus(`Auto-refresh every 5 seconds. Last updated: ${new Date().toLocaleTimeString()}`);
}

document.getElementById("simulate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    const result = await fetchJson("/incidents/simulate", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form.entries())),
    });
    setMessage(`Queued simulated incident: ${result.queued} for ${result.service}`);
    await refreshDashboard();
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("live-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    const result = await fetchJson("/telemetry/collect/live", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(form.entries())),
    });
    setMessage(`Queued live incident candidate: ${result.queued}`);
    await refreshDashboard();
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("run-loop").addEventListener("click", async () => {
  try {
    const result = await fetchJson("/loop/run-once", { method: "POST" });
    const incident = result.incident;
    if (!incident) {
      setMessage("No queued telemetry events were available.");
    } else {
      setMessage(`Healing cycle completed for ${incident.service}: ${incident.status}`);
    }
    await refreshDashboard();
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("explain-last").addEventListener("click", async () => {
  try {
    const result = await fetchJson("/automation/explain-last-incident", { method: "POST" });
    renderGeminiExplanation(result);
    setMessage(`Gemini explained the last processed incident for ${result.service}.`);
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("refresh").addEventListener("click", refreshDashboard);

document.addEventListener("click", async (event) => {
  const approvalButton = event.target.closest("[data-approval-action]");
  if (approvalButton) {
    const approvalId = approvalButton.getAttribute("data-approval-id");
    const action = approvalButton.getAttribute("data-approval-action");
    try {
      await fetchJson(`/approvals/${approvalId}/${action}`, {
        method: "POST",
        body: JSON.stringify({ comment: "dashboard action" }),
      });
      setMessage(`Approval #${approvalId} ${action}d successfully.`);
      await refreshDashboard();
    } catch (error) {
      setMessage(error.message);
    }
    return;
  }

  const queueButton = event.target.closest("[data-requeue-queue]");
  if (queueButton) {
    const queueId = queueButton.getAttribute("data-requeue-queue");
    try {
      await fetchJson(`/queue/${queueId}/requeue`, { method: "POST" });
      setMessage(`Queue item #${queueId} requeued.`);
      await refreshDashboard();
    } catch (error) {
      setMessage(error.message);
    }
  }
});

refreshDashboard().catch((error) => setMessage(error.message));
renderGeminiExplanation(null);
renderImpactView(null);
setInterval(() => {
  refreshDashboard().catch((error) => setMessage(error.message));
}, 5000);
