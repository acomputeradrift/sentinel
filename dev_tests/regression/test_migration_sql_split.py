import unittest
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class MigrationSqlSplitTest(unittest.TestCase):
    def test_split_skips_line_comment_with_semicolon(self) -> None:
        from sentinel.server.persistence import db

        sql = """-- Maintained in append_test_result; historical note
create table if not exists x (a int);
"""
        parts = db._split_sql_migration_statements(sql)
        self.assertEqual(len(parts), 1)
        self.assertIn("create table", parts[0].lower())

    def test_split_preserves_semicolon_inside_single_quoted_literal(self) -> None:
        from sentinel.server.persistence import db

        sql = "insert into t (c) values ('a;b');\ndelete from t where c = 'z';"
        parts = db._split_sql_migration_statements(sql)
        self.assertEqual(len(parts), 2)
        self.assertIn("'a;b'", parts[0])
        self.assertIn("delete", parts[1].lower())


if __name__ == "__main__":
    unittest.main()
