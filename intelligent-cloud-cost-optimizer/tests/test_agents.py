"""Tests for the agent pipeline."""
import pytest
import asyncio
from agents.base_agent import AgentMemory
from agents.planner_agent import PlannerAgent
from agents.data_agent import DataAgent
from agents.optimization_agent import OptimizationAgent

def run(coro): return asyncio.get_event_loop().run_until_complete(coro)

def test_planner_rule_based():
    mem = AgentMemory()
    agent = PlannerAgent(mem)
    result = run(agent.run({"query":"reduce my AWS costs next month","mode":"recommendation"}))
    assert result.success
    plan = result.data
    assert "tasks" in plan
    assert "mode" in plan
    assert len(plan["tasks"]) >= 2

def test_data_agent_collects():
    mem = AgentMemory()
    agent = DataAgent(mem)
    result = run(agent.run({"action":"collect_all_costs"}))
    assert result.success
    data = mem.get("unified_data")
    assert data is not None
    summ = mem.get("monthly_summary")
    assert summ["total_cost"] > 0

def test_optimization_agent_generates():
    mem = AgentMemory()
    # Pre-populate memory
    da = DataAgent(mem)
    run(da.run({"action":"collect_all_costs"}))
    oa = OptimizationAgent(mem)
    result = run(oa.run({}))
    assert result.success
    recs = mem.get("recommendations")
    assert isinstance(recs, list)
