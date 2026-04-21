from core.models import TokenStats, ProjectUsage, ModelUsage
from .calculator import CostCalculator, PRICING, DEFAULT_PRICING


class Analyzer:
    @staticmethod
    def cache_efficiency(stats: TokenStats) -> float:
        total = stats.total_cache_read + stats.total_input + stats.total_cache_write
        if total == 0:
            return 0.0
        return stats.total_cache_read / total * 100

    @staticmethod
    def project_breakdown(stats: TokenStats) -> list[ProjectUsage]:
        projects: dict[str, ProjectUsage] = {}
        for session in stats.sessions:
            proj = session.project
            if proj not in projects:
                projects[proj] = ProjectUsage(project=proj)
            pu = projects[proj]
            pu.sessions += 1
            for mu in session.model_stats.values():
                pu.total_tokens += mu.total_tokens
                pu.total_billable += mu.billable_tokens
        return sorted(projects.values(), key=lambda p: p.total_billable, reverse=True)

    @staticmethod
    def cache_savings_usd(stats: TokenStats) -> float:
        total_saved = 0.0
        for model, mu in stats.model_totals.items():
            pricing = PRICING.get(model, DEFAULT_PRICING)
            would_cost = mu.cache_read * pricing["input"] / 1_000_000
            actual_cost = mu.cache_read * pricing["cache_read"] / 1_000_000
            total_saved += would_cost - actual_cost
        return total_saved

    @staticmethod
    def model_comparison(stats: TokenStats) -> dict[str, float]:
        calc = CostCalculator()
        actual = calc.calculate_cost(stats).total_cost
        result: dict[str, float] = {"actual": actual}
        for model in ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"]:
            result[model] = calc.what_if_model(stats, model).total_cost
        return result
