"""Tests for security adapters and optimizer."""
import pytest
import asyncio
from cloud.aws.security import AWSSecurityAdapter
from cloud.azure.security import AzureSecurityAdapter
from cloud.gcp.security import GCPSecurityAdapter
from optimization.security_optimizer import SecurityOptimizer

def run(coro): return asyncio.get_event_loop().run_until_complete(coro)

def test_aws_security_checks():
    adapter = AWSSecurityAdapter()
    result  = run(adapter.run_security_checks())
    assert "overall_score" in result
    assert 0 <= result["overall_score"] <= 100
    assert result["provider"] == "aws"

def test_azure_security_checks():
    adapter = AzureSecurityAdapter()
    result  = run(adapter.run_security_checks())
    assert "overall_score" in result

def test_gcp_security_checks():
    adapter = GCPSecurityAdapter()
    result  = run(adapter.run_security_checks())
    assert "overall_score" in result

def test_security_optimizer_filter():
    opt = SecurityOptimizer()
    options = [
        {"provider":"aws","monthly_cost":18500},
        {"provider":"azure","monthly_cost":15800},
        {"provider":"gcp","monthly_cost":14200},
    ]
    reports = {
        "aws":   {"overall_score":82,"findings":[]},
        "azure": {"overall_score":85,"findings":[]},
        "gcp":   {"overall_score":88,"findings":[]},
    }
    adjusted, best = opt.filter_by_security(options, reports)
    assert len(adjusted) == 3
    assert best is not None
    assert best.is_approved
