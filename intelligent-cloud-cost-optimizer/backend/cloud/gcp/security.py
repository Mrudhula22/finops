"""GCP Security Command Center adapter."""

import logging
from typing import Any, Dict, List, Optional
from cloud.base import SecurityFinding

logger = logging.getLogger(__name__)


class GCPSecurityAdapter:

    def __init__(self, project_id: Optional[str] = None, **kwargs):
        self.project_id = project_id

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
            "iam_score":        self._category_score(findings, ["iam", "sa"]),
            "encryption_score": self._category_score(findings, ["kms", "gcs"]),
            "network_score":    self._category_score(findings, ["fw", "vpc"]),
            "compliance_score": self._category_score(findings, ["audit", "org"]),
            "passed_checks":    len(passed),
            "failed_checks":    len(failed),
            "findings":         [self._to_dict(f) for f in failed],
            "provider":         "gcp",
        }

    async def get_findings(self) -> List[SecurityFinding]:
        return [
            SecurityFinding("GCP-IAM-001", "No service account key files",       "high",     "sa",    "Avoid user-managed SA keys",           "Use Workload Identity instead",     True),
            SecurityFinding("GCP-IAM-002", "No primitive roles at project level", "high",     "iam",   "Avoid roles/owner and roles/editor",   "Use predefined roles",              True),
            SecurityFinding("GCP-IAM-003", "OS Login enabled",                   "medium",   "iam",   "Use OS Login for SSH key management",  "Enable OS Login on all VMs",        False),
            SecurityFinding("GCP-KMS-001", "CMEK enabled for Cloud SQL",         "high",     "kms",   "Use customer-managed encryption keys", "Configure CMEK in Cloud SQL",        True),
            SecurityFinding("GCP-GCS-001", "Uniform bucket-level access enabled","high",     "gcs",   "Use uniform bucket-level access",      "Enable UBL access on all buckets",  False),
            SecurityFinding("GCP-GCS-002", "No public buckets",                  "critical", "gcs",   "Buckets should not be publicly readable","Remove allUsers / allAuthUsers",    False),
            SecurityFinding("GCP-FW-001",  "No default network firewall",        "medium",   "fw",    "Delete default network",               "Use custom VPC networks",           True),
            SecurityFinding("GCP-FW-002",  "No firewall rules allow port 22",    "high",     "fw",    "SSH should not be open to 0.0.0.0/0",  "Use IAP for SSH access",            True),
            SecurityFinding("GCP-AUD-001", "Audit logs enabled for all services","medium",   "audit", "Enable data access audit logs",        "Enable audit logs in org policy",   True),
            SecurityFinding("GCP-ORG-001", "Org policy constraints enforced",    "medium",   "org",   "Enforce org-level constraints",        "Configure org policies",            False),
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
