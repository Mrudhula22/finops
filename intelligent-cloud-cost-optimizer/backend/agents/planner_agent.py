"""
Planner Agent.
Receives a natural-language user query, breaks it into a structured plan,
and dispatches sub-tasks to the correct downstream agents.
Uses OpenAI if available; falls back to a rule-based planner.
"""

import json
import logging
from typing import Any, Dict, List

from agents.base_agent import BaseAgent, AgentMemory, AgentResult
from config.settings import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an Intelligent Cloud Cost Optimization Planner.
Given a user's natural-language request, produce a JSON plan with:
{
  "goal": "<one sentence summary>",
  "tasks": [
    {"agent": "<agent_name>", "action": "<action>", "priority": <1-5>}
  ],
  "mode": "recommendation | autonomous",
  "providers": ["aws", "azure", "gcp"],
  "urgency": "low | medium | high"
}

Available agents: data_agent, prediction_agent, optimization_agent,
                  security_agent, explanation_agent, execution_agent

Be concise. Return only valid JSON."""


class PlannerAgent(BaseAgent):
    """Translates natural-language queries into structured execution plans."""

    def __init__(self, memory: AgentMemory = None):
        super().__init__("planner_agent", memory)
        self._openai_client = None
        self._init_openai()

    def _init_openai(self):
        try:
            from openai import OpenAI
            if settings.OPENAI_API_KEY:
                self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        except ImportError:
            logger.warning("OpenAI not installed — using rule-based planner.")

    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        query = context.get("query", "")
        mode  = context.get("mode", "recommendation")

        self._add_message("user", query)

        if self._openai_client and settings.OPENAI_API_KEY:
            plan = await self._llm_plan(query, mode)
        else:
            plan = self._rule_based_plan(query, mode)

        self._add_message("assistant", json.dumps(plan, indent=2))
        self.memory.set("plan", plan)
        self.memory.set("mode", plan.get("mode", mode))

        return AgentResult(
            agent_name=self.name,
            success=True,
            data=plan,
            reasoning=f"Plan generated for goal: {plan.get('goal', query)}",
        )

    async def _llm_plan(self, query: str, mode: str) -> Dict[str, Any]:
        try:
            response = self._openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Mode preference: {mode}\nQuery: {query}"},
                ],
                temperature=0.1,
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as exc:
            logger.warning("LLM planning failed: %s — falling back.", exc)
            return self._rule_based_plan(query, mode)

    @staticmethod
    def _rule_based_plan(query: str, mode: str) -> Dict[str, Any]:
        """Simple keyword-based plan for offline use."""
        q = query.lower()
        tasks: List[Dict[str, Any]] = []

        # Always start with data collection
        tasks.append({"agent": "data_agent", "action": "collect_all_costs", "priority": 1})

        if any(w in q for w in ["predict", "forecast", "next month", "budget", "future"]):
            tasks.append({"agent": "prediction_agent", "action": "forecast_costs", "priority": 2})

        if any(w in q for w in ["optimize", "save", "reduce", "cheaper", "cost", "overrun"]):
            tasks.append({"agent": "optimization_agent", "action": "generate_recommendations", "priority": 3})

        if any(w in q for w in ["security", "secure", "risk", "safe", "vulnerable"]):
            tasks.append({"agent": "security_agent", "action": "assess_security", "priority": 3})

        tasks.append({"agent": "explanation_agent", "action": "explain_recommendations", "priority": 4})

        if mode == "autonomous":
            tasks.append({"agent": "execution_agent", "action": "execute_approved", "priority": 5})

        providers = []
        if "aws"   in q: providers.append("aws")
        if "azure" in q: providers.append("azure")
        if "gcp"   in q: providers.append("gcp")
        if not providers:
            providers = ["aws", "azure", "gcp"]

        urgency = "high" if any(w in q for w in ["urgent", "overspend", "exceeded", "alert"]) \
                  else "medium"

        return {
            "goal":      query,
            "tasks":     tasks,
            "mode":      mode,
            "providers": providers,
            "urgency":   urgency,
        }
