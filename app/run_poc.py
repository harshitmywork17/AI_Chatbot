"""CLI runner: ask natural-language questions, see the generated SQL and rows.

Usage:
    python -m app.run_poc
"""

import asyncio
from typing import Any

from llama_index.core.agent.workflow import AgentOutput, FunctionAgent, ToolCallResult
from llama_index.core.memory import ChatMemoryBuffer

from app.services.sql_agent_service import SQLAgentProvider
from app.utils.logger import get_logger

logger = get_logger(__name__)

_EXIT_COMMANDS = {"exit", "quit"}


def _print_result(sql: str | None, query_result: dict[str, Any] | None, summary: str) -> None:
    print("\n--- Generated SQL ---")
    print(sql or "(no query was executed)")

    print("\n--- Summary ---")
    print(summary)

    print("\n--- Rows ---")
    if not query_result or not query_result["rows"]:
        print("(no rows returned)")
    else:
        print(query_result["columns"])
        for row in query_result["rows"]:
            print([row.get(column) for column in query_result["columns"]])
        if query_result["truncated"]:
            print(f"... results truncated to {len(query_result['rows'])} rows")
    print()


async def _handle_query(agent: FunctionAgent, memory: ChatMemoryBuffer, user_query: str) -> None:
    handler = agent.run(user_msg=user_query, memory=memory)

    last_sql: str | None = None
    last_result: dict[str, Any] | None = None
    async for event in handler.stream_events():
        if isinstance(event, ToolCallResult) and event.tool_name == "execute_sql_query":
            last_sql = event.tool_kwargs.get("sql")
            last_result = event.tool_output.raw_output

    response: AgentOutput = await handler
    _print_result(last_sql, last_result, str(response.response.content))


async def _run_repl() -> None:
    agent = SQLAgentProvider().agent
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
            await _handle_query(agent, memory, user_query)
        except Exception:
            logger.exception("Agent run failed for query: %s", user_query)
            print("Sorry, something went wrong answering that. Check the logs above.\n")


def main() -> None:
    asyncio.run(_run_repl())


if __name__ == "__main__":
    main()
