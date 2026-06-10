import os
import yaml
from loguru import logger
from core.policy.models import EconiqPolicy

class PolicyManager:
    def __init__(self, config_path: str = "policy.yaml"):
        self.config_path = config_path
        self._policy = self.load_policy()

    def load_policy(self) -> EconiqPolicy:
        if not os.path.exists(self.config_path):
            logger.info(f"Policy configuration file '{self.config_path}' not found. Initializing with hardcoded platform defaults.")
            return EconiqPolicy()
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            policy = EconiqPolicy.model_validate(data)
            logger.info(f"Successfully loaded and validated policy parameters from '{self.config_path}'")
            return policy
        except Exception as e:
            logger.error(f"Error validating policy file '{self.config_path}', falling back to default values. Error: {e}")
            return EconiqPolicy()

    @property
    def policy(self) -> EconiqPolicy:
        return self._policy

    def reload(self):
        """Forces reload of policy configuration at runtime."""
        self._policy = self.load_policy()

# Global singleton policy instance
policy_manager = PolicyManager()
