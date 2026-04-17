/* ================================================================
   DEMO.JS — Real-time color-coded service status
   
   Color rules:
     🟢 healthy  → green glow
     🔴 down     → red pulse animation
     🟠 degraded → orange
     🟡 slow     → yellow/amber
     🔵 fixed    → blue flash then transitions to green
   ================================================================ */

// Track previous service statuses to detect transitions (broken → fixed = blue flash)
let previousServiceStatuses = {};
let previousFaultMode = null;

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
  document.getElementById("demo-message").textContent = text;
}

/* ================================================================
   STATUS CARD — maps fault_mode to visual state
   ================================================================ */
function getStatusClass(faultMode) {
  // Check if this was just fixed (was broken, now healthy)
  if (faultMode === "healthy" && previousFaultMode && previousFaultMode !== "healthy") {
    previousFaultMode = faultMode;
    return "status-fixed"; // Blue flash!
  }
  previousFaultMode = faultMode;

  switch (faultMode) {
    case "dependency-down":
    case "auth-down":
    case "inventory-down":
      return "status-broken";    // 🔴 RED pulse
    case "payment-slow":
      return "status-slow";      // 🟡 YELLOW
    default:
      return "status-healthy";   // 🟢 GREEN
  }
}

function getStatusEmoji(faultMode) {
  switch (faultMode) {
    case "dependency-down": return "🔴";
    case "auth-down": return "🔴";
    case "inventory-down": return "🔴";
    case "payment-slow": return "🟡";
    case "healthy": return "🟢";
    default: return "⚪";
  }
}

function renderStatus(status) {
  const faultMode = status.fault_mode || "healthy";
  const statusClass = getStatusClass(faultMode);
  const emoji = getStatusEmoji(faultMode);
  const isDown = faultMode !== "healthy" && faultMode !== "payment-slow";
  const isSlow = faultMode === "payment-slow";

  // After blue flash, transition to green after 2 seconds
  if (statusClass === "status-fixed") {
    setTimeout(() => {
      const el = document.querySelector(".status-indicator");
      if (el && el.classList.contains("status-fixed")) {
        el.classList.remove("status-fixed");
        el.classList.add("status-healthy");
        const badge = el.querySelector(".status-badge");
        if (badge) {
          badge.textContent = "🟢 HEALTHY";
          badge.style.background = "var(--green)";
        }
      }
    }, 2000);
  }

  const badgeColor = statusClass === "status-broken" ? "var(--red)"
    : statusClass === "status-slow" ? "var(--yellow)"
    : statusClass === "status-degraded" ? "var(--orange)"
    : statusClass === "status-fixed" ? "var(--blue)"
    : "var(--green)";

  const badgeText = statusClass === "status-broken" ? `🔴 ${faultMode.toUpperCase()}`
    : statusClass === "status-slow" ? "🟡 SLOW"
    : statusClass === "status-fixed" ? "🔵 JUST FIXED"
    : "🟢 HEALTHY";

  document.getElementById("demo-status").innerHTML = `
    <div class="status-indicator ${statusClass} animate-in">
      <span class="status-badge" style="background:${badgeColor}">${badgeText}</span>
      <p><strong>Mode:</strong> ${faultMode}</p>
      <p><strong>Message:</strong> ${status.visible_message}</p>
      <p><strong>Total requests:</strong> ${status.total_requests}</p>
      <p><strong>Failed:</strong> ${status.failed_requests} | <strong>Success:</strong> ${status.successful_requests}</p>
      <p><strong>Last order:</strong> ${status.last_order_status || "n/a"}</p>
      <p><strong>Last error:</strong> ${status.last_error || "none"}</p>
      <p><strong>Changed at:</strong> ${status.last_changed_at || "n/a"}</p>
      
      <!-- Token Quota Tracker -->
      <div style="margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--panel-border);">
        <p style="display: flex; justify-content: space-between; margin-bottom: 4px;">
          <span><strong>Tokens Used:</strong></span> 
          <span style="color:var(--purple);font-family:monospace;font-weight:700">${(status.gemini_tokens_used || 0).toLocaleString()}</span>
        </p>
        <p style="display: flex; justify-content: space-between;">
          <span><strong>Tokens Left:</strong> <span style="font-size:0.7em;color:var(--text-muted)">(1M Daily Limit)</span></span>
          <span style="color:var(--green);font-family:monospace;font-weight:700">${(1000000 - (status.gemini_tokens_used || 0)).toLocaleString()}</span>
        </p>
      </div>
    </div>
  `;
}

