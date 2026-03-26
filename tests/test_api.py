def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_documents_and_compare(client, test_app):
    from paddleocr_quant.seeds import seed_repository

    seed_repository(test_app.state.container.repo, test_app.state.container.fixtures_dir)
    compare_response = client.post(
        "/scores/compare",
        json={"company_codes": ["600519.SH", "0700.HK", "AAPL"], "fiscal_year": 2023},
    )
    assert compare_response.status_code == 200
    payload = compare_response.json()
    assert payload["fiscal_year"] == 2023
    assert len(payload["scores"]) == 3


def test_local_ingest_parse_search_and_qa(client, tmp_path):
    source = tmp_path / "financials.txt"
    source.write_text(
        "Revenue 1200\nNet Profit 300\nOperating cash flow 260\nRevenue growth 12%\n",
        encoding="utf-8",
    )

    ingest_response = client.post(
        "/documents",
        json={
            "company_code": "AAPL",
            "company_name": "Apple",
            "market": "US",
            "fiscal_year": 2025,
            "report_type": "annual_report",
            "language": "en-US",
            "source_path": str(source),
            "source_fixture": None,
        },
    )
    assert ingest_response.status_code == 200
    metadata = ingest_response.json()
    assert metadata["source_type"] == "local"
    assert metadata["file_hash"]
    assert metadata["stored_path"].endswith(".txt")
    assert metadata["detected_extension"] == ".txt"

    document_id = metadata["document_id"]
    parse_response = client.post(f"/documents/{document_id}/parse")
    assert parse_response.status_code == 200
    parsed = parse_response.json()
    assert parsed["parser_name"] == "text-heuristic"
    assert parsed["chunks"]
    assert any(field["name"].lower() == "revenue" for field in parsed["extracted_fields"])

    search_response = client.get(f"/documents/{document_id}/search", params={"q": "revenue"})
    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload["total_hits"] >= 1
    assert "Revenue 1200" in search_payload["chunks"][0]["text"]

    qa_response = client.post(
        f"/documents/{document_id}/qa",
        json={"question": "What does the report say about revenue?", "top_k": 2},
    )
    assert qa_response.status_code == 200
    qa_payload = qa_response.json()
    assert qa_payload["citations"]
    assert "revenue" in qa_payload["answer"].lower()


def test_sample_filings_endpoint(client):
    response = client.get("/filings/sample", params={"market": "US", "ticker": "AAPL"})
    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["ticker"] == "AAPL"
    assert payload[0]["local_fixture"].endswith("AAPL_2025_10K.json")


def test_document_inspection_and_explicit_ocr_parse(client, tmp_path, monkeypatch):
    from paddleocr_quant.pdf import PDFInspectionResult

    source = tmp_path / "scanned.pdf"
    source.write_bytes(b"%PDF-1.4 scanned")

    ingest_response = client.post(
        "/documents",
        json={
            "company_code": "600519.SH",
            "company_name": "Moutai",
            "market": "CN_A",
            "fiscal_year": 2025,
            "report_type": "annual_report",
            "language": "zh-CN",
            "source_path": str(source),
            "source_fixture": None,
        },
    )
    assert ingest_response.status_code == 200
    document_id = ingest_response.json()["document_id"]

    monkeypatch.setattr(
        "paddleocr_quant.parser.inspect_pdf_text",
        lambda _path: PDFInspectionResult(text_extractable=False, page_count=1),
    )

    inspect_response = client.get(f"/documents/{document_id}/inspect")
    assert inspect_response.status_code == 200
    inspection = inspect_response.json()
    assert inspection["recommended_strategy"] == "ocr"
    assert inspection["page_count"] == 1

    parse_response = client.post(f"/documents/{document_id}/parse/ocr")
    assert parse_response.status_code == 200
    parsed = parse_response.json()
    assert parsed["strategy"] == "ocr"
    assert parsed["page_results"]
    assert any("PaddleOCR is not installed" in warning for warning in parsed["warnings"])
