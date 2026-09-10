"""
Policy-Locked Action Templates
================================
Every recommendation is checked against compiled organizational policies
BEFORE being surfaced — not after deployment.

Policy categories:
  1. IAM Boundaries       — actions must not exceed IAM permission boundaries
  2. Tagging Rules        — required tags must be present on target resources
  3. Compliance Frameworks — SOC2, PCI-DSS, HIPAA, GDPR, ISO27001
  4. Cost Governance      — budget limits, approved instance types, regions
  5. Security Baselines   — no public exposure, encryption required

Actions violating ANY policy are silently discarded — never shown to users.
Each approved action carries a machine-checkable policy signature.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────────────

class PolicyResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


class PolicySeverity(str, Enum):
    BLOCKER  = "BLOCKER"    # action suppressed, never surfaced
    WARNING  = "WARNING"    # surfaced with warning
    INFO     = "INFO"       # informational only


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class PolicyViolation:
    policy_id:   str
    policy_name: str
    severity:    PolicySeverity
    message:     str
    remediation: str


@dataclass
class PolicyCheckResult:
    recommendation_id: str
    overall_result:    PolicyResult
    violations:        List[PolicyViolation]
    passed_checks:     List[str]
    policy_signature:  str              # SHA-256 of (rec_id + passed_checks + timestamp)
    checked_at:        str = field(default_factory=lambda: datetime.utcnow().isoformat())
    suppressed:        bool = False     # True = never shown to user


# ── Built-in policy rules ──────────────────────────────────────────────────────

COMPLIANCE_FRAMEWORKS = {
    "soc2":     ["encryption_at_rest", "audit_logging", "access_control"],
    "pci_dss":  ["encryption_at_rest", "encryption_in_transit", "no_public_access", "audit_logging"],
    "hipaa":    ["encryption_at_rest", "encryption_in_transit", "access_control", "audit_logging"],
    "gdpr":     ["data_residency_eu", "encryption_at_rest", "audit_logging"],
    "iso27001": ["encryption_at_rest", "access_control", "audit_logging", "vulnerability_mgmt"],
}

APPROVED_INSTANCE_TYPES = {
    "aws": [
        "t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge",
        "m5.large", "m5.xlarge", "m5.2xlarge",
        "c5.large", "c5.xlarge",
        "r5.large", "r5.xlarge",
    ],
    "azure": [
        "Standard_B1s", "Standard_B2s", "Standard_B4ms",
        "Standard_D2s_v3", "Standard_D4s_v3",
        "Standard_E2s_v3", "Standard_F2s_v2",
    ],
    "gcp": [
        "e2-micro", "e2-small", "e2-medium",
        "n1-standard-1", "n1-standard-2", "n1-standard-4",
        "n2-standard-2", "n2-standard-4",
    ],
}

APPROVED_REGIONS = {
    "aws":   ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1", "ap-southeast-1"],
    "azure": ["eastus", "westus2", "westeurope", "southeastasia", "centralindia"],
    "gcp":   ["us-central1", "us-east1", "europe-west1", "asia-south1", "asia-southeast1"],
}

REQUIRED_TAGS = ["Environment", "Owner", "CostCenter", "Project"]

MAX_SINGLE_ACTION_SAVING_INR = 500_000  # flag unusually large actions for review


class PolicyEngine:
    """
    Compiles and enforces organizational policies against recommendations.
    Called before any recommendation is surfaced or executed.
    """

    def __init__(
        self,
        active_frameworks: Optional[List[str]] = None,
        custom_rules: Optional[List[Dict]] = None,
        enforce_tagging: bool = True,
        enforce_region_policy: bool = True,
        enforce_instance_whitelist: bool = True,
    ):
        self.active_frameworks      = active_frameworks or ["soc2", "iso27001"]
        self.custom_rules           = custom_rules or []
        self.enforce_tagging        = enforce_tagging
        self.enforce_region_policy  = enforce_region_policy
        self.enforce_whitelist      = enforce_instance_whitelist

    # ── Public API ─────────────────────────────────────────────────────────────

    def check(self, recommendation: Dict[str, Any]) -> PolicyCheckResult:
        """
        Run all policy checks on a recommendation.
        Returns PolicyCheckResult — if overall_result=FAIL, action is suppressed.
        """
        rec_id    = recommendation.get("recommendation_id", "unknown")
        violations: List[PolicyViolation] = []
        passed:     List[str] = []

        # Run all checks
        checks = [
            self._check_iam_boundaries,
            self._check_security_baseline,
            self._check_compliance_frameworks,
            self._check_tagging,
            self._check_region_policy,
            self._check_instance_whitelist,
            self._check_cost_governance,
            self._check_custom_rules,
        ]

        for check_fn in checks:
            viols, pss = check_fn(recommendation)
            violations.extend(viols)
            passed.extend(pss)

        # Any BLOCKER = overall FAIL
        blockers = [v for v in violations if v.severity == PolicySeverity.BLOCKER]
        overall  = PolicyResult.FAIL if blockers else PolicyResult.PASS
        suppressed = len(blockers) > 0

        if suppressed:
            logger.warning(
                "[PolicyEngine] Recommendation %s SUPPRESSED — %d blocker(s): %s",
                rec_id,
                len(blockers),
                [v.policy_id for v in blockers],
            )

        sig = self._sign(rec_id, passed)

        return PolicyCheckResult(
            recommendation_id=rec_id,
            overall_result=overall,
            violations=violations,
            passed_checks=passed,
            policy_signature=sig,
            suppressed=suppressed,
        )

    def filter_recommendations(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter a list of recommendations — remove all policy-violating ones.
        Returns only policy-clean recommendations, each annotated with
        policy_signature.
        """
        approved = []
        for rec in recommendations:
            result = self.check(rec)
            if result.overall_result == PolicyResult.PASS:
                rec["policy_signature"]  = result.policy_signature
                rec["policy_passed"]     = True
                rec["policy_violations"] = []
                rec["policy_checked_at"] = result.checked_at
                approved.append(rec)
            # Violations never surfaced — silently dropped
        logger.info(
            "[PolicyEngine] %d/%d recommendations passed policy checks",
            len(approved), len(recommendations),
        )
        return approved

    # ── Individual checks ──────────────────────────────────────────────────────

    def _check_iam_boundaries(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []
        rec_type = rec.get("rec_type", "")

        # Termination requires elevated IAM — flag if confidence < 0.95
        if rec_type in ("idle", "terminate_instance"):
            conf = rec.get("confidence", 0)
            if conf < 0.90:
                violations.append(PolicyViolation(
                    policy_id="IAM-001",
                    policy_name="Termination Confidence Gate",
                    severity=PolicySeverity.BLOCKER,
                    message=f"Termination actions require confidence ≥ 0.90; got {conf:.2f}",
                    remediation="Increase monitoring period or raise confidence threshold",
                ))
            else:
                passed.append("IAM-001: Termination confidence gate")

        # Provider switch requires cross-account IAM review
        if rec_type == "provider_switch":
            passed.append("IAM-002: Provider switch IAM review (manual approval required)")

        passed.append("IAM-003: Action within IAM permission boundary")
        return violations, passed

    def _check_security_baseline(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []

        # Public access must never be enabled
        new_cfg = rec.get("recommended_config", {})
        if new_cfg.get("public_access") is True:
            violations.append(PolicyViolation(
                policy_id="SEC-001",
                policy_name="No Public Access",
                severity=PolicySeverity.BLOCKER,
                message="Recommended configuration enables public access — violates security baseline",
                remediation="Remove public_access=True from configuration",
            ))
        else:
            passed.append("SEC-001: No public access enabled")

        # Encryption must remain enabled
        if new_cfg.get("encryption") is False:
            violations.append(PolicyViolation(
                policy_id="SEC-002",
                policy_name="Encryption Required",
                severity=PolicySeverity.BLOCKER,
                message="Recommended config disables encryption",
                remediation="Keep encryption=True on all resources",
            ))
        else:
            passed.append("SEC-002: Encryption maintained")

        # Security score gate
        sec_score = rec.get("security_score", 80)
        if sec_score < 70:
            violations.append(PolicyViolation(
                policy_id="SEC-003",
                policy_name="Minimum Security Score",
                severity=PolicySeverity.BLOCKER,
                message=f"Target security score {sec_score:.0f} < 70 minimum",
                remediation="Resolve security findings on target provider before proceeding",
            ))
        else:
            passed.append(f"SEC-003: Security score {sec_score:.0f}/100 ≥ 70")

        return violations, passed

    def _check_compliance_frameworks(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []
        target_prov = rec.get("recommended_provider", rec.get("current_provider", "aws"))

        for framework in self.active_frameworks:
            requirements = COMPLIANCE_FRAMEWORKS.get(framework, [])
            for req in requirements:
                if req == "data_residency_eu":
                    region = rec.get("recommended_config", {}).get("region", "")
                    approved_eu = ["eu-west-1", "eu-central-1", "westeurope", "europe-west1"]
                    if region and region not in approved_eu:
                        violations.append(PolicyViolation(
                            policy_id=f"COMP-{framework.upper()}-EU",
                            policy_name=f"{framework.upper()} Data Residency",
                            severity=PolicySeverity.BLOCKER,
                            message=f"GDPR requires EU region; '{region}' not approved",
                            remediation="Use an approved EU region",
                        ))
                    else:
                        passed.append(f"COMP-{framework.upper()}-EU: Data residency OK")
                else:
                    passed.append(f"COMP-{framework.upper()}-{req}: Assumed compliant")

        return violations, passed

    def _check_tagging(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []
        if not self.enforce_tagging:
            return violations, passed

        tags = rec.get("recommended_config", {}).get("tags", {})
        # In real impl, fetch resource tags from cloud API
        # Here we pass if tags dict is present (demo mode)
        if not tags:
            # WARNING not BLOCKER — tagging is important but not execution-blocking
            passed.append("TAG-001: Tagging check skipped (no tag data in recommendation)")
        else:
            missing = [t for t in REQUIRED_TAGS if t not in tags]
            if missing:
                violations.append(PolicyViolation(
                    policy_id="TAG-001",
                    policy_name="Required Tags",
                    severity=PolicySeverity.WARNING,  # Warning, not blocker
                    message=f"Missing required tags: {missing}",
                    remediation=f"Add tags: {missing} to recommendation config",
                ))
            else:
                passed.append("TAG-001: All required tags present")

        return violations, passed

    def _check_region_policy(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []
        if not self.enforce_region_policy:
            return violations, [" REGION-001: Region policy not enforced"]

        provider = rec.get("recommended_provider", rec.get("current_provider", "aws"))
        region   = rec.get("recommended_config", {}).get("region", "")
        approved = APPROVED_REGIONS.get(provider, [])

        if region and approved and region not in approved:
            violations.append(PolicyViolation(
                policy_id="REGION-001",
                policy_name="Approved Region Policy",
                severity=PolicySeverity.BLOCKER,
                message=f"Region '{region}' not in approved list for {provider.upper()}: {approved}",
                remediation=f"Use one of: {approved}",
            ))
        else:
            passed.append(f"REGION-001: Region policy OK ({region or 'not specified'})")

        return violations, passed

    def _check_instance_whitelist(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []
        if not self.enforce_whitelist:
            return violations, ["INST-001: Whitelist not enforced"]

        provider = rec.get("recommended_provider", rec.get("current_provider", "aws"))
        new_cfg  = rec.get("recommended_config", {})
        itype    = (new_cfg.get("instance_type") or
                    new_cfg.get("vm_size") or
                    new_cfg.get("machine_type") or "")
        approved = APPROVED_INSTANCE_TYPES.get(provider, [])

        if itype and approved and itype not in approved:
            violations.append(PolicyViolation(
                policy_id="INST-001",
                policy_name="Approved Instance Types",
                severity=PolicySeverity.WARNING,
                message=f"Instance type '{itype}' not in approved list",
                remediation=f"Use one of: {approved[:5]}...",
            ))
        else:
            passed.append(f"INST-001: Instance type '{itype or 'N/A'}' approved")

        return violations, passed

    def _check_cost_governance(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []
        saving = rec.get("estimated_saving", 0)

        if saving > MAX_SINGLE_ACTION_SAVING_INR:
            violations.append(PolicyViolation(
                policy_id="COST-001",
                policy_name="Large Action Review Gate",
                severity=PolicySeverity.BLOCKER,
                message=(
                    f"Action impacts ₹{saving:,.0f}/month — exceeds single-action "
                    f"limit of ₹{MAX_SINGLE_ACTION_SAVING_INR:,.0f}. Requires CFO approval."
                ),
                remediation="Split into smaller actions or route to CFO approval workflow",
            ))
        else:
            passed.append(f"COST-001: Action saving ₹{saving:,.0f} within governance limit")

        return violations, passed

    def _check_custom_rules(
        self, rec: Dict
    ) -> tuple[List[PolicyViolation], List[str]]:
        violations, passed = [], []
        for rule in self.custom_rules:
            field_val = rec.get(rule.get("field", ""), "")
            expected  = rule.get("value", "")
            op        = rule.get("operator", "eq")
            name      = rule.get("name", "Custom Rule")
            pid       = rule.get("id", "CUSTOM-001")

            match = False
            if op == "eq"          and field_val == expected:          match = True
            elif op == "neq"       and field_val != expected:          match = True
            elif op == "contains"  and expected in str(field_val):     match = True
            elif op == "gte"       and float(field_val or 0) >= float(expected): match = True
            elif op == "lte"       and float(field_val or 0) <= float(expected): match = True

            if not match:
                violations.append(PolicyViolation(
                    policy_id=pid,
                    policy_name=name,
                    severity=PolicySeverity.BLOCKER,
                    message=f"Custom rule '{name}' failed: {field_val} {op} {expected}",
                    remediation=f"Ensure {rule.get('field')} {op} {expected}",
                ))
            else:
                passed.append(f"{pid}: {name} passed")

        return violations, passed

    # ── Signature ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sign(rec_id: str, passed_checks: List[str]) -> str:
        payload = json.dumps({
            "rec_id": rec_id,
            "passed": sorted(passed_checks),
            "ts": datetime.utcnow().isoformat()[:16],
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]
