from fastapi.testclient import TestClient

from paddleocr_quant.api import app
from paddleocr_quant.bootstrap import build_container
from paddleocr_quant.seeds import seed_repository
from paddleocr_quant.settings import get_settings

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_documents_and_compare():
    settings = get_settings()
    container = build_container(settings)
    seed_repository(container.repo, container.fixtures_dir)

    compare_response = client.post(
        "/scores/compare",
        json={"company_codes": ["600519.SH", "0700.HK", "AAPL"], "fiscal_year": 2023},
    )
    assert compare_response.status_code == 200
    payload = compare_response.json()
    assert payload["fiscal_year"] == 2023
    assert len(payload["scores"]) == 3
