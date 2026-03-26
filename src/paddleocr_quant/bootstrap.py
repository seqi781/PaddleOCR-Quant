from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from paddleocr_quant.crawlers import FilingSourceRegistry
from paddleocr_quant.parser import ParserRegistry
from paddleocr_quant.settings import Settings
from paddleocr_quant.storage import LocalObjectStore, SQLiteRepository


@dataclass
class Container:
    settings: Settings
    repo: SQLiteRepository
    object_store: LocalObjectStore
    parser_registry: ParserRegistry
    filing_sources: FilingSourceRegistry
    fixtures_dir: Path


def build_container(settings: Settings) -> Container:
    fixtures_dir = Path(__file__).resolve().parents[2] / "fixtures"
    repo = SQLiteRepository(settings.db_path)
    object_store = LocalObjectStore(settings.object_store_root)
    parser_registry = ParserRegistry(fixtures_dir=fixtures_dir, object_store_root=object_store.root)
    filing_sources = FilingSourceRegistry()
    return Container(
        settings=settings,
        repo=repo,
        object_store=object_store,
        parser_registry=parser_registry,
        filing_sources=filing_sources,
        fixtures_dir=fixtures_dir,
    )
