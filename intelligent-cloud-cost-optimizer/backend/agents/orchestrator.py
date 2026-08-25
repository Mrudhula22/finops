"""
Agent Orchestrator.
Reads the plan from PlannerAgent and dispatches each task to the
correct agent in order, passing shared AgentMemory throughout.

Full pipeline:
  User Query
    → PlannerAgent        (understand intent, create task list)
    → DataAgent           (collect multi-cloud data)
    → PredictionAgent     (forecast costs, detect anomalies)
    → OptimizationAgent   (generate recommendations)
    → SecurityAgent       (filter by security compliance)
    → ExplanationAgent    (generate XAI explanations)
    → ExecutionAgent      (execute or present for approval)
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from agents.base_agent import AgentMemory, AgentResult
from agents.planner_agent import PlannerAgent
from agents.data_agent import DataAgent
from agents.prediction_agent import PredictionAgent
from agents.optimization_agent import OptimizationAgent
from agents.security_agent import SecurityAgent
from agents.explanation_agent import ExplanationAgent
from agents.execution_agent import ExecutionAgent

logger = logging.getLogger(__name__)

# Map plan task agent names → agent classes
AGENT_REGISTRY = {
    "planner_agent":     PlannerAgent,
    "data_agent":        DataAgent,
    "prediction_agent":  PredictionAgent,
    "optimization_agent": OptimizationAgent,
    "security_agent":    SecurityAgent,
    "explanation_agent": ExplanationAgent,
    "execution_agent":   ExecutionAgent,
}

# Fixed pipeline order regardless of plan (data must come before prediction, etc.)
PIPELINE_ORDER = [
    "data_agent",
    "prediction_agent",
    "optimization_agent",
    "security_agent",
    "explanation_agent",
    "execution_agent",
]


class AgentOrchestrator:
    """
    Central coordinator for the multi-agent system.
    Runs the full pipeline for a given user query.
    """

    def __init__(self):
        self.memory = AgentMemory()
        self._agents: Dict[str, Any] = {}
        self._init_agents()

    def _init_agents(self):
        for name, cls in AGENT_REGISTRY.items():
            self._agents[name] = cls(memory=self.memory)

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(
        self,
        query: str,
        mode: str = "recommendation",
        providers: Optional[List[str]] = None,
        model: str = "ensemble",
        periods: int = 30,
    ) -> Dict[str, Any]:
        """
        Execute the full agent pipeline for a user query.

        Args:
            query:     Natural language question or instruction.
            mode:      "recommendation" (safe) or "autonomous" (auto-execute).
            providers: Restrict to specific cloud providers.
            model:     Forecasting model to use.
            periods:   Days to forecast ahead.

        Returns:
            Structured result dict with all agent outputs.
        """
        start_ts = time.time()
        logger.info("Orchestrator START | mode=%s | query=%s", mode, query[:80])

        pipeline_results: Dict[str, Any] = {}
        errors: List[str] = []

        # ── Step 0: Plan ──────────────────────────────────────────────────────
        planner = self._agents["planner_agent"]
        plan_result = await planner.run({
            "query": query,
            "mode":  mode,
            "providers": providers or ["aws", "azure", "gcp"],
        })
        pipeline_results["planner"] = self._result_to_dict(plan_result)
        if not plan_result.success:
            errors.append(f"PlannerAgent: {plan_result.error}")

        plan = self.memory.get("plan", {})
        active_mode = plan.get("mode", mode)

        # ── Step 1-6: Pipeline agents ─────────────────────────────────────────
        # Determine which agents are needed from the plan's task list
        plan_agents = {t["agent"] for t in plan.get("tasks", [])}

        for agent_name in PIPELINE_ORDER:
            # Skip agents not in the plan (unless always required)
            always_run = {"data_agent", "explanation_agent"}
            if agent_name not in plan_agents and agent_name not in always_run:
                logger.info("Skipping %s (not in plan)", agent_name)
                continue

            agent = self._agents[agent_name]
            context = {
                "mode":     active_mode,
                "model":    model,
                "periods":  periods,
                "providers": providers or plan.get("providers", ["aws", "azure", "gcp"]),
            }

            agent_result = await agent.run(context)
            pipeline_results[agent_name] = self._result_to_dict(agent_result)

            if not agent_result.success:
                errors.append(f"{agent_name}: {agent_result.error}")
                logger.warning("Agent %s failed — continuing pipeline.", agent_name)

        # ── Compile final output ──────────────────────────────────────────────
        elapsed = round((time.time() - start_ts) * 1000, 1)
        logger.info("Orchestrator DONE | %.0f ms | errors=%d", elapsed, len(errors))

        return self._compile_output(
            query=query,
            mode=active_mode,
            pipeline_results=pipeline_results,
            errors=errors,
            elapsed_ms=elapsed,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _compile_output(
        self,
        query: str,
        mode: str,
        pipeline_results: Dict[str, Any],
        errors: List[str],
        elapsed_ms: float,
    ) -> Dict[str, Any]:
        monthly_summ = self.memory.get("monthly_summary", {})
        predictions  = self.memory.get("predictions", {})
        explained    = self.memory.get("explained_recommendations", [])
        exec_results = self.memory.get("execution_results", [])

        return {
            "query":    query,
            "mode":     mode,

            # ── Dashboard data ────────────────────────────────────────────────
            "summary": {
                "aws_cost":   monthly_summ.get("aws_cost", 0),
                "azure_cost": monthly_summ.get("azure_cost", 0),
                "gcp_cost":   monthly_summ.get("gcp_cost", 0),
                "total_cost": monthly_summ.get("total_cost", 0),
                "predicted_next_month": predictions.get("total_predicted", 0),
                "monthly_budget":       predictions.get("monthly_budget", 50000),
                "budget_overrun":       predictions.get("total_overrun", 0),
                "budget_risk":          predictions.get("overall_risk", "low"),
                "anomalies_count":      len(predictions.get("anomalies", [])),
            },

            # ── Recommendations ───────────────────────────────────────────────
            "recommendations": explained,
            "total_savings_available": sum(
                r.get("estimated_saving", 0) for r in explained
            ),

            # ── Execution ─────────────────────────────────────────────────────
            "execution_results": exec_results,

            # ── Anomalies ─────────────────────────────────────────────────────
            "anomalies": predictions.get("anomalies", []),

            # ── Agent trace ───────────────────────────────────────────────────
            "agent_pipeline": pipeline_results,
            "errors":         errors,
            "elapsed_ms":     elapsed_ms,
        }

    @staticmethod
    def _result_to_dict(result: AgentResult) -> Dict[str, Any]:
        return {
            "agent":      result.agent_name,
            "success":    result.success,
            "reasoning":  result.reasoning,
            "duration_ms": result.duration_ms,
            "error":      result.error,
        }

    def reset(self) -> None:
        """Reset shared memory for a new session."""
        self.memory = AgentMemory()
        self._init_agents()
