from core.ml.simulator.simulator import CounterfactualSimulator


class ScenarioEngine:
    """
    Manages execution of multi-scenario simulations and counterfactual scoring.
    """
    def __init__(self, models_dir: str = "models"):
        self.simulator = CounterfactualSimulator(models_dir)

    async def run_scenario(self, customer_id: str, actions: list[str], session) -> dict:
        """
        Runs a single what-if scenario with specified actions.
        """
        return await self.simulator.simulate(customer_id, actions, session)

    async def compare_scenarios(self, customer_id: str, scenarios: dict[str, list[str]], session) -> dict:
        """
        Runs and compares multiple named scenarios for a customer.
        Example scenarios: 
        {
          "mitigate_risk": ["decrease_credit_limit", "collection_campaign"],
          "extend_help": ["offer_extension", "promise_to_pay"]
        }
        """
        results = {}
        for name, actions in scenarios.items():
            results[name] = await self.simulator.simulate(customer_id, actions, session)
        return results
