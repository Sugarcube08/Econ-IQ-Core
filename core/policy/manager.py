import os

import yaml

from core.observability.failure_registry import FailureRegistry
from core.policy.models import EconiqPolicy


class PolicyManager:
    def __init__(self, config_path: str = "policy.yaml"):
        self.config_path = config_path
        self._policy = self.load_policy()

    def load_policy(self) -> EconiqPolicy:
        if not os.path.exists(self.config_path):
            return EconiqPolicy()
        
        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            policy = EconiqPolicy.model_validate(data)
            FailureRegistry.recover("POLICY_VALIDATION_FAILED")
            return policy
        except Exception as e:
            FailureRegistry.record("POLICY_VALIDATION_FAILED", f"Error validating policy file '{self.config_path}', falling back to default values. Error: {e}", "ERROR")
            return EconiqPolicy()

    @property
    def policy(self) -> EconiqPolicy:
        return self._policy

    def reload(self):
        """Forces reload of policy configuration at runtime."""
        self._policy = self.load_policy()

# Global singleton policy instance
policy_manager = PolicyManager()
