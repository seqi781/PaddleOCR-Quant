from __future__ import annotations

import json
from pathlib import Path

from paddleocr_quant.models import CompanyMetricRecord
from paddleocr_quant.storage import SQLiteRepository


def load_seed_records(fixtures_dir: Path) -> list[CompanyMetricRecord]:
    payload = json.loads((fixtures_dir / "seed_company_metrics.json").read_text(encoding="utf-8"))
    return [CompanyMetricRecord.model_validate(item) for item in payload]


def seed_repository(repo: SQLiteRepository, fixtures_dir: Path) -> list[CompanyMetricRecord]:
    records = load_seed_records(fixtures_dir)
    for record in records:
        repo.upsert_company_metric(record)
    return records
