"""Azure Security Center adapter."""

import logging
from typing import Any, Dict, List, Optional
from cloud.base import SecurityFinding

logger = logging.getLogger(__name__)


class AzureSecurityAdapter:

    def __init__(self, subscription_id: Optional[str] = None, **kwargs):
        self.subscription_id = subscription_id

    async def run_security_checks(self) -> Dict[str, Any]:
        findings = await self.get_findings()
        passed = [f for f in findings if f.passed]
        failed = [f for f in findings if not f.passed]
        critical = len([f for f in failed if f.severity == "critical"])
        high     = len([f for f in failed if f.severity == "high"])
        medium   = len([f for f in failed if f.severity == "medium"])
        low      = len([f for f in failed if f.severity == "low"])
        deduction = critical * 25 + high * 15 + medium * 8 + low * 3
        score = max(0.0, min(100.0, 100.0 - deduction))
        return {
            "overall_score":    round(score, 1),
            "iam_score":        self._category_score(findings, ["rbac", "mfa"]),
            "encryption_score": self._category_score(findings, ["disk", "storage"]),
            "network_score":    self._category_score(findings, ["nsg", "fw"]),
            "compliance_score": self._category_score(findings, ["policy"]),
            "passed_checks":    len(passed),
            "failed_checks":    len(failed),
            "findings":         [self._to_dict(f) for f in failed],
            "provider":         "azure",
        }

    async def get_findings(self) -> List[SecurityFinding]:
        return [
            SecurityFinding("AZ-RBAC-001", "MFA enforced for all users",           "critical", "mfa",     "MFA should be enabled",               "Enable MFA in Azure AD",          True),
            SecurityFinding("AZ-RBAC-002", "No subscription owner service principals","high",  "rbac",    "Avoid broad owner assignments",       "Use least-privilege roles",        True),
            SecurityFinding("AZ-RBAC-003", "Guest user access reviewed",            "medium",  "rbac",    "Review guest user permissions",       "Remove unnecessary guest access",  False),
            SecurityFinding("AZ-ENC-001",  "Disk encryption enabled",               "high",    "disk",    "All disks should be encrypted",       "Enable Azure Disk Encryption",     True),
            SecurityFinding("AZ-ENC-002",  "Storage accounts HTTPS only",           "high",    "storage", "Enforce HTTPS on storage accounts",   "Disable HTTP access",              False),
            SecurityFinding("AZ-NET-001",  "NSG rules reviewed",                    "high",    "nsg",     "Remove overly permissive NSG rules",  "Audit and tighten NSG rules",      True),
            SecurityFinding("AZ-NET-002",  "Azure Firewall enabled",                "medium",  "fw",      "Use Azure Firewall for central control","Deploy Azure Firewall",           False),
            SecurityFinding("AZ-POL-001",  "Azure Policy assignments active",       "medium",  "policy",  "Enforce governance with Azure Policy","Assign relevant policies",         True),
            SecurityFinding("AZ-LOG-001",  "Diagnostic logs enabled",               "medium",  "log",     "Enable diagnostic logging",           "Enable for all resources",         True),
        ]

    def _category_score(self, findings, resource_ids):
        relevant = [f for f in findings if f.resource_id in resource_ids]
        if not relevant:
            return 100.0
        return round(sum(1 for f in relevant if f.passed) / len(relevant) * 100, 1)

    @staticmethod
    def _to_dict(f: SecurityFinding) -> Dict[str, Any]:
        return {"check_id": f.check_id, "title": f.title, "severity": f.severity,
                "resource": f.resource_id, "description": f.description, "remediation": f.remediation}
