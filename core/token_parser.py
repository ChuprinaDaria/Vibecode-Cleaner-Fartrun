try:
    import orjson as _json

    def _loads(s):
        return _json.loads(s)
except ImportError:
    import json as _json

    def _loads(s):
        return _json.loads(s)

import glob
import os
from datetime import datetime, timedelta
from .models import ModelUsage, SessionStats, TokenStats


class TokenParser:
    def __init__(self, claude_dir: str | None = None):
        self.claude_dir = claude_dir or os.path.expanduser("~/.claude")

    def get_subscription(self) -> dict:
        """Detect Claude subscription type from credentials."""
        creds_file = os.path.join(self.claude_dir, ".credentials.json")
        result = {"type": "unknown", "tier": "unknown", "is_paid_tokens": False}
        if not os.path.exists(creds_file):
            return result
        try:
            with open(creds_file, "rb") as f:
                data = _loads(f.read())
            oauth = data.get("claudeAiOauth", {})
            sub_type = oauth.get("subscriptionType", "free")
            rate_tier = oauth.get("rateLimitTier", "")
            result["type"] = sub_type  # free, pro, max, team
            result["tier"] = rate_tier
            # Pro/Max/Team subscriptions pay monthly fee, not per-token
            # API keys pay per-token
            result["is_paid_tokens"] = "apiKey" in data
        except (ValueError, OSError):
            pass
        return result

    def _get_sessions_for_date(self, target_date: str) -> dict[str, str]:
        history_file = os.path.join(self.claude_dir, "history.jsonl")
        if not os.path.exists(history_file):
            return {}

        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        day_start_ms = int(target_dt.replace(hour=0, minute=0, second=0).timestamp() * 1000)
        day_end_ms = int(target_dt.replace(hour=23, minute=59, second=59).timestamp() * 1000)

        sessions: dict[str, str] = {}
        with open(history_file, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    entry = _loads(line.strip())
                    ts = entry.get("timestamp", 0)
                    if day_start_ms <= ts <= day_end_ms:
                        sid = entry.get("sessionId", "")
                        proj = entry.get("project", "")
                        if sid:
                            sessions[sid] = proj
                except (ValueError, KeyError):
                    continue
        return sessions

    def _parse_session_jsonl(self, jsonl_path: str) -> dict[str, ModelUsage]:
        model_stats: dict[str, ModelUsage] = {}
        try:
            with open(jsonl_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        entry = _loads(line.strip())
                        if entry.get("type") != "assistant":
                            continue
                        msg = entry.get("message", {})
                        if not isinstance(msg, dict):
                            continue
                        usage = msg.get("usage", {})
                        model = msg.get("model", "unknown")

                        if model not in model_stats:
                            model_stats[model] = ModelUsage()
                        mu = model_stats[model]
                        mu.input += usage.get("input_tokens", 0)
                        mu.output += usage.get("output_tokens", 0)
                        mu.cache_read += usage.get("cache_read_input_tokens", 0)
                        mu.cache_write += usage.get("cache_creation_input_tokens", 0)
                        mu.calls += 1
                    except (ValueError, KeyError):
                        continue
        except OSError:
            pass
        return model_stats

    def _extract_project_name(self, dir_name: str) -> str:
        parts = dir_name.strip("-").split("-")
        return parts[-1] if parts else dir_name

    def parse_date(self, target_date: str) -> TokenStats:
        sessions_map = self._get_sessions_for_date(target_date)
        projects_dir = os.path.join(self.claude_dir, "projects")

        sessions: list[SessionStats] = []
        model_totals: dict[str, ModelUsage] = {}
        total_input = total_output = total_cache_read = total_cache_write = 0

        for jsonl_path in glob.glob(os.path.join(projects_dir, "*", "*.jsonl")):
            basename = os.path.basename(jsonl_path).replace(".jsonl", "")
            if basename not in sessions_map:
                continue

            dir_name = os.path.basename(os.path.dirname(jsonl_path))
            project_name = self._extract_project_name(dir_name)
            model_stats = self._parse_session_jsonl(jsonl_path)

            if not model_stats:
                continue

            sessions.append(SessionStats(
                session_id=basename, project=project_name, model_stats=model_stats,
            ))

            for model, mu in model_stats.items():
                total_input += mu.input
                total_output += mu.output
                total_cache_read += mu.cache_read
                total_cache_write += mu.cache_write

                if model not in model_totals:
                    model_totals[model] = ModelUsage()
                mt = model_totals[model]
                mt.input += mu.input
                mt.output += mu.output
                mt.cache_read += mu.cache_read
                mt.cache_write += mu.cache_write
                mt.calls += mu.calls

        return TokenStats(
            date=target_date, sessions=sessions,
            total_input=total_input, total_output=total_output,
            total_cache_read=total_cache_read, total_cache_write=total_cache_write,
            total_billable=total_input + total_output + total_cache_write,
            model_totals=model_totals,
        )

    def parse_today(self) -> TokenStats:
        return self.parse_date(datetime.now().strftime("%Y-%m-%d"))

    def parse_range(self, days: int = 14) -> list[TokenStats]:
        result = []
        today = datetime.now()
        for i in range(days):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            result.append(self.parse_date(d))
        result.reverse()
        return result
