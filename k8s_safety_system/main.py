import time
from models import Action
from policy_engine import PolicyEngine
from action_executor import ActionExecutor
from verifier import Verifier
from rollback import RollbackSystem

def orchestrate():
    # Initialize Core Systems
    engine = PolicyEngine()
    executor = ActionExecutor()
    verifier = Verifier()
    rollbacker = RollbackSystem(executor)
    
    # ----------------------------------------------------
    # Simulation Scenarios
    # ----------------------------------------------------
    scenarios = [
        # Scenario 1: Safe Action
        Action(
            type="scale_deployment", 
            target="web-deployment",
            confidence=0.95,
            metadata={"current_replicas": 3, "desired_replicas": 5}
        ),
        
        # Scenario 2: Unsafe Action (Too low confidence)
        Action(
            type="restart_pod",
            target="db-pod-7xyz",
            confidence=0.5,
            metadata={"pod_count": 1}
        ),
        
        # Scenario 3: Unsafe Action (Scaling too high - exceeds 2.0x limit)
        Action(
            type="scale_deployment",
            target="cache-deployment",
            confidence=0.99,
            metadata={"current_replicas": 2, "desired_replicas": 10}
        ),
        
        # Scenario 4: AI hallucinated action (Not whitelisted)
        Action(
            type="delete_namespace",
            target="production",
            confidence=1.0
        ),
        
        # Scenario 5: Valid action but verification FAILS (Triggers Rollback)
        Action(
            type="rollback_deployment",
            target="db-deployment",
            confidence=0.90,
            metadata={"force_fail_verification": True} # Simulated failure
        )
    ]
    
    print("=" * 60)
    print("KUBERNETES AI AGENT SAFETY SYSTEM - MENTOR DEMO")
    print("=" * 60)
    
    for i, action in enumerate(scenarios, 1):
        print(f"\n[Scenario {i}] ------------------------------------------")
        print(f"AI INFERENCE: [Action: {action.type}] on [Target: {action.target}] (AI Confidence: {action.confidence})")
        
        # 1. Policy Validate
        is_safe, reason = engine.validate(action)
        if not is_safe:
            print(f"[DENIED] POLICY: {reason}")
            continue
            
        print(f"[APPROVED] POLICY: {reason}")
        
        # 2. Execute
        exec_success = executor.execute(action)
        if not exec_success:
            print("[FAILED] EXECUTION aborted internally.")
            continue
            
        # 3. Verify
        verify_success = verifier.verify_action(action)
        engine.report_execution_result(verify_success)
        
        # 4. Rollback if verification failed
        if verify_success:
            print("[SUCCESS] ACTION COMPLETED & VERIFIED SAFELY.")
        else:
            print("[WARNING] VERIFICATION FAILED. TRIGGERING IMMEDIATE CLUSTER ROLLBACK.")
            rollbacker.rollback(action)
            print("[RESTORED] RECOVERY SUCCESS: SYSTEM SAFELY RESTORED TO PREVIOUS STATE.")

if __name__ == "__main__":
    orchestrate()
