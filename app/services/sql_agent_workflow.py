"""Workflow that runs the SQL agent for one query.

The FunctionAgent's tool-call loop still decides which tables to inspect and what
SQL to run (this doesn't become a fixed pipeline); this file only orchestrates
around it: pre-run semantic table discovery, a bounded retry for known transient
tool-call generation errors, reasoning-trace persistence, and forwarding every
internal tool-call/message event onto the workflow's own stream for any external
listener to observe. Each retry attempt gets a fresh trace and restores `memory`
to its pre-attempt snapshot, so a failed attempt never leaks partial state into
the attempt that succeeds.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llama_index.core.agent.workflow import AgentOutput, ToolCallResult
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step

from app.services.sql_agent_service import SQLAgentProvider
from app.services.table_search_service import TableSearchService
from app.services.trace_service import AgentTrace, save_trace
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Some providers (observed with Groq's hosted Llama models) occasionally emit a
# malformed function-call tag and reject their own generation with a 400
# 'tool_use_failed' error. This is a sampling-time glitch, not a deterministic bug
# in our tools/prompt, so resampling via a retry almost always succeeds.
#
# Detected by duck-typing the error body rather than importing a provider-specific
# exception type, so this stays correct regardless of which LLM_PROVIDER is
# configured — a non-matching exception (any type, from any provider) is simply
# re-raised immediately on the first attempt, unchanged from before this retry
# existed.
_MAX_TOOL_CALL_RETRIES = 2
_RETRYABLE_ERROR_CODE = "tool_use_failed"


def _is_retryable_tool_call_error(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    return isinstance(body, dict) and body.get("code") == _RETRYABLE_ERROR_CODE


@dataclass
class SqlAgentResult:
    """Everything a caller needs to print after one query."""

    sql: str | None
    query_result: dict[str, Any] | None
    summary: str
    trace_path: Path


class AgentRunCompleteEvent(Event):
    """Internal: the agent finished its tool-call loop for this query."""

    response: AgentOutput
    trace: AgentTrace
    sql: str | None
    query_result: dict[str, Any] | None


class SqlAgentWorkflow(Workflow):
    """Runs semantic table discovery, drives the FunctionAgent for one query, then persists its trace."""

    @step
    async def run_agent(self, ctx: Context, ev: StartEvent) -> AgentRunCompleteEvent:
        query: str = ev.query
        memory: ChatMemoryBuffer = ev.memory

        # 1. Pre-run Semantic Search on DB Table Descriptions
        search_service = TableSearchService()
        candidate_tables = search_service.search_relevant_tables(query)

        enriched_prompt_context = ""
        if candidate_tables:
            enriched_prompt_context = f"\n\nPre-discovered Candidate Tables & Relationships for query '{query}':\n"
            for t in candidate_tables:
                rels = [f"{r['from_column']} -> {r['target_table']}.{r['target_column']}" for r in t.get("relationships", [])]
                rel_str = f" | Joins: {', '.join(rels)}" if rels else ""
                enriched_prompt_context += f"- Table: {t['table_name']}{rel_str}\n  Purpose: {t['description']}\n"

        agent = SQLAgentProvider().agent
        user_input_with_context = f"{query}{enriched_prompt_context}" if enriched_prompt_context else query

        # `agent.run` writes the user message into `memory` as its very first step,
        # before any LLM call. Snapshotting here lets a retry restore memory to this
        # exact pre-attempt state, so a failed attempt never duplicates that message.
        # list(...) makes a real copy — aget_all() returns a live reference to
        # memory's internal store, which later aput() calls mutate in place.
        memory_snapshot = list(await memory.aget_all())

        for attempt in range(_MAX_TOOL_CALL_RETRIES + 1):
            trace = AgentTrace(query=query)
            sql: str | None = None
            query_result: dict[str, Any] | None = None
            try:
                handler = agent.run(user_msg=user_input_with_context, memory=memory)
                async for event in handler.stream_events():
                    ctx.write_event_to_stream(event)
                    if isinstance(event, ToolCallResult):
                        trace.record_tool_result(event)
                        if event.tool_name == "execute_sql_query":
                            sql = event.tool_kwargs.get("sql")
                            query_result = event.tool_output.raw_output
                    elif isinstance(event, AgentOutput):
                        trace.record_agent_output(event)

                response: AgentOutput = await handler
                return AgentRunCompleteEvent(
                    response=response, trace=trace, sql=sql, query_result=query_result
                )
            except Exception as exc:
                if not _is_retryable_tool_call_error(exc) or attempt == _MAX_TOOL_CALL_RETRIES:
                    raise
                await memory.aset(memory_snapshot)
                logger.warning(
                    "LLM emitted a malformed tool call (attempt %d/%d), retrying: %s",
                    attempt + 1,
                    _MAX_TOOL_CALL_RETRIES,
                    exc,
                )

        raise AssertionError("unreachable")  # loop always returns or raises

    @step
    async def persist_trace(self, ctx: Context, ev: AgentRunCompleteEvent) -> StopEvent:
        trace_path = save_trace(ev.trace)
        result = SqlAgentResult(
            sql=ev.sql,
            query_result=ev.query_result,
            summary=str(ev.response.response.content),
            trace_path=trace_path,
        )
        return StopEvent(result=result)
