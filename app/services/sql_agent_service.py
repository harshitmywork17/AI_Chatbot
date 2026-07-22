"""FunctionAgent wired up once with the SQL tools/prompt, then reused for every query."""

from llama_index.core.agent.workflow import FunctionAgent

from app.core.prompts import SQL_AGENT_SYSTEM_PROMPT
from app.services.llm_provider import LLMProvider
from app.services.tools import build_sql_agent_tools


class SQLAgentProvider:
    """Process-wide FunctionAgent wired up with the SQL tools and system prompt."""

    _instance: "SQLAgentProvider | None" = None
    _agent: FunctionAgent

    def __new__(cls) -> "SQLAgentProvider":
        # Singleton so tool binding (build_sql_agent_tools) runs once per process,
        # not on every question the REPL loop asks.
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._agent = FunctionAgent(
                name="sql_agent",
                description="Answers natural-language questions with read-only SQL.",
                tools=build_sql_agent_tools(),
                llm=LLMProvider().llm,
                system_prompt=SQL_AGENT_SYSTEM_PROMPT,
                # Our workflow is strictly sequential (search -> schema -> execute),
                # so parallel tool calls are never needed. Some providers (e.g. Groq's
                # open-weight Llama models) are also unreliable at emitting multiple
                # tool calls in one turn, so disabling this is a safe default regardless
                # of which LLM_PROVIDER is configured.
                allow_parallel_tool_calls=False,
            )
            cls._instance = instance
        return cls._instance

    @property
    def agent(self) -> FunctionAgent:
        return self._agent