/* ================================================================
   SERVICE TOPOLOGY — color-coded nodes per service
   ================================================================ */
function getNodeClass(status) {
  switch (status) {
    case "down": return "node-down";         // 🔴
    case "degraded": return "node-degraded"; // 🟠
    case "slow": return "node-slow";         // 🟡
    default: return "node-healthy";          // 🟢
  }
}

function getFlowClass(status) {
  switch (status) {
    case "down": return "flow-down";
    case "degraded": return "flow-degraded";
    case "slow": return "flow-slow";
    default: return "flow-healthy";
  }
}

function getServiceIcon(service, status) {
  const icons = {
    storefront: status === "healthy" ? "🏪" : "🏚️",
    checkout: status === "healthy" ? "🛒" : (status === "degraded" ? "⚠️" : "❌"),
    auth: status === "healthy" ? "🔐" : "🔓",
    inventory: status === "healthy" ? "📦" : "📭",
    payment: status === "healthy" ? "💳" : (status === "slow" ? "🐢" : "💔"),
  };
  return icons[service] || "⚙️";
}

function getStatusLabel(status, service) {
  // Check if this service was just fixed (was down/degraded/slow, now healthy)
  const prev = previousServiceStatuses[service];
  if (status === "healthy" && prev && prev !== "healthy") {
    // Mark as "just fixed" temporarily
    previousServiceStatuses[service] = status;
    return { label: "FIXED", className: "node-healthy", flowClass: "flow-healthy", isFixed: true };
  }
  previousServiceStatuses[service] = status;

  switch (status) {
    case "down": return { label: "DOWN", className: "node-down", flowClass: "flow-down", isFixed: false };
    case "degraded": return { label: "DEGRADED", className: "node-degraded", flowClass: "flow-degraded", isFixed: false };
    case "slow": return { label: "SLOW", className: "node-slow", flowClass: "flow-slow", isFixed: false };
    default: return { label: "HEALTHY", className: "node-healthy", flowClass: "flow-healthy", isFixed: false };
  }
}

function renderTopology(topology) {
  const services = topology.services || [];

  // Render flow view (storefront → checkout → auth/inventory/payment)
  const flowNode = document.getElementById("topology-flow");
  flowNode.innerHTML = `
    <div class="topology-flow">
      ${services.map((s, i) => {
        const info = getStatusLabel(s.status, s.service);
        const flowClass = info.flowClass;
        return `
          ${i > 0 ? '<span class="flow-arrow">→</span>' : ''}
          <div class="flow-node ${flowClass}">
            <span class="flow-dot"></span>
            ${s.service.toUpperCase()}
          </div>
        `;
      }).join('')}
    </div>
  `;

  // Render detailed node cards
  const topoNode = document.getElementById("demo-topology");
  topoNode.innerHTML = services.map((s) => {
    const nodeClass = getNodeClass(s.status);
    const icon = getServiceIcon(s.service, s.status);
    const statusLabel = s.status.toUpperCase();

    return `
      <div class="service-node ${nodeClass} animate-in">
        <div class="service-icon">${icon}</div>
        <div class="service-name">${s.service}</div>
        <div class="service-status-label">${statusLabel}</div>
        <div class="service-desc">${s.message}</div>
      </div>
    `;
  }).join('');
}

/* ================================================================
   CUSTOMER RESULT
   ================================================================ */
function renderCustomerResult(result) {
  const node = document.getElementById("customer-result");
  node.innerHTML = `
    <div class="customer-card ${result.success ? "customer-ok" : "customer-fail"} animate-in">
      <h3>${result.success ? "✅ Order Accepted" : "❌ Checkout Error"}</h3>
      <p>${result.message}</p>
      <p><strong>Status code:</strong> ${result.status_code}</p>
      <p><strong>Order ID:</strong> ${result.order_id || "none"}</p>
    </div>
  `;
}

