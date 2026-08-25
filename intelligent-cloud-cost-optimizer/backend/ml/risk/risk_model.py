"""
Risk Scoring Model.
Produces a composite risk score (0-100) for any optimization recommendation.
Considers performance, availability, security, and migration risks.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    recommendation_id: str
    overall_score: float          # 0-100 (higher = riskier)
    risk_level: str               # low | medium | high | critical
    performance_risk: float
    availability_risk: float
    security_risk: float
    migration_risk: float
    factors: List[str] = field(default_factory=list)
    mitigation: List[str] = field(default_factory=list)


class RiskModel:
    """
    Composite risk scorer for cloud optimization recommendations.
    Weights:
        performance  30%
        availability 25%
        security     25%
        migration    20%
    """

    WEIGHTS = {
        "performance":  0.30,
        "availability": 0.25,
        "security":     0.25,
        "migration":    0.20,
    }

    def assess(self, recommendation: Dict[str, Any]) -> RiskAssessment:
        """
        Assess risk for a recommendation.
        recommendation keys:
            recommendation_id, current_provider, recommended_provider,
            saving_percentage, resource_type, workload_criticality,
            security_score, current_cpu, current_memory, downtime_tolerance,
            data_size_gb, has_dependencies, is_stateful
        """
        rec_id = recommendation.get("recommendation_id", "unknown")

        perf_score   = self._performance_risk(recommendation)
        avail_score  = self._availability_risk(recommendation)
        sec_score    = self._security_risk(recommendation)
        mig_score    = self._migration_risk(recommendation)

        overall = (
            perf_score   * self.WEIGHTS["performance"] +
            avail_score  * self.WEIGHTS["availability"] +
            sec_score    * self.WEIGHTS["security"] +
            mig_score    * self.WEIGHTS["migration"]
        )
        overall = round(min(100.0, max(0.0, overall)), 1)

        factors    = self._identify_risk_factors(recommendation, perf_score, avail_score, sec_score, mig_score)
        mitigation = self._generate_mitigation(factors)
        risk_level = self._risk_level(overall)

        logger.info("Risk assessment %s: overall=%.1f (%s)", rec_id, overall, risk_level)

        return RiskAssessment(
            recommendation_id=rec_id,
            overall_score=overall,
            risk_level=risk_level,
            performance_risk=round(perf_score, 1),
            availability_risk=round(avail_score, 1),
            security_risk=round(sec_score, 1),
            migration_risk=round(mig_score, 1),
            factors=factors,
            mitigation=mitigation,
        )

    # ── Risk sub-scorers ─────────────────────────────────────────────────────

    def _performance_risk(self, rec: Dict[str, Any]) -> float:
        score = 10.0  # base

        # Downsizing risk
        saving_pct = rec.get("saving_percentage", 0)
        if saving_pct > 50:  score += 30
        elif saving_pct > 30: score += 15
        elif saving_pct > 20: score += 8

        # Current utilization
        cpu = rec.get("current_cpu", 50)
        mem = rec.get("current_memory", 50)
        if cpu > 80 or mem > 80:  score += 25
        elif cpu > 60 or mem > 60: score += 12

        # Criticality
        criticality = rec.get("workload_criticality", "medium").lower()
        if criticality == "critical":  score += 20
        elif criticality == "high":    score += 10

        return min(100, score)

    def _availability_risk(self, rec: Dict[str, Any]) -> float:
        score = 5.0

        # Cross-provider migration has higher availability risk
        current  = rec.get("current_provider", "")
        proposed = rec.get("recommended_provider", "")
        if current and proposed and current != proposed:
            score += 30

        downtime_tolerance = rec.get("downtime_tolerance", "hours").lower()
        if downtime_tolerance == "zero":    score += 35
        elif downtime_tolerance == "minutes": score += 20
        elif downtime_tolerance == "hours":   score += 8

        # Stateful workloads harder to move
        if rec.get("is_stateful", False):
            score += 15

        return min(100, score)

    def _security_risk(self, rec: Dict[str, Any]) -> float:
        security_score = rec.get("security_score", 80)
        # Invert: low security score = high security risk
        score = max(0, 100 - security_score)

        # Public resource risk
        if rec.get("has_public_access", False):
            score += 20

        return min(100, score)

    def _migration_risk(self, rec: Dict[str, Any]) -> float:
        score = 5.0

        # Data migration effort
        data_gb = rec.get("data_size_gb", 0)
        if data_gb > 1000:   score += 30
        elif data_gb > 100:  score += 15
        elif data_gb > 10:   score += 5

        # Dependencies
        if rec.get("has_dependencies", False):
            score += 20

        # Same vs cross-provider
        current  = rec.get("current_provider", "")
        proposed = rec.get("recommended_provider", "")
        if current and proposed and current != proposed:
            score += 25

        return min(100, score)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _identify_risk_factors(
        self, rec, perf, avail, sec, mig
    ) -> List[str]:
        factors = []
        if perf > 50:
            factors.append(f"High performance risk (score={perf:.0f}/100) — workload may be performance-sensitive")
        if avail > 50:
            factors.append(f"High availability risk (score={avail:.0f}/100) — migration may cause downtime")
        if sec > 50:
            factors.append(f"Security concerns (score={sec:.0f}/100) — review target environment security posture")
        if mig > 50:
            factors.append(f"Complex migration (score={mig:.0f}/100) — data or dependencies involved")
        if rec.get("is_stateful"):
            factors.append("Stateful workload — requires careful data migration planning")
        if rec.get("has_dependencies"):
            factors.append("Resource has dependencies — ensure all dependent services are migrated together")
        if not factors:
            factors.append("Low overall risk — optimization is safe to proceed")
        return factors

    @staticmethod
    def _generate_mitigation(factors: List[str]) -> List[str]:
        mitigation = []
        if any("performance" in f for f in factors):
            mitigation.append("Run load tests on the target configuration before full migration")
        if any("availability" in f for f in factors):
            mitigation.append("Use blue-green deployment to ensure zero-downtime migration")
        if any("security" in f for f in factors):
            mitigation.append("Run security assessment on target environment before migration")
        if any("migration" in f for f in factors):
            mitigation.append("Use phased migration — start with non-critical workloads first")
        if any("stateful" in f for f in factors):
            mitigation.append("Create full snapshot/backup before starting migration")
        if any("dependencies" in f for f in factors):
            mitigation.append("Map all dependencies and migrate in correct order")
        if not mitigation:
            mitigation.append("Standard deployment procedure applies — no special precautions needed")
        return mitigation

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 70:  return "critical"
        if score >= 50:  return "high"
        if score >= 25:  return "medium"
        return "low"
