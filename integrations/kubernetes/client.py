from __future__ import annotations

from datetime import datetime, timezone

from kubernetes import client, config

from app.models import ActionStatus, ClusterWorkload, ImpactView, RemediationAction, WorkloadEvent
from app.state import state


class KubernetesExecutor:
    def __init__(self, mode: str = "mock") -> None:
        self.mode = mode
        self.apps_api = None
        self.core_api = None
        self._ready = False

        if self.mode == "cluster":
            try:
                config.load_kube_config()
            except Exception:
                try:
                    config.load_incluster_config()
                except Exception:
                    self.mode = "mock"
            if self.mode == "cluster":
                self.apps_api = client.AppsV1Api()
                self.core_api = client.CoreV1Api()
                self._ready = True

    def execute(self, action: RemediationAction) -> RemediationAction:
        if action.target_name == "checkout" and action.namespace == "demo":
            if action.action in {"restart_deployment", "scale_deployment"}:
                state.reset_demo_environment(f"self-healing action {action.action}")
                action.status = ActionStatus.executed
                return action
            if action.action == "rollback_deployment":
                state.reset_demo_environment("self-healing rollback")
                action.status = ActionStatus.executed
                return action

        if self.mode != "cluster" or not self._ready:
            action.status = ActionStatus.executed
            return action

        try:
            if action.action == "restart_deployment":
                restarted_at = datetime.now(timezone.utc).isoformat()
                body = {
                    "spec": {
                        "template": {
                            "metadata": {
                                "annotations": {
                                    "kubectl.kubernetes.io/restartedAt": restarted_at
                                }
                            }
                        }
                    }
                }
                self.apps_api.patch_namespaced_deployment(
                    name=action.target_name,
                    namespace=action.namespace,
                    body=body,
                )
            elif action.action == "scale_deployment":
                replicas = int(action.parameters.get("replicas", 1))
                scale_body = {"spec": {"replicas": replicas}}
                self.apps_api.patch_namespaced_deployment_scale(
                    name=action.target_name,
                    namespace=action.namespace,
                    body=scale_body,
                )
            elif action.action == "rollback_deployment":
                if not self._rollback_deployment(action.target_name, action.namespace):
                    action.status = ActionStatus.failed
                    return action

            action.status = ActionStatus.executed
            return action
        except Exception:
            action.status = ActionStatus.failed
            return action

    def _rollback_deployment(self, name: str, namespace: str) -> bool:
        deployment = self.apps_api.read_namespaced_deployment(name=name, namespace=namespace)
        selector = deployment.spec.selector.match_labels or {}
        if not selector:
            return False

        label_selector = ",".join(f"{key}={value}" for key, value in selector.items())
        replica_sets = self.apps_api.list_namespaced_replica_set(namespace=namespace, label_selector=label_selector).items
        owned_sets = [
            replica_set
            for replica_set in replica_sets
            if any(
                owner.kind == "Deployment" and owner.name == name
                for owner in (replica_set.metadata.owner_references or [])
            )
        ]
        if len(owned_sets) < 2:
            return False

        def revision(replica_set) -> int:
            annotations = replica_set.metadata.annotations or {}
            try:
                return int(annotations.get("deployment.kubernetes.io/revision", "0"))
            except ValueError:
                return 0

        ordered_sets = sorted(owned_sets, key=revision, reverse=True)
        current_set = ordered_sets[0]
        previous_set = next((item for item in ordered_sets[1:] if revision(item) < revision(current_set)), None)
        if previous_set is None or previous_set.spec.template is None:
            return False

        template = previous_set.spec.template.to_dict()
        metadata = template.get("metadata") or {}
        annotations = metadata.get("annotations") or {}
        annotations["selfheal.ai/rollbackAt"] = datetime.now(timezone.utc).isoformat()
        annotations["selfheal.ai/rollbackFromRevision"] = str(revision(current_set))
        annotations["selfheal.ai/rollbackToRevision"] = str(revision(previous_set))
        metadata["annotations"] = annotations
        template["metadata"] = metadata

        body = {"spec": {"template": template}}
        self.apps_api.patch_namespaced_deployment(name=name, namespace=namespace, body=body)
        return True

    def list_workloads(self, namespace: str | None = None) -> list[ClusterWorkload]:
        if self.mode != "cluster" or not self._ready:
            return [
                ClusterWorkload(
                    name="checkout",
                    namespace=namespace or "demo",
                    desired_replicas=3,
                    available_replicas=3,
                    updated_replicas=3,
                    ready_replicas=3,
                    conditions=["Available=True", "Progressing=True"],
                )
            ]

        if namespace:
            response = self.apps_api.list_namespaced_deployment(namespace=namespace)
        else:
            response = self.apps_api.list_deployment_for_all_namespaces()

        workloads: list[ClusterWorkload] = []
        for item in response.items:
            workloads.append(
                ClusterWorkload(
                    name=item.metadata.name,
                    namespace=item.metadata.namespace,
                    desired_replicas=item.spec.replicas or 0,
                    available_replicas=item.status.available_replicas or 0,
                    updated_replicas=item.status.updated_replicas or 0,
                    ready_replicas=item.status.ready_replicas,
                    conditions=[
                        f"{condition.type}={condition.status}"
                        for condition in (item.status.conditions or [])
                    ],
                    restarted_at=(item.spec.template.metadata.annotations or {}).get(
                        "kubectl.kubernetes.io/restartedAt"
                    ),
                )
            )
        return workloads

    def impact_view(
        self,
        *,
        service: str | None,
        namespace: str | None,
        scenario: str | None,
        latest_action: str | None,
        latest_action_status: str | None,
        incident_id: str | None,
        simulated_incident_only: bool,
    ) -> ImpactView:
        if not service or not namespace:
            return ImpactView(
                mode=self.mode,
                simulated_incident_only=simulated_incident_only,
                incident_id=incident_id,
                service=service,
                namespace=namespace,
                scenario=scenario,
                latest_action=latest_action,
                latest_action_status=latest_action_status,
                summary="No processed incident is available yet.",
            )

        if self.mode != "cluster" or not self._ready:
            workload = ClusterWorkload(
                name=service,
                namespace=namespace,
                desired_replicas=3,
                available_replicas=3,
                updated_replicas=3,
                ready_replicas=3,
                conditions=["Available=True"],
            )
            return ImpactView(
                mode=self.mode,
                simulated_incident_only=simulated_incident_only,
                incident_id=incident_id,
                service=service,
                namespace=namespace,
                scenario=scenario,
                latest_action=latest_action,
                latest_action_status=latest_action_status,
                summary="Mock mode only shows synthetic workload impact. No real cluster workload was changed.",
                workload=workload,
                events=[],
            )

        if service == "checkout" and namespace == "demo":
            workload = ClusterWorkload(
                name=service,
                namespace=namespace,
                desired_replicas=1,
                available_replicas=1,
                updated_replicas=1,
                ready_replicas=1,
                conditions=["DemoWorkload=True"],
            )
            summary = (
                "This is the visible demo storefront. The customer-facing failure is shown on /demo-app, and the self-healing action cleared that fault."
                if simulated_incident_only
                else "This visible demo storefront is using real customer-facing failure state from /demo-app."
            )
            return ImpactView(
                mode=self.mode,
                simulated_incident_only=simulated_incident_only,
                incident_id=incident_id,
                service=service,
                namespace=namespace,
                scenario=scenario,
                latest_action=latest_action,
                latest_action_status=latest_action_status,
                summary=summary,
                workload=workload,
                events=[],
            )

        workload = self._read_workload(service, namespace)
        events = self._recent_events(service, namespace)
        summary = (
            "This incident was simulated, so the fault itself was not injected into the app. "
            "Only the remediation action and cluster state below are real."
            if simulated_incident_only
            else "This view shows the real workload state and recent Kubernetes events for the affected deployment."
        )
        return ImpactView(
            mode=self.mode,
            simulated_incident_only=simulated_incident_only,
            incident_id=incident_id,
            service=service,
            namespace=namespace,
            scenario=scenario,
            latest_action=latest_action,
            latest_action_status=latest_action_status,
            summary=summary,
            workload=workload,
            events=events,
        )

    def _read_workload(self, service: str, namespace: str) -> ClusterWorkload | None:
        try:
            item = self.apps_api.read_namespaced_deployment(name=service, namespace=namespace)
        except Exception:
            return None

        return ClusterWorkload(
            name=item.metadata.name,
            namespace=item.metadata.namespace,
            desired_replicas=item.spec.replicas or 0,
            available_replicas=item.status.available_replicas or 0,
            updated_replicas=item.status.updated_replicas or 0,
            ready_replicas=item.status.ready_replicas,
            conditions=[
                f"{condition.type}={condition.status}"
                for condition in (item.status.conditions or [])
            ],
            restarted_at=(item.spec.template.metadata.annotations or {}).get("kubectl.kubernetes.io/restartedAt"),
        )

    def _recent_events(self, service: str, namespace: str) -> list[WorkloadEvent]:
        try:
            response = self.core_api.list_namespaced_event(
                namespace=namespace,
                field_selector=f"involvedObject.kind=Deployment,involvedObject.name={service}",
            )
        except Exception:
            return []

        sorted_items = sorted(
            response.items,
            key=lambda item: item.last_timestamp
            or item.event_time
            or item.first_timestamp
            or datetime.now(timezone.utc),
            reverse=True,
        )
        events: list[WorkloadEvent] = []
        for item in sorted_items[:8]:
            timestamp = item.last_timestamp or item.event_time or item.first_timestamp
            events.append(
                WorkloadEvent(
                    timestamp=timestamp.isoformat() if timestamp else "unknown",
                    type=item.type or "Normal",
                    reason=item.reason or "Unknown",
                    message=item.message or "",
                )
            )
        return events
