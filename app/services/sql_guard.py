"""Read-only SQL enforcement gate. Kept separate from tools.py per SRP."""

import re

from app.core.constants import FORBIDDEN_SQL_KEYWORDS

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_LEADING_STATEMENT_RE = re.compile(r"^\s*(\w+)", re.IGNORECASE)

_ALLOWED_LEADING_KEYWORDS = {"SELECT", "WITH"}


class UnsafeSqlQueryError(Exception):
    """Raised when a candidate SQL string fails the read-only safety gate."""


def _strip_comments(sql: str) -> str:
    without_block_comments = _BLOCK_COMMENT_RE.sub(" ", sql)
    return _LINE_COMMENT_RE.sub(" ", without_block_comments)


def assert_select_only(sql: str) -> None:
    """Raise UnsafeSqlQueryError unless `sql` is a single, plain SELECT statement.

    Rejects: empty input, more than one statement, any statement that doesn't
    start with SELECT/WITH, and any of the DML/DDL keywords in
    FORBIDDEN_SQL_KEYWORDS appearing anywhere in the query.
    """
    cleaned = _strip_comments(sql).strip()
    if not cleaned:
        raise UnsafeSqlQueryError("Query is empty.")

    statements = [part.strip() for part in cleaned.split(";") if part.strip()]
    if len(statements) != 1:
        raise UnsafeSqlQueryError("Only a single SQL statement is allowed.")

    statement = statements[0]
    leading_match = _LEADING_STATEMENT_RE.match(statement)
    leading_keyword = leading_match.group(1).upper() if leading_match else ""
    if leading_keyword not in _ALLOWED_LEADING_KEYWORDS:
        raise UnsafeSqlQueryError("Only SELECT statements are allowed.")

    upper_statement = statement.upper()
    for forbidden_keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{forbidden_keyword}\b", upper_statement):
            raise UnsafeSqlQueryError(f"Query contains forbidden keyword: {forbidden_keyword}.")
