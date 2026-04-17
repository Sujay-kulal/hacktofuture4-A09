from models import Action

class ActionExecutor:
    """Simulates Kubernetes API executions and captures previous cluster state."""
    
    def __init__(self):
        # Store state BEFORE mutation to allow 100% reliable rollback
        self.previous_states = {}
        
        # Mock cluster state
        self.mock_cluster_state = {
            "web-deployment": {"replicas": 3, "version": "v1.2.0"},
            "db-deployment": {"replicas": 1, "version": "v3.0.0"}
        }

    def execute(self, action: Action) -> bool:
        """Dispatches execution explicitly, ensuring only pre-defined mocks run."""
        if action.type == "restart_pod":
            return self._restart_pod(action)
        elif action.type == "scale_deployment":
            return self._scale_deployment(action)
        elif action.type == "rollback_deployment":
            return self._rollback_deployment(action)
            
        return False

    def _restart_pod(self, action: Action) -> bool:
        print(f" -> [K8s API Mock] Progressively deleting pod {action.target} (1 at a time)")
        return True
        
    def _scale_deployment(self, action: Action) -> bool:
        target = action.target
        desired = action.metadata.get("desired_replicas", 1)
        
        # 1. Take state snapshot
        current = self.mock_cluster_state.get(target, {}).get("replicas", -1)
        self.previous_states[action.signature] = {"type": "scale", "replicas": current}
        
        # 2. Mutate state
        print(f" -> [K8s API Mock] Executing scale for {target} to {desired} replicas")
        if target in self.mock_cluster_state:
            self.mock_cluster_state[target]["replicas"] = desired
        return True
        
    def _rollback_deployment(self, action: Action) -> bool:
        target = action.target
        
        # 1. Take state snapshot
        current_version = self.mock_cluster_state.get(target, {}).get("version", "unknown")
        self.previous_states[action.signature] = {"type": "deploy_version", "version": current_version}
        
        # 2. Mutate state
        print(f" -> [K8s API Mock] Triggering `kubectl rollout undo` for {target}")
        if target in self.mock_cluster_state:
            self.mock_cluster_state[target]["version"] = "previous-version"
        return True

    def get_previous_state(self, action_signature: str):
        return self.previous_states.get(action_signature)
