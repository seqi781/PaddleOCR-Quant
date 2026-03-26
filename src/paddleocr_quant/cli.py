from __future__ import annotations

import json

import typer

from paddleocr_quant.bootstrap import build_container
from paddleocr_quant.scoring import score_company
from paddleocr_quant.seeds import seed_repository
from paddleocr_quant.settings import get_settings

app = typer.Typer(help="PaddleOCR-Quant local MVP CLI.")


@app.command("seed")
def seed_command() -> None:
    container = build_container(get_settings())
    records = seed_repository(container.repo, container.fixtures_dir)
    typer.echo(f"Seeded {len(records)} company metric records.")


@app.command("score")
def score_command(company_code: str, fiscal_year: int) -> None:
    container = build_container(get_settings())
    record = container.repo.get_company_metric(company_code, fiscal_year)
    if not record:
        raise typer.BadParameter(f"No metric found for {company_code} in {fiscal_year}")
    typer.echo(json.dumps(score_company(record).model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
