"""
Base Agent class.
Every agent inherits from this, gets a shared memory store,
and follows the same run() → result pattern.
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    role: str          # user | assistant | system | tool
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    data: Any
    reasoning: str
    messages: List[AgentMessage] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0


class AgentMemory:
    """Simple in-process key-value memory shared between agents in one session."""

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._history.append({"key": key, "ts": datetime.utcnow().isoformat()})

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def all(self) -> Dict[str, Any]:
        return dict(self._store)

    def history(self) -> List[Dict]:
        return list(self._history)


class BaseAgent(ABC):
    """Abstract base for all agents."""

    def __init__(self, name: str, memory: Optional[AgentMemory] = None):
        self.name   = name
        self.memory = memory or AgentMemory()
        self.logger = logging.getLogger(f"agent.{name}")
        self._messages: List[AgentMessage] = []

    async def run(self, context: Dict[str, Any]) -> AgentResult:
        start = datetime.utcnow()
        self.logger.info("[%s] Starting with context keys: %s", self.name, list(context.keys()))
        try:
            result = await self._execute(context)
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            result.duration_ms = round(elapsed, 1)
            result.messages = self._messages
            self.logger.info("[%s] Finished in %.0f ms — success=%s", self.name, elapsed, result.success)
            return result
        except Exception as exc:
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            self.logger.error("[%s] Error: %s", self.name, exc, exc_info=True)
            return AgentResult(
                agent_name=self.name,
                success=False,
                data=None,
                reasoning="Agent encountered an unexpected error.",
                messages=self._messages,
                error=str(exc),
                duration_ms=round(elapsed, 1),
            )

    @abstractmethod
    async def _execute(self, context: Dict[str, Any]) -> AgentResult:
        ...

    def _add_message(self, role: str, content: str, **meta) -> None:
        self._messages.append(AgentMessage(role=role, content=content, metadata=meta))
