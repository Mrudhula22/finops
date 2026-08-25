"""
AWS Cost Explorer adapter.
Fetches real billing data via boto3 Cost Explorer API.
Falls back to realistic mock data when credentials are absent.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from cloud.base import CostEntry

logger = logging.getLogger(__name__)

# INR conversion rate (1 USD ≈ 83 INR)
USD_TO_INR = 83.0


class AWSCostAdapter:
    """Wraps AWS Cost Explorer to retrieve cost data."""

    def __init__(self, access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 region: str = "us-east-1"):
        self.region = region
        self._client = None
        try:
            import boto3
            self._client = boto3.client(
                "ce",
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
        except Exception as exc:
            logger.warning("AWS boto3 not available or creds missing: %s", exc)

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_cost_summary(
        self, start_date: datetime, end_date: datetime
    ) -> List[CostEntry]:
        """Return per-service cost line items for the period."""
        if self._client is None:
            return self._mock_cost_summary(start_date, end_date)
        try:
            return await self._fetch_real_costs(start_date, end_date)
        except Exception as exc:
            logger.error("AWS Cost Explorer error: %s", exc)
            return self._mock_cost_summary(start_date, end_date)

    async def get_monthly_total(self, year: int, month: int) -> float:
        """Return total monthly cost in INR."""
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
        entries = await self.get_cost_summary(start, end)
        return sum(e.amount for e in entries)

    async def get_historical_costs(self, months: int = 12) -> List[Dict[str, Any]]:
        """Return last N months of cost totals for forecasting."""
        results = []
        now = datetime.utcnow()
        for i in range(months - 1, -1, -1):
            month_date = now - timedelta(days=30 * i)
            total = await self.get_monthly_total(month_date.year, month_date.month)
            results.append({
                "year": month_date.year,
                "month": month_date.month,
                "date": month_date.strftime("%Y-%m"),
                "cost": total,
                "provider": "aws",
            })
        return results

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fetch_real_costs(
        self, start_date: datetime, end_date: datetime
    ) -> List[CostEntry]:
        response = self._client.get_cost_and_usage(
            TimePeriod={
                "Start": start_date.strftime("%Y-%m-%d"),
                "End": end_date.strftime("%Y-%m-%d"),
            },
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        entries = []
        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                service = group["Keys"][0]
                amount_usd = float(group["Metrics"]["UnblendedCost"]["Amount"])
                entries.append(CostEntry(
                    provider="aws",
                    service=service,
                    amount=round(amount_usd * USD_TO_INR, 2),
                    period_start=start_date,
                    period_end=end_date,
                ))
        return entries

    def _mock_cost_summary(
        self, start_date: datetime, end_date: datetime
    ) -> List[CostEntry]:
        """Realistic mock data when real credentials are unavailable."""
        services = {
            "Amazon EC2":                    18500,
            "Amazon RDS":                     7200,
            "Amazon S3":                      3800,
            "AWS Lambda":                     1200,
            "Amazon CloudFront":              1500,
            "Amazon VPC":                      800,
            "AWS Data Transfer":               600,
            "Amazon Route 53":                 300,
        }
        return [
            CostEntry(
                provider="aws",
                service=svc,
                amount=amount,
                period_start=start_date,
                period_end=end_date,
            )
            for svc, amount in services.items()
        ]
