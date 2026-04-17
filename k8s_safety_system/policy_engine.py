import time
from models import Action

class PolicyEngine:
    """
    Deterministic rule engine that validates AI actions before execution.
    NO LLM is used here. This is pure code-based safety.
    """
    def __init__(self):
        self.WHITELIST = {"restart_pod", "scale_deployment", "rollback_deployment"}
        self.MIN_CONFIDENCE = 0.8
        self.MAX_RESTARTS_PER_MIN = 5
        self.MAX_SCALE_MULTIPLIER = 2.0
        self.MAX_PODS_AFFECTED = 10
        self.COOLDOWN_SECONDS = 120
        self.MAX_CONSECUTIVE_FAILURES = 5
        
        # State tracking for rules
        self.action_history = []
        self.cooldown_tracker = {} # signature -> timestamp
        self.recent_restarts = [] # timestamps of pod restarts
        self.consecutive_failures = 0
        self.circuit_breaker_tripped = False
        
    def validate(self, action: Action) -> tuple[bool, str]:
        """Validates an action against strict safety rules before execution."""
        
        # 1. Circuit Breaker
        if self.circuit_breaker_tripped:
            return False, "REJECTED: Circuit breaker is open due to consecutive AI failures."
            
        # 2. Whitelist Check (Critical Safety)
        if action.type not in self.WHITELIST:
            return False, f"REJECTED: Action '{action.type}' is hallucinated or dangerous. Not in whitelist."
            
        # 3. Confidence Threshold Check
        if action.confidence < self.MIN_CONFIDENCE:
            return False, f"REJECTED: AI Confidence ({action.confidence}) is below strict minimum ({self.MIN_CONFIDENCE})."
            
        # 4. Cooldown Check
        last_execution_time = self.cooldown_tracker.get(action.signature, 0)
        if time.time() - last_execution_time < self.COOLDOWN_SECONDS:
            return False, f"REJECTED: Action '{action.signature}' is cooling down. Wait 120s."
            
        # 5. Type-specific checks
        if action.type == "restart_pod":
            pods_to_restart = action.metadata.get("pod_count", 1)
            
            # Scope Limit
            if pods_to_restart > self.MAX_PODS_AFFECTED:
                return False, f"REJECTED: Bulk operation requested ({pods_to_restart}). Max allowed is {self.MAX_PODS_AFFECTED}."
                
            # Rate limiting check
            now = time.time()
            self.recent_restarts = [t for t in self.recent_restarts if now - t < 60]
            if len(self.recent_restarts) >= self.MAX_RESTARTS_PER_MIN:
                return False, "REJECTED: Max restarts per minute (5) exceeded."
                
        elif action.type == "scale_deployment":
            current_replicas = action.metadata.get("current_replicas", 1)
            desired_replicas = action.metadata.get("desired_replicas", 1)
            
            # Prevent dramatic scaling spikes
            if desired_replicas > current_replicas * self.MAX_SCALE_MULTIPLIER:
                return False, f"REJECTED: Cannot scale beyond 2x current capacity (Requested: {desired_replicas}, Current: {current_replicas})."
                
        # Validated! Update variables for execution
        self.cooldown_tracker[action.signature] = time.time()
        if action.type == "restart_pod":
            for _ in range(action.metadata.get("pod_count", 1)):
                self.recent_restarts.append(time.time())
                
        self.action_history.append((action.signature, "ACCEPTED"))
        return True, "ACCEPTED by Policy Engine"

    def report_execution_result(self, success: bool):
        """Called by verifier to update the circuit breaker state."""
        if not success:
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self.circuit_breaker_tripped = True
                print("[CRITICAL ALERT] Circuit Breaker TRIPPED! All AI actions halted.")
        else:
            self.consecutive_failures = 0
