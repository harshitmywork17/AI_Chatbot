"""LlamaIndex Workflow that runs the SQL agent for one query.

Replaces the manual event-loop + trace-building that used to live in
run_poc.py: the FunctionAgent's tool-call loop still decides which tables to
inspect and what SQL to run (this doesn't become a fixed pipeline), but the
surrounding orchestration - running the agent, collecting a reasoning trace,
persisting it - is now expressed as two Workflow steps instead of inline
REPL code, and every internal tool-call/message event is forwarded to the
workflow's own stream for any external listener to observe.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llama_index.core.agent.workflow import AgentOutput, ToolCallResult
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step

from app.services.sql_agent_service import SQLAgentProvider
from app.services.trace_service import AgentTrace, save_trace


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
    """Runs the FunctionAgent for one query, then persists its reasoning trace.

    Step 1 (`run_agent`) drives the agent's tool-call loop and builds the
    trace as events arrive. Step 2 (`persist_trace`) writes that trace to
    disk and shapes the final result. Splitting them keeps "talk to the LLM"
    and "write the trace file" independently testable.
    """

    @step
    async def run_agent(self, ctx: Context, ev: StartEvent) -> AgentRunCompleteEvent:
        query: str = ev.query
        memory: ChatMemoryBuffer = ev.memory

        agent = SQLAgentProvider().agent
        handler = agent.run(user_msg=query, memory=memory)
        trace = AgentTrace(query=query)

        sql: str | None = None
        query_result: dict[str, Any] | None = None
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
