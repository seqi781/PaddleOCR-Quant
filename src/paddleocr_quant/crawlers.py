from __future__ import annotations

from abc import ABC, abstractmethod

from paddleocr_quant.models import MarketCode, SampleFiling


class FilingSource(ABC):
    market: MarketCode

    @abstractmethod
    def list_sample_filings(self, ticker: str) -> list[SampleFiling]:
        raise NotImplementedError


class ChinaFilingSource(FilingSource):
    market: MarketCode = "CN_A"

    def list_sample_filings(self, ticker: str) -> list[SampleFiling]:
        normalized = ticker or "600519.SH"
        return [
            SampleFiling(
                market="CN_A",
                ticker=normalized,
                title="Kweichow Moutai 2025 Annual Report",
                report_type="annual_report",
                filing_date="2026-03-15",
                source_url="https://example.local/cn/600519.SH/annual-report",
                local_fixture="fixtures/financials/600519.SH_2025_AR.json",
            )
        ]


class HongKongFilingSource(FilingSource):
    market: MarketCode = "HK"

    def list_sample_filings(self, ticker: str) -> list[SampleFiling]:
        normalized = ticker or "0700.HK"
        return [
            SampleFiling(
                market="HK",
                ticker=normalized,
                title="Tencent Holdings 2025 Annual Report",
                report_type="annual_report",
                filing_date="2026-03-19",
                source_url="https://example.local/hk/0700.HK/annual-report",
                local_fixture="fixtures/financials/0700.HK_2025_AR.json",
            )
        ]


class UnitedStatesFilingSource(FilingSource):
    market: MarketCode = "US"

    def list_sample_filings(self, ticker: str) -> list[SampleFiling]:
        normalized = ticker or "AAPL"
        return [
            SampleFiling(
                market="US",
                ticker=normalized,
                title="Apple 2025 Form 10-K",
                report_type="10-K",
                filing_date="2025-11-01",
                source_url="https://example.local/us/AAPL/10-k",
                local_fixture="fixtures/financials/AAPL_2025_10K.json",
            )
        ]


class FilingSourceRegistry:
    def __init__(self) -> None:
        self._sources: dict[MarketCode, FilingSource] = {
            "CN_A": ChinaFilingSource(),
            "HK": HongKongFilingSource(),
            "US": UnitedStatesFilingSource(),
        }

    def list_sample_filings(self, market: MarketCode, ticker: str) -> list[SampleFiling]:
        return self._sources[market].list_sample_filings(ticker)
