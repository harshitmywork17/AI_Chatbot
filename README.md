# Conversation AI POC — Natural Language to SQL (NL-to-SQL)

A local proof of concept validating the NL-to-SQL querying approach against a local
PostgreSQL database, using LlamaIndex's `FunctionAgent` and Groq (Llama model) as the LLM.

Read-only by design: the agent can only discover the schema and run a single validated
`SELECT` statement per turn. See [`src/agent/sql_guard.py`](src/agent/sql_guard.py) for the
enforcement gate.

## Project layout

Follows the standard `app/{core,models,services,utils}` layout (no `api/`/`auth/` —
there's no HTTP layer or authentication in this CLI-only POC, so those folders would
sit empty):

```
conversation_ai_poc/
├── app/
│   ├── core/
│   │   ├── config.py       # env-driven Settings (pydantic-settings)
│   │   ├── constants.py    # row caps, forbidden SQL keywords, table registry
│   │   ├── prompts.py      # SQL_AGENT_SYSTEM_PROMPT + tool descriptions (all LLM-facing text)
│   │   └── database.py     # DatabaseSessionProvider (singleton SQLAlchemy engine)
│   ├── models/
│   │   └── av_platform.py  # SQLAlchemy models for the 11 tables
│   ├── services/
│   │   ├── llm_provider.py      # LLMProvider (singleton) — swap via LLM_PROVIDER (groq/anthropic)
│   │   ├── embedding_provider.py # EmbeddingProvider (singleton) — swap via EMBEDDING_PROVIDER (local/openai)
│   │   ├── sql_guard.py         # assert_select_only read-only gate
│   │   ├── tools.py             # list_available_tables / get_table_schema / execute_sql_query
│   │   ├── sql_agent_service.py # SQLAgentProvider (singleton FunctionAgent)
│   │   ├── sql_agent_workflow.py # SqlAgentWorkflow (LlamaIndex Workflow: run agent -> persist trace)
│   │   ├── seed_service.py      # seeding logic, called by app/seed.py
│   │   └── trace_service.py     # AgentTrace/save_trace — per-query JSON reasoning trace
│   ├── utils/
│   │   └── logger.py       # get_logger(__name__)
│   ├── run_poc.py          # CLI REPL entrypoint
│   └── seed.py             # schema-creation + seed entrypoint
├── tests/
├── .env / .env.example
├── requirements.txt
├── pyproject.toml          # black / isort / mypy / pytest config
└── .flake8
```

## Setup

A virtual environment named `li` already exists at the project root.

1. Activate it:
   ```powershell
   .\li\Scripts\Activate.ps1
   ```
2. Dependencies are already installed from `requirements.txt`. To reinstall/update:
   ```powershell
   .\li\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. Fill in `GROQ_API_KEY` in `.env` (get a free key at console.groq.com). `DATABASE_URL`
   already points at a local Postgres instance — update the host/user/password/db name
   to match your local setup if different.
4. Make sure the target Postgres database exists and is reachable, e.g.:
   ```powershell
   createdb conversation_ai_poc
   ```
   The seed script creates the `pgcrypto` extension and all tables itself — no manual
   migration step is needed.

## Running

Create the schema and seed dummy data (safe to re-run — it no-ops if already seeded):
```powershell
.\li\Scripts\python.exe -m app.seed
```

Start the NL-to-SQL console:
```powershell
.\li\Scripts\python.exe -m app.run_poc
```

Each turn prints the generated SQL, a natural-language summary, and the raw rows
returned (capped at 100).

### Reasoning traces

Every query also writes a JSON trace to `traces/<UTC-timestamp>.json` — the ordered
list of tool calls the agent made (table lists, schema lookups, the SQL it ran, and
each tool's raw output), plus its final answer. This is the closest thing to visible
"reasoning" a tool-calling model exposes: Groq's function-calling models don't emit
chain-of-thought text on tool-call turns, so the trace is the sequence of what the
agent looked up and ran, in order, rather than freeform commentary. `traces/` is
gitignored — it's local run output, not source.

## Tests / linting

```powershell
.\li\Scripts\python.exe -m pytest
.\li\Scripts\python.exe -m black --check .
.\li\Scripts\python.exe -m isort --check-only .
.\li\Scripts\python.exe -m ruff check .
.\li\Scripts\python.exe -m mypy app
```

## Seeded data

- 1 site (Boise HQ), 3 room templates, 6 rooms.
- 15 devices across Neat, Poly, and Crestron hardware.
- 2 devices with active baseline drift and matching drift events.
- 5 successful auto-heal remediation events.
- 4 ServiceNow tickets (2 open, 2 closed).
- A firmware policy requiring `1.8.2` for video bars, with 3 devices seeded below that
  baseline in `firmware_inventory`.

## Security notes

- `execute_sql_query` rejects anything but a single `SELECT`/`WITH` statement (see
  `sql_guard.assert_select_only`) and additionally runs inside a Postgres
  `SET TRANSACTION READ ONLY` transaction as a second line of defense.
- `get_table_schema` only accepts table names present in the `TABLE_DESCRIPTIONS`
  registry, so the agent can't probe arbitrary database objects.
- For anything beyond local experimentation, point `DATABASE_URL` at a Postgres role
  that only has `SELECT` grants — the in-app guard is defense-in-depth, not a
  replacement for DB-level permissions.
