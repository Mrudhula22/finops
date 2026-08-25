"""
Multi-Cloud API — /api/multicloud
  GET  /compare         - compare providers for a workload
  GET  /compare/all     - compare all workload sizes
  GET  /security        - security scores for all providers
  GET  /pricing         - pricing comparison table
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from cloud.collector import MultiCloudCollector
from database.models import User
from optimization.multi_cloud_optimizer import MultiCloudOptimizer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/compare")
async def compare_providers(
    workload: str = Query("Web Application"),
    resource_type: str = Query("compute"),
    size: str = Query("medium", description="small | medium | large"),
    current_provider: str = Query("aws"),
    current_user: User = Depends(get_current_user),
):
    """Compare AWS, Azure, and GCP for a specific workload."""
    collector = MultiCloudCollector()
    security  = await collector.get_all_security()

    sec_scores = {
        prov: sec.get("overall_score", 80)
        for prov, sec in security.items()
    }

    optimizer = MultiCloudOptimizer()
    cmp = optimizer.compare_workload(
        workload=workload,
        resource_type=resource_type,
        size=size,
        current_provider=current_provider,
        security_scores=sec_scores,
    )

    return {
        "workload":         cmp.workload,
        "current_provider": cmp.current_provider,
        "current_cost":     cmp.current_cost,
        "best_provider":    cmp.best_provider,
        "best_cost":        cmp.best_cost,
        "saving_vs_current": cmp.saving_vs_current,
        "potential_saving": cmp.potential_saving,
        "recommendation":   cmp.recommendation_reason,
        "options": [
            {
                "provider":           o.provider,
                "service_name":       o.service_name,
                "configuration":      o.configuration,
                "monthly_cost":       o.monthly_cost,
                "performance_score":  o.performance_score,
                "security_score":     o.security_score,
                "availability_pct":   o.availability_pct,
                "compliance_score":   o.compliance_score,
                "total_score":        o.total_score,
            }
            for o in cmp.options
        ],
        "score_breakdown": cmp.score_breakdown,
        "generated_at":    datetime.utcnow().isoformat(),
    }


@router.get("/compare/all")
async def compare_all_workloads(
    current_user: User = Depends(get_current_user),
):
    """Compare all standard workload sizes across all providers."""
    collector = MultiCloudCollector()
    security  = await collector.get_all_security()
    resources = await collector.get_all_resources()

    sec_scores = {p: s.get("overall_score", 80) for p, s in security.items()}
    optimizer  = MultiCloudOptimizer()
    comparisons = optimizer.compare_all_workloads(resources, sec_scores)

    return {
        "comparisons": [
            {
                "workload":         c.workload,
                "best_provider":    c.best_provider,
                "best_cost":        c.best_cost,
                "saving_vs_aws":    c.saving_vs_current,
                "recommendation":   c.recommendation_reason,
            }
            for c in comparisons
        ],
        "total_potential_saving": sum(c.saving_vs_current for c in comparisons),
        "generated_at":           datetime.utcnow().isoformat(),
    }


@router.get("/security")
async def multi_cloud_security(
    current_user: User = Depends(get_current_user),
):
    """Security scores and findings for all providers."""
    collector = MultiCloudCollector()
    security  = await collector.get_all_security()

    result = {}
    for prov, report in security.items():
        result[prov] = {
            "overall_score":    report.get("overall_score", 0),
            "iam_score":        report.get("iam_score", 0),
            "encryption_score": report.get("encryption_score", 0),
            "network_score":    report.get("network_score", 0),
            "compliance_score": report.get("compliance_score", 0),
            "passed_checks":    report.get("passed_checks", 0),
            "failed_checks":    report.get("failed_checks", 0),
            "top_findings":     report.get("findings", [])[:5],
        }

    # Rank providers by security score
    ranked = sorted(result.items(), key=lambda x: x[1]["overall_score"], reverse=True)
    return {
        "scores":       result,
        "ranking":      [{"rank": i+1, "provider": p, "score": s["overall_score"]}
                         for i, (p, s) in enumerate(ranked)],
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/pricing")
async def pricing_comparison(
    resource_type: str = Query("compute"),
    current_user: User = Depends(get_current_user),
):
    """Side-by-side pricing table for equivalent services across providers."""
    from optimization.multi_cloud_optimizer import COMPUTE_PRICING, STORAGE_PRICING

    if resource_type == "compute":
        table = []
        for size, prices in COMPUTE_PRICING.items():
            table.append({
                "size":  size,
                "aws":   prices["aws"],
                "azure": prices["azure"],
                "gcp":   prices["gcp"],
                "cheapest": min(prices, key=prices.get),
                "aws_vs_cheapest_saving": prices["aws"] - min(prices.values()),
            })
        return {"resource_type": "compute", "currency": "INR/month", "pricing": table}

    if resource_type == "storage":
        table = []
        for tier, prices in STORAGE_PRICING.items():
            table.append({
                "tier":  tier,
                "aws":   prices["aws"],
                "azure": prices["azure"],
                "gcp":   prices["gcp"],
                "unit":  "INR/GB/month",
                "cheapest": min(prices, key=prices.get),
            })
        return {"resource_type": "storage", "currency": "INR/GB/month", "pricing": table}

    return {"error": "Unsupported resource_type. Use: compute | storage"}
