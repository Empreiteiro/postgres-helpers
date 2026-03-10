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

    def run_query(self, sql: str, max_rows: int = 500) -> dict:
        """Executa SQL arbitrário e retorna resultado estruturado.

        Retorna dict com:
          ok, is_select, columns, rows, rowcount, truncated  — em caso de sucesso
          ok=False, error, pgcode                            — em caso de erro
        """
        try:
            with self._conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql)
                    if cur.description is not None:
                        # SELECT / RETURNING / EXPLAIN / SHOW
                        raw = cur.fetchmany(max_rows + 1)
                        truncated = len(raw) > max_rows
                        rows = [dict(r) for r in raw[:max_rows]]
                        columns = [d[0] for d in cur.description]
                        return {
                            "ok": True,
                            "is_select": True,
                            "columns": columns,
                            "rows": rows,
                            "rowcount": len(rows),
                            "truncated": truncated,
                        }
                    else:
                        # INSERT / UPDATE / DELETE / DDL (rowcount == -1 para DDL)
                        return {
                            "ok": True,
                            "is_select": False,
                            "columns": [],
                            "rows": [],
                            "rowcount": cur.rowcount,
                            "truncated": False,
                        }
        except psycopg2.Error as e:
            return {
                "ok": False,
                "error": e.pgerror.strip() if e.pgerror else str(e),
                "pgcode": e.pgcode,
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "pgcode": None}

    def get_foreign_keys(self) -> list[dict]:
        """Retorna todas as relações FK do schema public."""
        return self.query("""
            SELECT
                kcu1.table_name  AS from_table,
                kcu1.column_name AS from_column,
                kcu2.table_name  AS to_table,
                kcu2.column_name AS to_column,
                rc.constraint_name
            FROM information_schema.referential_constraints rc
            JOIN information_schema.key_column_usage kcu1
                ON kcu1.constraint_catalog = rc.constraint_catalog
                AND kcu1.constraint_schema  = rc.constraint_schema
                AND kcu1.constraint_name    = rc.constraint_name
            JOIN information_schema.key_column_usage kcu2
                ON kcu2.constraint_catalog = rc.unique_constraint_catalog
                AND kcu2.constraint_schema  = rc.unique_constraint_schema
                AND kcu2.constraint_name    = rc.unique_constraint_name
            WHERE kcu1.table_schema = 'public'
            ORDER BY kcu1.table_name, kcu1.column_name
        """)

    def get_columns_with_types(self, table: str) -> list[dict]:
        """Retorna colunas com tipo de dado e flag de PK para uma tabela."""
        return self.query("""
            SELECT
                c.column_name,
                c.data_type,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_pk
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema   = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_name      = %s
                  AND tc.table_schema    = 'public'
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_name   = %s
              AND c.table_schema = 'public'
            ORDER BY c.ordinal_position
        """, (table, table))

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
