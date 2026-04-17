from action_executor import ActionExecutor
from models import Action

class RollbackSystem:
    """Restores the Kubernetes state if an AI action exacerbates the problem."""
    
    def __init__(self, executor: ActionExecutor):
        self.executor = executor
        
    def rollback(self, action: Action):
        print(f" -> [Rollback Component] Active mapping identified!")
        
        prev_state = self.executor.get_previous_state(action.signature)
        if not prev_state:
            print(" -> [Rollback] No previous state captured to rollback to!")
            return False
            
        target = action.target
        
        if prev_state["type"] == "scale":
            old_replicas = prev_state["replicas"]
            print(f" -> [K8s API Mock Rollback] Reverting scale for {target} to original {old_replicas} replicas.")
            if target in self.executor.mock_cluster_state:
                self.executor.mock_cluster_state[target]["replicas"] = old_replicas
                
        elif prev_state["type"] == "deploy_version":
            old_version = prev_state["version"]
            print(f" -> [K8s API Mock Rollback] Redeploying original verified version {old_version} for {target}.")
            if target in self.executor.mock_cluster_state:
                self.executor.mock_cluster_state[target]["version"] = old_version
                
        return True