/* ================================================================
   TRACES
   ================================================================ */
function renderTraces(topology) {
  const node = document.getElementById("demo-traces");
  const traces = topology.recent_traces || [];
  if (!traces.length) {
    node.innerHTML = '<p style="color:var(--text-muted)">No demo traces yet.</p>';
    return;
  }

  node.innerHTML = traces.map((trace) => `
    <div class="trace-entry ${trace.outcome === "success" ? "trace-success" : "trace-failure"} animate-in">
      <div class="trace-time">${trace.timestamp}</div>
      <div class="trace-outcome">${trace.outcome === "success" ? "✅" : "❌"} ${trace.outcome}</div>
      <div class="trace-detail">
        <strong>${trace.summary}</strong><br/>
        <span>${(trace.services || []).join(" → ")}</span>
      </div>
    </div>
  `).join('');
}

/* ================================================================
   REFRESH LOOP — polls every 2 seconds
   ================================================================ */
async function refreshStatus() {
  const [status, topology] = await Promise.all([
    fetchJson("/demo/status"),
    fetchJson("/demo/topology"),
  ]);
  renderStatus(status);
  renderTopology(topology);
  renderTraces(topology);
}

async function postCheckout() {
  const response = await fetch("/demo/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return response.json();
}

/* ================================================================
   EVENT LISTENERS
   ================================================================ */
document.getElementById("break-dependency").addEventListener("click", async () => {
  try {
    const status = await fetchJson("/demo/faults/dependency-down", {
      method: "POST",
      body: JSON.stringify({ enabled: true }),
    });
    renderStatus(status);
    await refreshStatus();
    setMessage("💥 Payment dependency is BROKEN. Services turning red...");
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("break-inventory").addEventListener("click", async () => {
  try {
    await toggleFault("/demo/faults/inventory", "💥 Inventory is BROKEN. Service turning red...");
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("break-auth").addEventListener("click", async () => {
  try {
    await toggleFault("/demo/faults/auth", "💥 Auth is BROKEN. Service turning red...");
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("slow-payment").addEventListener("click", async () => {
  try {
    await toggleFault("/demo/faults/payment_slow", "🐢 Payment is SLOW. Service turning yellow...");
  } catch (error) {
    setMessage(error.message);
  }
});

async function toggleFault(path, message) {
  const status = await fetchJson(path, {
    method: "POST",
    body: JSON.stringify({ enabled: true }),
  });
  renderStatus(status);
  await refreshStatus();
  setMessage(message);
}

document.getElementById("restore-dependency").addEventListener("click", async () => {
  try {
    const status = await fetchJson("/demo/faults/dependency-down", {
      method: "POST",
      body: JSON.stringify({ enabled: false }),
    });
    await fetchJson("/demo/faults/inventory", {
      method: "POST",
      body: JSON.stringify({ enabled: false }),
    });
    await fetchJson("/demo/faults/auth", {
      method: "POST",
      body: JSON.stringify({ enabled: false }),
    });
    await fetchJson("/demo/faults/payment_slow", {
      method: "POST",
      body: JSON.stringify({ enabled: false }),
    });
    renderStatus(status);
    await refreshStatus();
    setMessage("🔧 All services restored! Flashing blue → green...");
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("place-order").addEventListener("click", async () => {
  try {
    const result = await postCheckout();
    renderCustomerResult(result);
    renderStatus(result.status);
    await refreshStatus();
    setMessage(result.success ? "✅ " + result.message : "❌ " + result.message);
  } catch (error) {
    setMessage(error.message);
  }
});

document.getElementById("send-to-ai").addEventListener("click", async () => {
  try {
    const result = await fetchJson("/telemetry/collect/demo", { method: "POST" });
    setMessage(`🚀 Queued ${result.queued} for ${result.service}. Open the dashboard and run healing cycle.`);
  } catch (error) {
    setMessage(error.message);
  }
});

// Initial load + auto-refresh every 2 seconds
refreshStatus().catch((error) => setMessage(error.message));
setInterval(() => {
  refreshStatus().catch(() => {});
}, 2000);
