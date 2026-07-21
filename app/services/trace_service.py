"""Builds and persists a JSON reasoning trace for one agent run: the ordered
sequence of tool calls and model messages that led to the final answer.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from llama_index.core.agent.workflow import AgentOutput, ToolCallResult

from app.core.constants import TRACE_DIR


@dataclass
class TraceStep:
    """One entry in the trace: either a model message or a tool call/result."""

    type: Literal["agent_message", "tool_call"]
    content: str | None = None
    tool_name: str | None = None
    tool_kwargs: dict[str, Any] | None = None
    tool_output: Any = None


@dataclass
class AgentTrace:
    """Chronological record of one user query, ready to serialize to JSON."""

    query: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    steps: list[TraceStep] = field(default_factory=list)
    final_answer: str = ""

    def record_agent_output(self, event: AgentOutput) -> None:
        """Log the model's message text for this turn, if it said anything.

        Tool-calling turns usually carry empty content, so this mostly captures
        commentary turns and the final answer — the closest thing to visible
        "reasoning" a function-calling model exposes.
        """
        content = (event.response.content or "").strip()
        if content:
            self.steps.append(TraceStep(type="agent_message", content=content))
            self.final_answer = content

    def record_tool_result(self, event: ToolCallResult) -> None:
        self.steps.append(
            TraceStep(
                type="tool_call",
                tool_name=event.tool_name,
                tool_kwargs=event.tool_kwargs,
                tool_output=event.tool_output.raw_output,
            )
        )


def save_trace(trace: AgentTrace) -> Path:
    """Write `trace` to TRACE_DIR/<timestamp>.json and return the file path."""
    TRACE_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    trace_path = TRACE_DIR / f"{timestamp}.json"
    trace_path.write_text(
        json.dumps(asdict(trace), indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return trace_path
