from dataclasses import dataclass, field
from typing import Dict, Any
import time

@dataclass
class Action:
    type: str  # e.g., restart_pod, scale_deployment, rollback_deployment
    target: str # e.g., pod name or deployment name
    confidence: float # AI confidence score (0.0 to 1.0)
    metadata: Dict[str, Any] = field(default_factory=dict) # e.g., replicas, namespace
    timestamp: float = field(default_factory=time.time)
    
    @property
    def signature(self) -> str:
        """Unique signature to identify identical AI actions for cooldown tracking."""
        return f"{self.type}:{self.target}"
