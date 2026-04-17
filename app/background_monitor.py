from __future__ import annotations

from datetime import datetime
import logging
import threading
import time

from app.database import SessionLocal
from app.repository import IncidentRepository
from app.state import AppState
from integrations.kubernetes.client import KubernetesExecutor
from integrations.telemetry.provider import TelemetryProvider

logger = logging.getLogger("selfheal.monitor")


class BackgroundMonitor:
    def __init__(
        self,
        *,
        enabled: bool,
        interval_seconds: int,
        max_events_per_scan: int,
        max_queue_depth: int,
        namespaces: list[str],
        state: AppState,
        executor: KubernetesExecutor,
        telemetry: TelemetryProvider,
        orchestrator,
    ) -> None:
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        self.max_events_per_scan = max_events_per_scan
        self.max_queue_depth = max_queue_depth
        self.namespaces = namespaces
        self.state = state
        self.executor = executor
        self.telemetry = telemetry
        self.orchestrator = orchestrator
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.recent_events: dict[tuple[str, str, str], float] = {}

    def start(self) -> None:
        self.state.update_monitoring_status(
            enabled=self.enabled,
            running=False,
            interval_seconds=self.interval_seconds,
        )
        if not self.enabled:
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="selfheal-background-monitor")
        self.thread.start()
        self.state.log("Background monitor thread started", "success")
        logger.info("Background monitor started with %ss interval", self.interval_seconds)

    def stop(self) -> None:
        self.stop_event.set()
        self.state.update_monitoring_status(running=False, last_message="Background monitor stopped")

    def _run_loop(self) -> None:
        self.state.update_monitoring_status(running=True, last_message="Background monitor is scanning workloads")
        while not self.stop_event.is_set():
            scanned = 0
            remediated = 0
            try:
                workloads = self._list_targets()
                scanned = len(workloads)
                if self.telemetry.depth() >= self.max_queue_depth:
                    message = (
                        f"Queue depth {self.telemetry.depth()} reached safety limit {self.max_queue_depth}; "
                        "background monitor paused this scan"
                    )
                    self.state.log(message, "warning")
                    self.state.update_monitoring_status(
                        running=True,
                        last_scan_time=datetime.now().strftime("%H:%M:%S"),
                        last_message=message,
                        targets_scanned=scanned,
                    )
                    logger.warning(message)
                    self.stop_event.wait(self.interval_seconds)
                    continue

                processed_this_scan = 0
                for namespace, service in workloads:
                    if processed_this_scan >= self.max_events_per_scan:
                        self.state.log(
                            f"Background monitor hit max_events_per_scan={self.max_events_per_scan}",
                            "warning",
                        )
                        logger.warning("Background monitor reached max_events_per_scan=%s", self.max_events_per_scan)
                        break
                    event = self.telemetry.collect_live(service=service, namespace=namespace)
                    if event is None:
                        continue
                    cache_key = (event.namespace, event.service, event.scenario)
                    now = time.time()
                    if now - self.recent_events.get(cache_key, 0) < self.interval_seconds:
                        continue

                    self.recent_events[cache_key] = now
                    self.telemetry.push(event)
                    self.state.log(
                        f"Background monitor queued '{event.scenario}' for service '{event.service}'",
                        "info",
                    )
                    logger.info(
                        "Background monitor queued event: scenario=%s service=%s namespace=%s",
                        event.scenario,
                        event.service,
                        event.namespace,
                    )
                    with SessionLocal() as session:
                        repository = IncidentRepository(session)
                        result = self.orchestrator.run_once(repository)
                        if result.incident is not None:
                            remediated += 1
                            processed_this_scan += 1
            except Exception as exc:
                message = f"Background monitor scan failed: {exc}"
                self.state.log(message, "error")
                logger.exception(message)
                self.state.update_monitoring_status(
                    running=True,
                    last_scan_time=datetime.now().strftime("%H:%M:%S"),
                    last_message=message,
                    targets_scanned=scanned,
                )
            else:
                last_message = (
                    f"Scanned {scanned} workloads and processed {remediated} anomalies"
                    if scanned
                    else "No workloads available for background monitoring"
                )
                self.state.update_monitoring_status(
                    running=True,
                    last_scan_time=datetime.now().strftime("%H:%M:%S"),
                    last_remediation_time=datetime.now().strftime("%H:%M:%S") if remediated else None,
                    last_message=last_message,
                    targets_scanned=scanned,
                )
                logger.info(last_message)

            self.stop_event.wait(self.interval_seconds)

    def _list_targets(self) -> list[tuple[str, str]]:
        targets: list[tuple[str, str]] = []
        if self.namespaces:
            for namespace in self.namespaces:
                for workload in self.executor.list_workloads(namespace=namespace):
                    targets.append((workload.namespace, workload.name))
            return targets

        for workload in self.executor.list_workloads():
            targets.append((workload.namespace, workload.name))
        return targets
