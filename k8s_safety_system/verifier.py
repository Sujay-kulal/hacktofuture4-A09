class Verifier:
    """Simulates a monitoring layer that checks Prometheus/Datadog after an AI action."""
    
    def verify_action(self, action) -> bool:
        """Determines if the action resulted in positive system recovery."""
        print(f" -> [Verifier] Analyzing metrics (latency, error_rate) for {action.target}...")
        
        # We simulate a failure if the metadata asks us to for demo purposes
        force_fail = action.metadata.get("force_fail_verification", False)
        
        if force_fail:
            print(" -> [Verifier] FAILED: Health metrics collapsed. System is degraded.")
            return False
            
        print(" -> [Verifier] SUCCESS: Error rate decreased, latency improved.")
        return True
