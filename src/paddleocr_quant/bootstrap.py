from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from paddleocr_quant.parser import MockPaddleOCRParser
from paddleocr_quant.settings import Settings
from paddleocr_quant.storage import LocalObjectStore, SQLiteRepository


@dataclass
class Container:
    settings: Settings
    repo: SQLiteRepository
    object_store: LocalObjectStore
    parser: MockPaddleOCRParser
    fixtures_dir: Path


def build_container(settings: Settings) -> Container:
    fixtures_dir = Path(__file__).resolve().parents[2] / "fixtures"
    repo = SQLiteRepository(settings.db_path)
    object_store = LocalObjectStore(settings.object_store_root)
    parser = MockPaddleOCRParser(fixtures_dir=fixtures_dir)
    return Container(
        settings=settings,
        repo=repo,
        object_store=object_store,
        parser=parser,
        fixtures_dir=fixtures_dir,
    )
