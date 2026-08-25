"""
Costs API — /api/costs
  GET /summary          - multi-cloud cost summary (current month)
  GET /breakdown        - per-service cost breakdown
  GET /history          - historical cost trend (N months)
  GET /anomalies        - detected cost anomalies
  GET /resources        - all cloud resources
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from cloud.collector import MultiCloudCollector
from database.models import User
from ml.anomaly_detection.isolation_forest import IsolationForestDetector
from ml.anomaly_detection.threshold_detection import ThresholdDetector

logger = logging.getLogger(__name__)
router = APIRouter()


def _collector() -> MultiCloudCollector:
    return MultiCloudCollector()


@router.get("/summary")
async def cost_summary(
    current_user: User = Depends(get_current_user),
):
    """Current month multi-cloud cost summary."""
    collector = _collector()
    now   = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    data  = await collector.get_all_costs(start, now)

    aws_total   = data["aws"]["total"]
    azure_total = data["azure"]["total"]
    gcp_total   = data["gcp"]["total"]
    total       = data["total"]

    from config.settings import settings
    budget = settings.DEFAULT_MONTHLY_BUDGET

    return {
        "aws_cost":             round(aws_total, 2),
        "azure_cost":           round(azure_total, 2),
        "gcp_cost":             round(gcp_total, 2),
        "total_cost":           round(total, 2),
        "monthly_budget":       budget,
        "budget_utilization_pct": round(total / budget * 100, 1),
        "currency":             "INR",
        "period":               start.strftime("%Y-%m"),
        "generated_at":         now.isoformat(),
    }


@router.get("/breakdown")
async def cost_breakdown(
    current_user: User = Depends(get_current_user),
    provider: Optional[str] = Query(None, description="Filter: aws | azure | gcp"),
):
    """Per-service cost breakdown."""
    collector = _collector()
    now   = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    data  = await collector.get_all_costs(start, now)

    result = {}
    providers = [provider] if provider else ["aws", "azure", "gcp"]
    for prov in providers:
        total = data[prov]["total"]
        breakdown = [
            {
                **item,
                "percentage": round(item["amount"] / max(total, 1) * 100, 1),
            }
            for item in data[prov]["breakdown"]
        ]
        result[prov] = {
            "total":     round(total, 2),
            "breakdown": sorted(breakdown, key=lambda x: x["amount"], reverse=True),
        }

    return result


@router.get("/history")
async def cost_history(
    months: int = Query(12, ge=1, le=24),
    current_user: User = Depends(get_current_user),
):
    """Monthly cost history for the past N months."""
    collector = _collector()
    history   = await collector.get_historical_costs(months=months)

    # Combine into unified timeline
    combined: dict = {}
    for provider in ["aws", "azure", "gcp"]:
        for entry in history.get(provider, []):
            key = entry["date"]
            if key not in combined:
                combined[key] = {"date": key, "aws": 0, "azure": 0, "gcp": 0}
            combined[key][provider] = round(entry["cost"], 2)

    timeline = sorted(combined.values(), key=lambda x: x["date"])
    for row in timeline:
        row["total"] = round(row["aws"] + row["azure"] + row["gcp"], 2)

    return {"history": timeline, "months": months}


@router.get("/anomalies")
async def cost_anomalies(
    current_user: User = Depends(get_current_user),
):
    """Detected cost anomalies across all providers."""
    collector = _collector()
    history   = await collector.get_historical_costs(months=12)

    from config.settings import settings
    threshold = ThresholdDetector()
    detector  = IsolationForestDetector(contamination=0.10)
    all_anomalies = []

    for provider in ["aws", "azure", "gcp"]:
        hist = history.get(provider, [])
        if not hist:
            continue
        values = [h["cost"] for h in hist]
        dates  = [h["date"] for h in hist]

        # Budget check
        current = values[-1] if values else 0
        prev    = values[-2] if len(values) >= 2 else current
        budget_a = threshold.detect_budget_breach(current, settings.DEFAULT_MONTHLY_BUDGET / 3, provider)
        if budget_a:
            all_anomalies.append(vars(budget_a))

        # Spike check
        spike_a = threshold.detect_cost_spike(provider, provider, prev, current)
        if spike_a:
            all_anomalies.append(vars(spike_a))

        # Statistical
        if len(values) >= 6:
            stat_a = detector.detect(provider, provider, dates, values, "monthly_cost")
            all_anomalies.extend([vars(a) for a in stat_a[:3]])

    return {
        "anomalies": all_anomalies,
        "count":     len(all_anomalies),
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/resources")
async def get_resources(
    current_user: User = Depends(get_current_user),
    provider: Optional[str] = Query(None),
):
    """All cloud resources across providers."""
    collector = _collector()
    resources = await collector.get_all_resources()

    if provider:
        return {provider: resources.get(provider, {})}
    return resources
