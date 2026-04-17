from __future__ import annotations

from app.models import Incident, TelemetryEvent


class MonitorAgent:
    def detect(self, event: TelemetryEvent, incident_id: str) -> Incident:
        timeline = [f"Monitor detected anomaly for service '{event.service}'"]
        if event.traces:
            timeline.append(f"Trace evidence: {' | '.join(event.traces[:2])}")
        dependencies = event.metadata.get("dependencies", [])
        impacted_services = event.metadata.get("impacted_services", [])
        if dependencies:
            timeline.append(f"Known dependencies: {', '.join(dependencies[:4])}")
        if impacted_services:
            timeline.append(f"Potential cascading impact: {', '.join(impacted_services[:4])}")

        return Incident(
            id=incident_id,
            scenario=event.scenario,
            service=event.service,
            namespace=event.namespace,
            symptoms=event.symptoms,
            metrics=event.metrics,
            traces=event.traces,
            timeline=timeline,
        )
