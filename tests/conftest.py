from __future__ import annotations

from pathlib import Path

import pytest

from paddleocr_quant.main import create_app
from paddleocr_quant.settings import Settings


@pytest.fixture()
def test_app(tmp_path: Path):
    settings = Settings(
        app_env="test",
        data_dir=tmp_path,
        db_path=tmp_path / "test.db",
        object_store_root=tmp_path / "object_store",
    )
    app = create_app(settings)
    return app
