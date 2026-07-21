"""CLI runner: ask natural-language questions, see the generated SQL and rows.

Usage:
    python -m app.run_poc
"""

import asyncio
import os

os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

from llama_index.core.memory import ChatMemoryBuffer

from app.services.sql_agent_service import SQLAgentProvider
from app.services.sql_agent_workflow import SqlAgentResult, SqlAgentWorkflow
from app.utils.logger import get_logger

logger = get_logger(__name__)

_EXIT_COMMANDS = {"exit", "quit"}


def _print_result(result: SqlAgentResult) -> None:
    print("\n--- Generated SQL ---")
    print(result.sql or "(no query was executed)")

    print("\n--- Summary ---")
    print(result.summary)

    print("\n--- Rows ---")
    query_result = result.query_result
    if not query_result or not query_result["rows"]:
        print("(no rows returned)")
    else:
        print(query_result["columns"])
        for row in query_result["rows"]:
            print([row.get(column) for column in query_result["columns"]])
        if query_result["truncated"]:
            print(f"... results truncated to {len(query_result['rows'])} rows")
    print()


async def _handle_query(
    workflow: SqlAgentWorkflow, memory: ChatMemoryBuffer, user_query: str
) -> None:
    # SqlAgentWorkflow.run_agent drives the tool-call loop and builds the trace;
    # persist_trace writes it and shapes the result, so this is just await + print.
    result: SqlAgentResult = await workflow.run(query=user_query, memory=memory)
    _print_result(result)
    print(f"Trace: {result.trace_path}\n")


async def _run_repl() -> None:
    agent = SQLAgentProvider().agent
    # No timeout ceiling on the agent's multi-tool-call conversation, matching the
    # unbounded FunctionAgent.run() this replaces (Workflow defaults to 45s).
    workflow = SqlAgentWorkflow(timeout=None)
    memory = ChatMemoryBuffer.from_defaults(llm=agent.llm)

    print("Conversation AI POC - NL to SQL. Type 'exit' to quit.\n")
    while True:
        try:
            user_query = input("You: ").strip()
        except EOFError:
            break

        if not user_query:
            continue
        if user_query.lower() in _EXIT_COMMANDS:
            break

        try:
            await _handle_query(workflow, memory, user_query)
        except Exception:
            logger.exception("Agent run failed for query: %s", user_query)
            print("Sorry, something went wrong answering that. Check the logs above.\n")


def main() -> None:
    asyncio.run(_run_repl())


if __name__ == "__main__":
    main()
