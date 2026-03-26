from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from paddleocr_quant.models import CompanyMetricRecord, DocumentMetadata


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def put_json(self, key: str, payload: dict) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def get_json(self, key: str) -> dict:
        path = self.root / key
        return json.loads(path.read_text(encoding="utf-8"))


class SQLiteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    company_code TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    fiscal_year INTEGER NOT NULL,
                    report_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    source_fixture TEXT NOT NULL,
                    source_path TEXT,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS company_metrics (
                    company_code TEXT NOT NULL,
                    company_name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    fiscal_year INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    normalized_fields_json TEXT NOT NULL,
                    PRIMARY KEY (company_code, fiscal_year)
                )
                """
            )

    def insert_document(self, metadata: DocumentMetadata) -> DocumentMetadata:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, company_code, company_name, market, fiscal_year,
                    report_type, language, source_fixture, source_path, tags_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.document_id,
                    metadata.company_code,
                    metadata.company_name,
                    metadata.market,
                    metadata.fiscal_year,
                    metadata.report_type,
                    metadata.language,
                    metadata.source_fixture,
                    metadata.source_path,
                    json.dumps(metadata.tags, ensure_ascii=False),
                    metadata.created_at.isoformat(),
                ),
            )
        return metadata

    def get_document(self, document_id: str) -> DocumentMetadata | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["tags"] = json.loads(payload.pop("tags_json"))
        return DocumentMetadata.model_validate(payload)

    def upsert_company_metric(self, record: CompanyMetricRecord) -> CompanyMetricRecord:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO company_metrics (
                    company_code, company_name, market, fiscal_year, currency, normalized_fields_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_code, fiscal_year) DO UPDATE SET
                    company_name=excluded.company_name,
                    market=excluded.market,
                    currency=excluded.currency,
                    normalized_fields_json=excluded.normalized_fields_json
                """,
                (
                    record.company_code,
                    record.company_name,
                    record.market,
                    record.fiscal_year,
                    record.currency,
                    json.dumps([field.model_dump() for field in record.normalized_fields], ensure_ascii=False),
                ),
            )
        return record

    def get_company_metric(self, company_code: str, fiscal_year: int) -> CompanyMetricRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM company_metrics
                WHERE company_code = ? AND fiscal_year = ?
                """,
                (company_code, fiscal_year),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["normalized_fields"] = json.loads(payload.pop("normalized_fields_json"))
        return CompanyMetricRecord.model_validate(payload)

    def list_company_metrics(self, company_codes: list[str], fiscal_year: int) -> list[CompanyMetricRecord]:
        if not company_codes:
            return []
        placeholders = ",".join("?" for _ in company_codes)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM company_metrics
                WHERE fiscal_year = ? AND company_code IN ({placeholders})
                """,
                [fiscal_year, *company_codes],
            ).fetchall()
        records = []
        for row in rows:
            payload = dict(row)
            payload["normalized_fields"] = json.loads(payload.pop("normalized_fields_json"))
            records.append(CompanyMetricRecord.model_validate(payload))
        return records
