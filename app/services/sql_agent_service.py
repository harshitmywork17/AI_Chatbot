"""FunctionAgent wired up once with the SQL tools/prompt, then reused for every query."""

from llama_index.core.agent.workflow import FunctionAgent

from app.core.prompts import SQL_AGENT_SYSTEM_PROMPT
from app.services.llm_provider import GroqLLMProvider
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
                llm=GroqLLMProvider().llm,
                system_prompt=SQL_AGENT_SYSTEM_PROMPT,
            )
            cls._instance = instance
        return cls._instance

    @property
    def agent(self) -> FunctionAgent:
        return self._agent
