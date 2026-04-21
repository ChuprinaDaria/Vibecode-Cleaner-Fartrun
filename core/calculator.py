from core.models import TokenStats, ModelUsage, CostBreakdown

PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6":   {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
    "claude-opus-4-5":   {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4":   {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5":  {"input": 1.00, "output": 5.00,  "cache_read": 0.10, "cache_write": 1.25},
    "claude-haiku-3-5":  {"input": 0.80, "output": 4.00,  "cache_read": 0.08, "cache_write": 1.00},
}
DEFAULT_PRICING = {"input": 5.00, "output": 25.00, "cache_read": 0.50, "cache_write": 6.25}


class CostCalculator:
    def _get_pricing(self, model: str) -> dict[str, float]:
        return PRICING.get(model, DEFAULT_PRICING)

    def _cost_for_usage(self, mu: ModelUsage, pricing: dict[str, float]) -> CostBreakdown:
        m = 1_000_000
        ic = mu.input * pricing["input"] / m
        oc = mu.output * pricing["output"] / m
        crc = mu.cache_read * pricing["cache_read"] / m
        cwc = mu.cache_write * pricing["cache_write"] / m
        return CostBreakdown(
            input_cost=ic, output_cost=oc,
            cache_read_cost=crc, cache_write_cost=cwc,
            total_cost=ic + oc + crc + cwc,
        )

    def calculate_cost(self, stats: TokenStats) -> CostBreakdown:
        total = CostBreakdown()
        for model, mu in stats.model_totals.items():
            cb = self._cost_for_usage(mu, self._get_pricing(model))
            total.input_cost += cb.input_cost
            total.output_cost += cb.output_cost
            total.cache_read_cost += cb.cache_read_cost
            total.cache_write_cost += cb.cache_write_cost
            total.total_cost += cb.total_cost
        return total

    def what_if_model(self, stats: TokenStats, target_model: str) -> CostBreakdown:
        pricing = self._get_pricing(target_model)
        combined = ModelUsage()
        for mu in stats.model_totals.values():
            combined.input += mu.input
            combined.output += mu.output
            combined.cache_read += mu.cache_read
            combined.cache_write += mu.cache_write
            combined.calls += mu.calls
        return self._cost_for_usage(combined, pricing)

