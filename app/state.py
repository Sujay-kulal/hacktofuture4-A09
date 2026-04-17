from __future__ import annotations

from datetime import datetime
import json
import os
from typing import List
from uuid import uuid4

from app.models import (
    ActivityEntry,
    DemoAppStatus,
    DemoCheckoutResponse,
    DemoServiceState,
    DemoTopologyStatus,
    DemoTraceRecord,
    GeminiIncidentExplanation,
    Incident,
    LogEntry,
    MonitoringStatus,
    RemediationAction,
    TelemetryEvent,
)


class AppState:
    def __init__(self) -> None:
        self.telemetry_queue: List[TelemetryEvent] = []
        self.activity_feed: List[ActivityEntry] = []
        self.log_feed: List[LogEntry] = []
        self.monitoring_status = MonitoringStatus(
            enabled=False,
            running=False,
            interval_seconds=30,
            last_message="Background monitor not started",
        )
        self.last_processed_event: TelemetryEvent | None = None
        self.last_processed_incident: Incident | None = None
        self.last_processed_action: RemediationAction | None = None
        self.last_gemini_explanation: GeminiIncidentExplanation | None = None
        self.demo_dependency_down = False
        self.demo_inventory_down = False
        self.demo_auth_down = False
        
        self.gemini_tokens_used = 0
        if os.path.exists("tokens_usage.json"):
            try:
                with open("tokens_usage.json", "r") as f:
                    self.gemini_tokens_used = json.load(f).get("tokens", 0)
            except Exception:
                pass

        self.demo_payment_slow = False
        self.demo_total_requests = 0
        self.demo_failed_requests = 0
        self.demo_successful_requests = 0
        self.demo_last_error: str | None = None
        self.demo_last_order_status: str | None = None
        self.demo_last_changed_at: str | None = None
        self.demo_last_order_at: str | None = None
        self.demo_last_fault_service: str | None = None
        self.demo_recent_traces: List[DemoTraceRecord] = []

    def log(self, message: str, level: str = "info") -> None:
        self.activity_feed.insert(
            0,
            ActivityEntry(
                timestamp=datetime.now().strftime("%H:%M:%S"),
                level=level,
                message=message,
            ),
        )
        self.activity_feed = self.activity_feed[:200]

    def add_log(self, message: str, level: str = "INFO", source: str = "app") -> None:
        self.log_feed.insert(
            0,
            LogEntry(
                timestamp=datetime.now().strftime("%H:%M:%S"),
                level=level.upper(),
                source=source,
                message=message,
            ),
        )
        self.log_feed = self.log_feed[:400]

    def update_monitoring_status(
        self,
        *,
        enabled: bool | None = None,
        running: bool | None = None,
        interval_seconds: int | None = None,
        last_scan_time: str | None = None,
        last_remediation_time: str | None = None,
        last_message: str | None = None,
        targets_scanned: int | None = None,
    ) -> None:
        current = self.monitoring_status
        self.monitoring_status = MonitoringStatus(
            enabled=current.enabled if enabled is None else enabled,
            running=current.running if running is None else running,
            interval_seconds=current.interval_seconds if interval_seconds is None else interval_seconds,
            last_scan_time=current.last_scan_time if last_scan_time is None else last_scan_time,
            last_remediation_time=current.last_remediation_time if last_remediation_time is None else last_remediation_time,
            last_message=current.last_message if last_message is None else last_message,
            targets_scanned=current.targets_scanned if targets_scanned is None else targets_scanned,
        )

    def record_last_run(
        self,
        *,
        event: TelemetryEvent | None,
        incident: Incident | None,
        action: RemediationAction | None,
    ) -> None:
        self.last_processed_event = event
        self.last_processed_incident = incident
        self.last_processed_action = action

    def set_gemini_explanation(self, explanation: GeminiIncidentExplanation | None) -> None:
        self.last_gemini_explanation = explanation

    def add_gemini_tokens(self, tokens: int) -> None:
        self.gemini_tokens_used += tokens
        try:
            with open("tokens_usage.json", "w") as f:
                json.dump({"tokens": self.gemini_tokens_used}, f)
        except Exception:
            pass

    def demo_status(self) -> DemoAppStatus:
        if self.demo_auth_down:
            visible_message = "Auth service is down. Storefront requests are failing before checkout."
            fault_mode = "auth-down"
        elif self.demo_inventory_down:
            visible_message = "Inventory service is down. Checkout cannot reserve stock."
            fault_mode = "inventory-down"
        elif self.demo_dependency_down:
            visible_message = "Payment dependency is down. Checkout requests are failing right now."
            fault_mode = "dependency-down"
        elif self.demo_payment_slow:
            visible_message = "Payment dependency is slow. Checkout is degraded with high latency."
            fault_mode = "payment-slow"
        else:
            visible_message = "Checkout service is healthy."
            fault_mode = "healthy"
        return DemoAppStatus(
            dependency_down=self.demo_dependency_down,
            inventory_down=self.demo_inventory_down,
            auth_down=self.demo_auth_down,
            payment_slow=self.demo_payment_slow,
            total_requests=self.demo_total_requests,
            failed_requests=self.demo_failed_requests,
            successful_requests=self.demo_successful_requests,
            last_error=self.demo_last_error,
            last_order_status=self.demo_last_order_status,
            last_changed_at=self.demo_last_changed_at,
            last_order_at=self.demo_last_order_at,
            fault_mode=fault_mode,
            visible_message=visible_message,
            gemini_tokens_used=self.gemini_tokens_used,
        )

    def set_demo_dependency(self, enabled: bool, source: str) -> DemoAppStatus:
        return self.set_demo_fault("payment", enabled, source)

    def set_demo_fault(self, fault: str, enabled: bool, source: str) -> DemoAppStatus:
        self.demo_last_changed_at = datetime.now().strftime("%H:%M:%S")
        if fault == "payment":
            self.demo_dependency_down = enabled
            if enabled:
                self.demo_last_fault_service = "payment"
                self.demo_last_error = "payment dependency unreachable"
                self.log(f"Demo payment fault enabled by {source}", "warning")
            else:
                self.demo_last_error = None
                self.log(f"Demo payment dependency restored by {source}", "success")
        elif fault == "inventory":
            self.demo_inventory_down = enabled
            if enabled:
                self.demo_last_fault_service = "inventory"
                self.demo_last_error = "inventory service unavailable"
                self.log(f"Demo inventory fault enabled by {source}", "warning")
            else:
                self.demo_last_error = None
                self.log(f"Demo inventory service restored by {source}", "success")
        elif fault == "auth":
            self.demo_auth_down = enabled
            if enabled:
                self.demo_last_fault_service = "auth"
                self.demo_last_error = "auth service unavailable"
                self.log(f"Demo auth fault enabled by {source}", "warning")
            else:
                self.demo_last_error = None
                self.log(f"Demo auth service restored by {source}", "success")
        elif fault == "payment_slow":
            self.demo_payment_slow = enabled
            if enabled:
                self.demo_last_fault_service = "payment"
                self.demo_last_error = "payment service exceeded latency budget"
                self.log(f"Demo payment latency fault enabled by {source}", "warning")
            else:
                self.demo_last_error = None
                self.log(f"Demo payment latency restored by {source}", "success")
        return self.demo_status()

    def reset_demo_environment(self, source: str) -> DemoAppStatus:
        self.demo_dependency_down = False
        self.demo_inventory_down = False
        self.demo_auth_down = False
        self.demo_payment_slow = False
        self.demo_last_error = None
        self.demo_last_fault_service = None
        self.demo_last_changed_at = datetime.now().strftime("%H:%M:%S")
        self.log(f"Demo environment restored by {source}", "success")
        return self.demo_status()

    def process_demo_checkout(self) -> DemoCheckoutResponse:
        self.demo_total_requests += 1
        self.demo_last_order_at = datetime.now().strftime("%H:%M:%S")
        if self.demo_auth_down:
            self.demo_failed_requests += 1
            self.demo_last_order_status = "failed"
            self.demo_last_error = "checkout failed because auth service is down"
            self.log("Demo storefront checkout failed because auth service is down", "error")
            return DemoCheckoutResponse(
                success=False,
                message="Checkout failed. Auth service is unavailable.",
                status_code=503,
                status=self.demo_status(),
            )

        if self.demo_inventory_down:
            self.demo_failed_requests += 1
            self.demo_last_order_status = "failed"
            self.demo_last_error = "checkout failed because inventory service is down"
            self.log("Demo storefront checkout failed because inventory service is down", "error")
            return DemoCheckoutResponse(
                success=False,
                message="Checkout failed. Inventory service is unavailable.",
                status_code=503,
                status=self.demo_status(),
            )

        if self.demo_dependency_down:
            self.demo_failed_requests += 1
            self.demo_last_order_status = "failed"
            self.demo_last_error = "checkout failed because payment dependency is down"
            self.log("Demo storefront checkout failed because payment dependency is down", "error")
            return DemoCheckoutResponse(
                success=False,
                message="Checkout failed. Payment dependency is down.",
                status_code=503,
                status=self.demo_status(),
            )

        self.demo_successful_requests += 1
        self.demo_last_order_status = "success"
        self.demo_last_error = (
            "checkout succeeded but payment exceeded latency budget"
            if self.demo_payment_slow
            else None
        )
        order_id = f"demo-{uuid4().hex[:8]}"
        if self.demo_payment_slow:
            self.log(f"Demo storefront checkout succeeded slowly with order {order_id}", "warning")
        else:
            self.log(f"Demo storefront checkout succeeded with order {order_id}", "success")
        return DemoCheckoutResponse(
            success=True,
            message="Checkout succeeded, but payment was slow." if self.demo_payment_slow else "Checkout succeeded.",
            order_id=order_id,
            status_code=200,
            status=self.demo_status(),
        )

    def record_demo_trace(self, trace_id: str, services: list[str], outcome: str, summary: str) -> None:
        record = DemoTraceRecord(
            trace_id=trace_id,
            services=services,
            outcome=outcome,
            summary=summary,
            timestamp=datetime.now().strftime("%H:%M:%S"),
        )
        self.demo_recent_traces.insert(0, record)
        self.demo_recent_traces = self.demo_recent_traces[:20]

    def recent_demo_traces(self) -> list[DemoTraceRecord]:
        return list(self.demo_recent_traces)

    def demo_topology_status(self) -> DemoTopologyStatus:
        services = [
            DemoServiceState(
                service="storefront",
                status="degraded" if any([self.demo_auth_down, self.demo_inventory_down, self.demo_dependency_down]) else "healthy",
                message="Customer-facing UI and order entry",
                affected=any([self.demo_auth_down, self.demo_inventory_down, self.demo_dependency_down, self.demo_payment_slow]),
            ),
            DemoServiceState(
                service="checkout",
                status="degraded" if any([self.demo_auth_down, self.demo_inventory_down, self.demo_dependency_down, self.demo_payment_slow]) else "healthy",
                message="Coordinates auth, inventory, and payment",
                affected=any([self.demo_auth_down, self.demo_inventory_down, self.demo_dependency_down, self.demo_payment_slow]),
            ),
            DemoServiceState(
                service="auth",
                status="down" if self.demo_auth_down else "healthy",
                message="Authenticates the customer session",
                affected=self.demo_auth_down,
            ),
            DemoServiceState(
                service="inventory",
                status="down" if self.demo_inventory_down else "healthy",
                message="Reserves available stock",
                affected=self.demo_inventory_down,
            ),
            DemoServiceState(
                service="payment",
                status="slow" if self.demo_payment_slow and not self.demo_dependency_down else ("down" if self.demo_dependency_down else "healthy"),
                message="Charges the customer and confirms payment",
                affected=self.demo_dependency_down or self.demo_payment_slow,
            ),
        ]
        return DemoTopologyStatus(
            services=services,
            last_trace=self.demo_recent_traces[0] if self.demo_recent_traces else None,
            recent_traces=list(self.demo_recent_traces[:6]),
        )


state = AppState()
