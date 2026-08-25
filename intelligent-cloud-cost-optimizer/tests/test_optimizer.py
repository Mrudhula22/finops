"""Tests for optimization engine."""
import pytest
from optimization.multi_cloud_optimizer import MultiCloudOptimizer
from optimization.what_if_simulator import WhatIfSimulator
from optimization.risk_engine import RiskEngine
from ml.risk.risk_model import RiskModel

def test_multi_cloud_compare():
    opt = MultiCloudOptimizer()
    result = opt.compare_workload("Test Workload", "compute", "medium", "aws")
    assert result.best_provider in ["aws","azure","gcp"]
    assert len(result.options) == 3
    assert result.best_cost > 0

def test_what_if_terminate_idle():
    sim = WhatIfSimulator()
    costs = {"aws_cost": 33900, "azure_cost": 35000, "gcp_cost": 30000}
    resources = {"aws": {"compute": [{"configuration":{"avg_cpu_utilization":3,"monthly_cost_inr":2500},"resource_id":"i-1","resource_name":"dev"}]}, "azure":{"compute":[]}, "gcp":{"compute":[]}}
    result = sim.simulate("terminate_idle", costs, resources)
    assert result.saving >= 0
    assert result.scenario_id == "sim_terminate_idle"

def test_risk_model_low_risk():
    rm = RiskModel()
    rec = {"recommendation_id":"r1","current_provider":"aws","recommended_provider":"aws",
           "saving_percentage":20,"security_score":90,"workload_criticality":"low",
           "current_cpu":15,"current_memory":20,"is_stateful":False,"has_dependencies":False}
    result = rm.assess(rec)
    assert result.overall_score < 60
    assert result.risk_level in ["low","medium"]

def test_risk_engine_auto_approve():
    engine = RiskEngine()
    rec = {"recommendation_id":"r2","rec_type":"rightsizing","current_provider":"aws",
           "recommended_provider":"aws","saving_percentage":15,"security_score":92,
           "security_approved":True,"workload_criticality":"low","current_cpu":10,
           "current_memory":20,"is_stateful":False,"has_dependencies":False}
    verdict = engine.evaluate(rec)
    assert not verdict.is_blocked
