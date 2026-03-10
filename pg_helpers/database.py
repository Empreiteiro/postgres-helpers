"""Interface de alto nível para operações PostgreSQL."""

import psycopg2
import psycopg2.extras
from psycopg2 import sql as psql
from contextlib import contextmanager
import math


class DatabaseManager:
    def __init__(self, host: str, port: int, user: str, password: str, dbname: str):
        self.params = dict(host=host, port=port, user=user, password=password, dbname=dbname)

    @contextmanager
    def _conn(self):
        conn = psycopg2.connect(**self.params)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params=None):
        """Executa um statement sem retornar linhas."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)

    def execute_many(self, sql: str, params_list: list):
        """Executa um statement para múltiplos conjuntos de parâmetros."""
        if not params_list:
            return
        with self._conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, sql, params_list, page_size=200)

    def query(self, sql, params=None) -> list[dict]:
        """Executa uma query e retorna lista de dicts."""
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]

    def list_tables(self) -> list[str]:
        rows = self.query(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        return [r["tablename"] for r in rows]

    def columns(self, table: str) -> list[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(psql.SQL("SELECT * FROM {} LIMIT 0").format(psql.Identifier(table)))
                return [desc[0] for desc in cur.description]

    def count(self, table: str) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(psql.SQL("SELECT COUNT(*) FROM {}").format(psql.Identifier(table)))
                return cur.fetchone()[0]

    def list_databases(self) -> list[str]:
        rows = self.query(
            "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
        )
        return [r["datname"] for r in rows]

    def drop_database(self, dbname: str):
        """Dropa um banco de dados. Requer conexão ao banco de manutenção (postgres)."""
        conn = psycopg2.connect(**{**self.params, "dbname": "postgres"})
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(
                    psql.SQL("DROP DATABASE {}").format(psql.Identifier(dbname))
                )
        finally:
            conn.close()

    def drop_table(self, table: str, cascade: bool = False):
        """Dropa uma tabela do banco atual."""
        stmt = psql.SQL("DROP TABLE {}").format(psql.Identifier(table))
        if cascade:
            stmt = psql.SQL("DROP TABLE {} CASCADE").format(psql.Identifier(table))
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(stmt)

    def paginate(self, table: str, page: int = 1, per_page: int = 50) -> tuple[list[dict], int]:
        offset = (page - 1) * per_page
        total = self.count(table)
        with self._conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    psql.SQL("SELECT * FROM {} LIMIT %s OFFSET %s").format(psql.Identifier(table)),
                    (per_page, offset),
                )
                rows = [dict(r) for r in cur.fetchall()]
        return rows, total
