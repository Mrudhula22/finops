"""
Multi-Cloud Optimizer.
Compares AWS, Azure, and GCP for equivalent workloads across five dimensions:
  Cost · Performance · Security · Availability · Compliance
Selects the best provider using a weighted scoring model.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Scoring weights
WEIGHTS = {
    "cost":         0.40,
    "performance":  0.20,
    "security":     0.20,
    "availability": 0.10,
    "compliance":   0.10,
}


@dataclass
class ProviderOption:
    provider:          str
    service_name:      str
    configuration:     str
    monthly_cost:      float          # INR
    performance_score: float          # 0-100
    security_score:    float          # 0-100
    availability_pct:  float          # e.g. 99.99
    data_transfer_cost: float         # INR/month
    compliance_score:  float          # 0-100
    total_score:       float = 0.0


@dataclass
class MultiCloudComparison:
    workload:              str
    options:               List[ProviderOption]
    best_provider:         str
    best_cost:             float
    potential_saving:      float
    saving_vs_current:     float
    current_provider:      str
    current_cost:          float
    recommendation_reason: str
    score_breakdown:       Dict[str, Dict[str, float]] = field(default_factory=dict)


# ── Pricing catalogue (INR/month, realistic estimates) ──────────────────────
COMPUTE_PRICING = {
    "small":  {"aws": 5040,  "azure": 4400,  "gcp": 3920},   # 2vCPU 4GB
    "medium": {"aws": 10159, "azure": 8970,  "gcp": 7885},   # 4vCPU 8GB
    "large":  {"aws": 20318, "azure": 17940, "gcp": 15769},  # 8vCPU 16GB
}
STORAGE_PRICING = {
    "standard": {"aws": 1.9,  "azure": 1.5,  "gcp": 1.66},   # INR per GB
    "archive":  {"aws": 0.33, "azure": 0.33, "gcp": 0.40},
}
AVAILABILITY = {
    "aws":   {"compute": 99.99, "storage": 99.999, "database": 99.95},
    "azure": {"compute": 99.99, "storage": 99.999, "database": 99.99},
    "gcp":   {"compute": 99.99, "storage": 99.999, "database": 99.95},
}
COMPLIANCE = {
    "aws":   {"soc2": True, "iso27001": True, "hipaa": True,  "pci": True,  "gdpr": True},
    "azure": {"soc2": True, "iso27001": True, "hipaa": True,  "pci": True,  "gdpr": True},
    "gcp":   {"soc2": True, "iso27001": True, "hipaa": True,  "pci": True,  "gdpr": True},
}


class MultiCloudOptimizer:
    """Selects the best cloud provider for a given workload."""

    def compare_workload(
        self,
        workload: str,
        resource_type: str,
        size: str,
        current_provider: str,
        security_scores: Optional[Dict[str, float]] = None,
        required_compliance: Optional[List[str]] = None,
    ) -> MultiCloudComparison:
        security_scores     = security_scores or {"aws": 82, "azure": 85, "gcp": 88}
        required_compliance = required_compliance or []

        options: List[ProviderOption] = []
        for prov in ["aws", "azure", "gcp"]:
            opt = self._build_option(
                provider=prov,
                resource_type=resource_type,
                size=size,
                security_score=security_scores.get(prov, 80),
                required_compliance=required_compliance,
            )
            options.append(opt)

        # Score each option
        options = self._score_options(options, required_compliance)
        best   = max(options, key=lambda o: o.total_score)
        worst  = max(options, key=lambda o: o.monthly_cost)  # most expensive

        current_opt = next((o for o in options if o.provider == current_provider), options[0])
        saving_vs_current = max(0, current_opt.monthly_cost - best.monthly_cost)
        potential_saving  = max(0, worst.monthly_cost - best.monthly_cost)

        score_breakdown = {
            o.provider: {
                "cost_score":         self._cost_score(o.monthly_cost, [x.monthly_cost for x in options]),
                "performance_score":  o.performance_score,
                "security_score":     o.security_score,
                "availability_score": (o.availability_pct - 99.0) * 100,
                "compliance_score":   o.compliance_score,
                "total_score":        o.total_score,
            }
            for o in options
        }

        reason = self._build_reason(best, current_opt, saving_vs_current)

        return MultiCloudComparison(
            workload=workload,
            options=options,
            best_provider=best.provider,
            best_cost=best.monthly_cost,
            potential_saving=round(potential_saving, 2),
            saving_vs_current=round(saving_vs_current, 2),
            current_provider=current_provider,
            current_cost=current_opt.monthly_cost,
            recommendation_reason=reason,
            score_breakdown=score_breakdown,
        )

    def compare_all_workloads(
        self,
        resources: Dict[str, Any],
        security_scores: Optional[Dict[str, float]] = None,
    ) -> List[MultiCloudComparison]:
        comparisons = []
        sizes = ["small", "medium", "large"]
        for i, size in enumerate(sizes):
            cmp = self.compare_workload(
                workload=f"Workload {i+1} ({size})",
                resource_type="compute",
                size=size,
                current_provider="aws",
                security_scores=security_scores,
            )
            comparisons.append(cmp)
        return comparisons

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_option(
        self,
        provider: str,
        resource_type: str,
        size: str,
        security_score: float,
        required_compliance: List[str],
    ) -> ProviderOption:
        pricing = COMPUTE_PRICING.get(size, COMPUTE_PRICING["medium"])
        cost    = pricing.get(provider, 10000)
        avail   = AVAILABILITY.get(provider, {}).get(resource_type, 99.9)
        compl   = COMPLIANCE.get(provider, {})
        compl_score = self._compliance_score(compl, required_compliance)

        # Performance: GCP slightly higher for compute-intensive workloads
        perf_base = {"aws": 82, "azure": 80, "gcp": 85}
        perf      = perf_base.get(provider, 80)

        return ProviderOption(
            provider=provider,
            service_name=self._service_name(provider, resource_type),
            configuration=f"{size} ({resource_type})",
            monthly_cost=float(cost),
            performance_score=float(perf),
            security_score=float(security_score),
            availability_pct=float(avail),
            data_transfer_cost=float(cost * 0.05),
            compliance_score=float(compl_score),
        )

    def _score_options(
        self, options: List[ProviderOption], required_compliance: List[str]
    ) -> List[ProviderOption]:
        costs = [o.monthly_cost for o in options]
        for o in options:
            cost_score = self._cost_score(o.monthly_cost, costs)
            avail_score = (o.availability_pct - 99.0) * 100   # 99.0=0, 99.99=99
            o.total_score = round(
                cost_score        * WEIGHTS["cost"]        +
                o.performance_score * WEIGHTS["performance"] +
                o.security_score   * WEIGHTS["security"]    +
                avail_score        * WEIGHTS["availability"] +
                o.compliance_score * WEIGHTS["compliance"],
                2,
            )
        return options

    @staticmethod
    def _cost_score(cost: float, all_costs: List[float]) -> float:
        """Higher score = lower cost (inverted normalised)."""
        min_c = min(all_costs)
        max_c = max(all_costs)
        if max_c == min_c:
            return 100.0
        return round((max_c - cost) / (max_c - min_c) * 100, 1)

    @staticmethod
    def _compliance_score(compl: Dict, required: List[str]) -> float:
        if not required:
            return 100.0
        passed = sum(1 for r in required if compl.get(r.lower(), False))
        return round(passed / len(required) * 100, 1)

    @staticmethod
    def _service_name(provider: str, resource_type: str) -> str:
        names = {
            "aws":   {"compute": "EC2", "storage": "S3", "database": "RDS"},
            "azure": {"compute": "Virtual Machines", "storage": "Blob Storage", "database": "Azure SQL"},
            "gcp":   {"compute": "Compute Engine", "storage": "Cloud Storage", "database": "Cloud SQL"},
        }
        return names.get(provider, {}).get(resource_type, resource_type.title())

    @staticmethod
    def _build_reason(
        best: ProviderOption, current: ProviderOption, saving: float
    ) -> str:
        if best.provider == current.provider:
            return f"Current provider {current.provider.upper()} is already optimal for this workload."
        return (
            f"{best.provider.upper()} offers the best overall score ({best.total_score:.0f}/100) "
            f"with monthly cost ₹{best.monthly_cost:,.0f} vs current ₹{current.monthly_cost:,.0f} "
            f"on {current.provider.upper()}. "
            f"Potential saving: ₹{saving:,.0f}/month."
        )
