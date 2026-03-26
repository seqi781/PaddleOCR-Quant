from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from paddleocr_quant.models import CompanyMetricRecord, DocumentMetadata, ParseResult, SearchResult, TextChunk


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

    def put_file(self, source_path: Path, key: str) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, path)
        return path


class SQLiteRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        with self._connect() as conn:
            columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

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
                    source_fixture TEXT,
                    source_path TEXT,
                    parser_hint TEXT,
                    source_type TEXT NOT NULL DEFAULT 'fixture',
                    file_hash TEXT,
                    stored_path TEXT,
                    detected_extension TEXT,
                    mime_type TEXT,
                    parser_name TEXT,
                    parsed_at TEXT,
                    tags_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS parsed_documents (
                    document_id TEXT PRIMARY KEY,
                    parser_name TEXT NOT NULL,
                    strategy TEXT NOT NULL DEFAULT 'text',
                    extracted_text TEXT NOT NULL,
                    extracted_fields_json TEXT NOT NULL,
                    page_results_json TEXT NOT NULL DEFAULT '[]',
                    warnings_json TEXT NOT NULL,
                    parsed_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
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
        self._ensure_column("documents", "parser_hint", "TEXT")
        self._ensure_column("documents", "source_type", "TEXT NOT NULL DEFAULT 'fixture'")
        self._ensure_column("documents", "file_hash", "TEXT")
        self._ensure_column("documents", "stored_path", "TEXT")
        self._ensure_column("documents", "detected_extension", "TEXT")
        self._ensure_column("documents", "mime_type", "TEXT")
        self._ensure_column("documents", "parser_name", "TEXT")
        self._ensure_column("documents", "parsed_at", "TEXT")
        self._ensure_column("parsed_documents", "strategy", "TEXT NOT NULL DEFAULT 'text'")
        self._ensure_column("parsed_documents", "page_results_json", "TEXT NOT NULL DEFAULT '[]'")

    def insert_document(self, metadata: DocumentMetadata) -> DocumentMetadata:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    document_id, company_code, company_name, market, fiscal_year,
                    report_type, language, source_fixture, source_path, parser_hint, source_type,
                    file_hash, stored_path, detected_extension, mime_type, parser_name, parsed_at,
                    tags_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    metadata.parser_hint,
                    metadata.source_type,
                    metadata.file_hash,
                    metadata.stored_path,
                    metadata.detected_extension,
                    metadata.mime_type,
                    metadata.parser_name,
                    metadata.parsed_at.isoformat() if metadata.parsed_at else None,
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

    def update_document_parse_status(
        self,
        document_id: str,
        parser_name: str,
        parsed_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE documents
                SET parser_name = ?, parsed_at = ?
                WHERE document_id = ?
                """,
                (parser_name, parsed_at, document_id),
            )

    def upsert_parse_result(self, result: ParseResult) -> ParseResult:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO parsed_documents (
                    document_id, parser_name, strategy, extracted_text, extracted_fields_json,
                    page_results_json, warnings_json, parsed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(document_id) DO UPDATE SET
                    parser_name=excluded.parser_name,
                    strategy=excluded.strategy,
                    extracted_text=excluded.extracted_text,
                    extracted_fields_json=excluded.extracted_fields_json,
                    page_results_json=excluded.page_results_json,
                    warnings_json=excluded.warnings_json,
                    parsed_at=CURRENT_TIMESTAMP
                """,
                (
                    result.document_id,
                    result.parser_name,
                    result.strategy,
                    result.extracted_text,
                    json.dumps([field.model_dump() for field in result.extracted_fields], ensure_ascii=False),
                    json.dumps([page.model_dump() for page in result.page_results], ensure_ascii=False),
                    json.dumps(result.warnings, ensure_ascii=False),
                ),
            )
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (result.document_id,))
            conn.executemany(
                """
                INSERT INTO document_chunks (chunk_id, document_id, seq, text, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.seq,
                        chunk.text,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                    )
                    for chunk in result.chunks
                ],
            )
        return result

    def list_document_chunks(self, document_id: str) -> list[TextChunk]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM document_chunks
                WHERE document_id = ?
                ORDER BY seq ASC
                """,
                (document_id,),
            ).fetchall()
        return [
            TextChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                seq=row["seq"],
                text=row["text"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        ]

    def search_chunks(self, document_id: str, query: str, limit: int = 5) -> SearchResult:
        needle = query.strip().lower()
        if not needle:
            return SearchResult(document_id=document_id, query=query, total_hits=0, chunks=[])
        terms = [term for term in needle.split() if term]
        matches: list[TextChunk] = []
        for chunk in self.list_document_chunks(document_id):
            haystack = chunk.text.lower()
            occurrences = sum(haystack.count(term) for term in terms) if terms else haystack.count(needle)
            if occurrences == 0:
                continue
            chunk.score = float(occurrences)
            matches.append(chunk)
        ranked = sorted(matches, key=lambda item: (item.score, -item.seq), reverse=True)
        return SearchResult(
            document_id=document_id,
            query=query,
            total_hits=len(matches),
            chunks=ranked[:limit],
        )

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
