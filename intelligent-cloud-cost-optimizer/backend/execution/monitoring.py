"""
Post-execution monitoring.
After an optimization action executes, monitor key metrics for 30 minutes
and flag if performance degrades beyond thresholds.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Thresholds that trigger automatic rollback recommendation
ROLLBACK_TRIGGERS = {
    "cpu_utilization":    95.0,   # % — too high after downsize
    "memory_utilization": 90.0,   # %
    "error_rate":          5.0,   # %
    "response_time_ms":  2000.0,  # ms
}


class PostExecutionMonitor:
    """Monitors metrics after an optimization action and decides pass/rollback."""

    async def monitor(
        self,
        action_record: Dict[str, Any],
        duration_minutes: int = 30,
        check_interval_seconds: int = 60,
    ) -> Dict[str, Any]:
        resource_id = action_record.get("resource_id", "")
        provider    = action_record.get("provider", "aws")
        action_type = action_record.get("action_type", "")

        logger.info("[Monitor] Starting post-execution monitoring for %s (%s)", resource_id, action_type)

        checks: List[Dict[str, Any]] = []
        start  = datetime.utcnow()

        # In real deployment this would poll CloudWatch / Azure Monitor / GCP Monitoring
        # Here we simulate realistic outcomes
        for minute in range(1, min(duration_minutes // check_interval_seconds + 1, 6)):
            await asyncio.sleep(0)  # non-blocking in tests
            metrics = await self._fetch_metrics(provider, resource_id, minute)
            verdict = self._evaluate(metrics)
            checks.append({"minute": minute, "metrics": metrics, "verdict": verdict})
            if verdict == "rollback":
                logger.warning("[Monitor] Rollback trigger at minute %d for %s", minute, resource_id)
                break

        final_verdict = checks[-1]["verdict"] if checks else "pass"
        return {
            "resource_id":    resource_id,
            "action_type":    action_type,
            "monitoring_start": start.isoformat(),
            "checks":         checks,
            "final_verdict":  final_verdict,
            "recommendation": "rollback" if final_verdict == "rollback" else "keep",
            "summary":        self._summary(checks, final_verdict),
        }

    async def _fetch_metrics(self, provider: str, resource_id: str, minute: int) -> Dict:
        """Simulate realistic post-optimization metrics."""
        import random
        # Simulate slight CPU spike then stabilise after rightsizing
        cpu  = 45 + random.uniform(-5, 10) if minute <= 2 else 38 + random.uniform(-5, 5)
        mem  = 55 + random.uniform(-5, 8)
        err  = random.uniform(0, 0.5)
        resp = 180 + random.uniform(-20, 40)
        return {
            "cpu_utilization":    round(cpu, 1),
            "memory_utilization": round(mem, 1),
            "error_rate":         round(err, 2),
            "response_time_ms":   round(resp, 1),
            "timestamp":          datetime.utcnow().isoformat(),
        }

    def _evaluate(self, metrics: Dict) -> str:
        for key, threshold in ROLLBACK_TRIGGERS.items():
            if metrics.get(key, 0) > threshold:
                return "rollback"
        return "pass"

    @staticmethod
    def _summary(checks: List[Dict], verdict: str) -> str:
        if verdict == "rollback":
            return "Performance degradation detected. Rollback recommended."
        if checks:
            avg_cpu = sum(c["metrics"].get("cpu_utilization", 0) for c in checks) / len(checks)
            return f"All checks passed. Average CPU post-optimization: {avg_cpu:.1f}%."
        return "Monitoring completed without issues."
