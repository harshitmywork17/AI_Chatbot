import pytest

from app.services.sql_guard import UnsafeSqlQueryError, assert_select_only


def test_assert_select_only_accepts_plain_select():
    assert_select_only('SELECT "name" FROM "sites"')


def test_assert_select_only_accepts_cte():
    assert_select_only("WITH ranked AS (SELECT 1 AS n) SELECT * FROM ranked")


def test_assert_select_only_rejects_empty_query():
    with pytest.raises(UnsafeSqlQueryError):
        assert_select_only("   ")


def test_assert_select_only_rejects_multiple_statements():
    with pytest.raises(UnsafeSqlQueryError):
        assert_select_only("SELECT 1; SELECT 2")


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO \"devices\" (mac) VALUES ('x')",
        "UPDATE \"devices\" SET status = 'online'",
        'DELETE FROM "devices"',
        'DROP TABLE "devices"',
        'ALTER TABLE "devices" ADD COLUMN foo TEXT',
        'TRUNCATE "devices"',
    ],
)
def test_assert_select_only_rejects_dml_ddl(sql):
    with pytest.raises(UnsafeSqlQueryError):
        assert_select_only(sql)


def test_assert_select_only_rejects_second_statement_hidden_after_comment():
    with pytest.raises(UnsafeSqlQueryError):
        assert_select_only('SELECT 1; -- harmless\nDROP TABLE "devices"')


def test_assert_select_only_strips_comment_before_checking_keywords():
    # The DROP text lives inside a block comment, so it is never executed;
    # stripping it before validation must not itself trigger a false positive.
    assert_select_only("SELECT 1 /* note: do not DROP this table */")


def test_assert_select_only_rejects_non_select_leading_keyword():
    with pytest.raises(UnsafeSqlQueryError):
        assert_select_only('EXPLAIN SELECT * FROM "devices"')


def test_assert_select_only_does_not_false_positive_on_identifier_substrings():
    # "update_count" contains "UPDATE" as a substring but not as a whole word.
    assert_select_only('SELECT "update_count" FROM "devices"')
