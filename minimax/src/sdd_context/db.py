from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

import pymysql
from pymysql.cursors import DictCursor

from .config import Settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS materials (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  kind VARCHAR(32) NOT NULL,
  path VARCHAR(512) NOT NULL,
  title VARCHAR(256) NOT NULL,
  content LONGTEXT NOT NULL,
  version VARCHAR(64) NOT NULL DEFAULT 'v1',
  tags VARCHAR(512) NOT NULL DEFAULT '',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_kind_path_version (kind, path, version)
);

CREATE TABLE IF NOT EXISTS query_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  purpose VARCHAR(128) NOT NULL,
  sql_text TEXT NOT NULL,
  row_count INT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class SeekDB:
    def __init__(self, settings: Settings):
        self.settings = settings

    def connect(self):
        return pymysql.connect(
            host=self.settings.seekdb_host,
            port=self.settings.seekdb_port,
            user=self.settings.seekdb_user,
            password=self.settings.seekdb_password,
            database=self.settings.seekdb_database,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )

    def init_schema(self) -> None:
        # Ensure DB exists (connect without database first)
        raw = pymysql.connect(
            host=self.settings.seekdb_host,
            port=self.settings.seekdb_port,
            user=self.settings.seekdb_user,
            password=self.settings.seekdb_password,
            charset="utf8mb4",
            autocommit=True,
        )
        try:
            with raw.cursor() as cur:
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.settings.seekdb_database}`"
                )
        finally:
            raw.close()

        with self.connect() as conn:
            with conn.cursor() as cur:
                for stmt in SCHEMA_SQL.strip().split(";"):
                    s = stmt.strip()
                    if s:
                        cur.execute(s)

    def reset_materials(self) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM materials")
                cur.execute("DELETE FROM query_log")

    def upsert_material(
        self,
        *,
        kind: str,
        path: str,
        title: str,
        content: str,
        version: str = "v1",
        tags: str = "",
    ) -> None:
        sql = """
        INSERT INTO materials (kind, path, title, content, version, tags)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          title=VALUES(title),
          content=VALUES(content),
          tags=VALUES(tags),
          updated_at=CURRENT_TIMESTAMP
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (kind, path, title, content, version, tags))

    def _log_query(self, purpose: str, sql_text: str, row_count: int) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO query_log (purpose, sql_text, row_count) VALUES (%s,%s,%s)",
                    (purpose, sql_text, row_count),
                )

    def query_materials(
        self, *, kinds: Iterable[str] | None = None, version: str | None = None
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        if kinds:
            kinds_list = list(kinds)
            placeholders = ",".join(["%s"] * len(kinds_list))
            clauses.append(f"kind IN ({placeholders})")
            params.extend(kinds_list)
        if version:
            clauses.append("version = %s")
            params.append(version)
        sql = (
            "SELECT id, kind, path, title, content, version, tags, updated_at "
            f"FROM materials WHERE {' AND '.join(clauses)} "
            "ORDER BY kind, path, version"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = list(cur.fetchall())
        self._log_query(
            purpose="assemble_context",
            sql_text=sql + " | params=" + json.dumps(params, ensure_ascii=False),
            row_count=len(rows),
        )
        return rows

    def latest_applicable_specs(self) -> list[dict[str, Any]]:
        """Pick highest version per path for kind=spec."""
        sql = """
        SELECT m.*
        FROM materials m
        INNER JOIN (
          SELECT path, MAX(version) AS max_version
          FROM materials
          WHERE kind = 'spec'
          GROUP BY path
        ) t ON m.path = t.path AND m.version = t.max_version
        WHERE m.kind = 'spec'
        ORDER BY m.path
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = list(cur.fetchall())
        self._log_query(purpose="latest_specs", sql_text=sql, row_count=len(rows))
        return rows

    def dump_query_log(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, purpose, sql_text, row_count, created_at FROM query_log ORDER BY id"
                )
                return list(cur.fetchall())
