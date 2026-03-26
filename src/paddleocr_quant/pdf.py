from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel, Field


class PreparedPageImage(BaseModel):
    page_number: int
    image_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class PDFInspectionResult(BaseModel):
    text_extractable: bool | None = None
    page_count: int | None = None
    extracted_text: str = ""
    warnings: list[str] = Field(default_factory=list)


class PageImagePreparationResult(BaseModel):
    page_images: list[PreparedPageImage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def inspect_pdf_text(pdf_path: str | Path) -> PDFInspectionResult:
    warnings: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return PDFInspectionResult(
            text_extractable=None,
            warnings=["PDF text inspection requires optional dependency `pypdf`."],
        )

    try:
        reader = PdfReader(str(pdf_path))
        texts: list[str] = []
        for page in reader.pages:
            texts.append((page.extract_text() or "").strip())
        extracted_text = "\n".join(part for part in texts if part).strip()
        return PDFInspectionResult(
            text_extractable=bool(extracted_text),
            page_count=len(reader.pages),
            extracted_text=extracted_text,
            warnings=warnings,
        )
    except Exception as exc:
        return PDFInspectionResult(
            text_extractable=None,
            warnings=[f"PDF text inspection failed: {exc}"],
        )


def prepare_pdf_page_images(
    pdf_path: str | Path,
    output_dir: str | Path,
    page_count_hint: int | None = None,
) -> PageImagePreparationResult:
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    warnings: list[str] = []

    try:
        from pdf2image import convert_from_path  # type: ignore
    except ImportError:
        convert_from_path = None

    if convert_from_path is not None:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            images = convert_from_path(str(pdf_path))
            page_images: list[PreparedPageImage] = []
            for index, image in enumerate(images, start=1):
                image_path = output_dir / f"page-{index:04d}.png"
                image.save(image_path, "PNG")
                page_images.append(
                    PreparedPageImage(
                        page_number=index,
                        image_path=str(image_path),
                        metadata={"source": "pdf2image"},
                    )
                )
            return PageImagePreparationResult(page_images=page_images)
        except Exception as exc:
            warnings.append(f"PDF page image preparation failed via `pdf2image`: {exc}")

    if shutil.which("pdftoppm"):
        warnings.append(
            "Poppler command `pdftoppm` is available, but this project does not invoke it automatically "
            "in lightweight mode."
        )
    else:
        warnings.append(
            "PDF page image preparation is unavailable: install optional `pdf2image` with Poppler on PATH "
            "for real rasterization."
        )

    page_total = page_count_hint or 1
    page_images = [
        PreparedPageImage(
            page_number=index,
            warnings=["No rendered page image available in the current environment."],
        )
        for index in range(1, page_total + 1)
    ]
    return PageImagePreparationResult(page_images=page_images, warnings=warnings)
