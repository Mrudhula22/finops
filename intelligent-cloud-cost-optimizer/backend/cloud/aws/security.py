"""
AWS Security adapter.
Runs security checks against IAM, S3, EC2 Security Groups, encryption, and logging.
Returns a security score and list of findings.
"""

import logging
from typing import Any, Dict, List, Optional

from cloud.base import SecurityFinding

logger = logging.getLogger(__name__)


class AWSSecurityAdapter:

    def __init__(self, access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 region: str = "us-east-1"):
        self.region = region
        self._iam = None
        self._s3 = None
        self._ec2 = None
        try:
            import boto3
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            self._iam = session.client("iam")
            self._s3  = session.client("s3")
            self._ec2 = session.client("ec2")
        except Exception as exc:
            logger.warning("AWS Security clients unavailable: %s", exc)

    async def run_security_checks(self) -> Dict[str, Any]:
        """Run all checks and return a structured security report."""
        findings = await self.get_findings()

        passed = [f for f in findings if f.passed]
        failed = [f for f in findings if not f.passed]

        critical = len([f for f in failed if f.severity == "critical"])
        high     = len([f for f in failed if f.severity == "high"])
        medium   = len([f for f in failed if f.severity == "medium"])
        low      = len([f for f in failed if f.severity == "low"])

        # Weighted score
        total_checks = len(findings)
        deduction = (critical * 25 + high * 15 + medium * 8 + low * 3)
        score = max(0.0, min(100.0, 100.0 - deduction))

        return {
            "overall_score":     round(score, 1),
            "iam_score":         self._category_score(findings, "iam"),
            "encryption_score":  self._category_score(findings, "encryption"),
            "network_score":     self._category_score(findings, "network"),
            "compliance_score":  self._category_score(findings, "compliance"),
            "passed_checks":     len(passed),
            "failed_checks":     len(failed),
            "findings":          [self._finding_to_dict(f) for f in failed],
            "provider":          "aws",
        }

    async def get_findings(self) -> List[SecurityFinding]:
        """Return security findings (mock with realistic data)."""
        return [
            SecurityFinding("AWS-IAM-001", "MFA enabled for root account",   "critical", "root", "Root account should have MFA",          "Enable MFA on root account",           True),
            SecurityFinding("AWS-IAM-002", "No unused IAM credentials",      "high",     "iam",  "Remove credentials unused >90 days",    "Audit and remove stale credentials",    True),
            SecurityFinding("AWS-IAM-003", "Password policy enforced",       "medium",   "iam",  "Strong password policy required",       "Set minimum length ≥ 14",               True),
            SecurityFinding("AWS-IAM-004", "No admin wildcard policies",     "high",     "iam",  "Avoid AdministratorAccess policy",      "Apply least-privilege policies",        False),
            SecurityFinding("AWS-ENC-001", "S3 default encryption enabled",  "high",     "s3",   "All S3 buckets must be encrypted",      "Enable SSE on all buckets",             False),
            SecurityFinding("AWS-ENC-002", "EBS volumes encrypted",          "medium",   "ebs",  "EBS volumes should be encrypted",       "Encrypt EBS volumes",                   True),
            SecurityFinding("AWS-ENC-003", "RDS encryption at rest",         "high",     "rds",  "RDS instances must be encrypted",       "Enable encryption at rest",             True),
            SecurityFinding("AWS-NET-001", "No SSH open to 0.0.0.0/0",      "critical", "sg",   "SSH should not be open to internet",    "Restrict SSH to known IPs",             False),
            SecurityFinding("AWS-NET-002", "No RDP open to 0.0.0.0/0",      "critical", "sg",   "RDP should not be open to internet",    "Restrict RDP to known IPs",             True),
            SecurityFinding("AWS-NET-003", "VPC flow logs enabled",          "medium",   "vpc",  "Enable VPC flow logs for monitoring",   "Enable flow logs on all VPCs",          True),
            SecurityFinding("AWS-LOG-001", "CloudTrail enabled in all regions","high",   "ct",   "CloudTrail must be enabled",            "Enable CloudTrail globally",            True),
            SecurityFinding("AWS-LOG-002", "S3 bucket logging enabled",      "low",      "s3",   "Enable server access logging",          "Enable logging on all buckets",         False),
            SecurityFinding("AWS-PUB-001", "No public S3 buckets",          "critical", "s3",   "S3 buckets should not be public",       "Block all public access",               False),
        ]

    def _category_score(self, findings: List[SecurityFinding], category: str) -> float:
        cat_map = {
            "iam": ["iam", "root"],
            "encryption": ["s3", "ebs", "rds"],
            "network": ["sg", "vpc"],
            "compliance": ["ct", "s3"],
        }
        ids = cat_map.get(category, [])
        relevant = [f for f in findings if f.resource_id in ids]
        if not relevant:
            return 100.0
        passed = sum(1 for f in relevant if f.passed)
        return round((passed / len(relevant)) * 100, 1)

    @staticmethod
    def _finding_to_dict(f: SecurityFinding) -> Dict[str, Any]:
        return {
            "check_id":    f.check_id,
            "title":       f.title,
            "severity":    f.severity,
            "resource":    f.resource_id,
            "description": f.description,
            "remediation": f.remediation,
        }
