from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PreparedPageImage(BaseModel):
    page_number: int
    image_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PDFInspectionResult(BaseModel):
    text_extractable: bool | None = None
    page_count: int | None = None
    extracted_text: str = ""
    warnings: list[str] = Field(default_factory=list)


class RasterizationResult(BaseModel):
    page_images: list[PreparedPageImage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PDFRasterizer(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def rasterize(
        self,
        pdf_path: str | Path,
        output_dir: str | Path,
        page_count_hint: int | None = None,
    ) -> RasterizationResult:
        raise NotImplementedError


def inspect_pdf_text(pdf_path: str | Path) -> PDFInspectionResult:
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
        )
    except Exception as exc:
        return PDFInspectionResult(
            text_extractable=None,
            warnings=[f"PDF text inspection failed: {exc}"],
        )


class PDF2ImageRasterizer(PDFRasterizer):
    name = "pdf2image"

    def __init__(self) -> None:
        self._pdftoppm_path = shutil.which("pdftoppm")

    def is_available(self) -> bool:
        try:
            from pdf2image import convert_from_path  # type: ignore  # noqa: F401
        except ImportError:
            return False
        return self._pdftoppm_path is not None

    def rasterize(
        self,
        pdf_path: str | Path,
        output_dir: str | Path,
        page_count_hint: int | None = None,
    ) -> RasterizationResult:
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        warnings: list[str] = []
        metadata: dict[str, Any] = {
            "engine": self.name,
            "poppler_pdftoppm_on_path": bool(self._pdftoppm_path),
        }

        try:
            from pdf2image import convert_from_path  # type: ignore
        except ImportError:
            warnings.append("Optional dependency `pdf2image` is not installed; real PDF rasterization is unavailable.")
            return _fallback_rasterization(
                page_count_hint=page_count_hint,
                warnings=warnings,
                metadata={**metadata, "status": "pdf2image_missing"},
            )

        if not self._pdftoppm_path:
            warnings.append("Poppler executable `pdftoppm` is not on PATH; `pdf2image` cannot rasterize PDFs.")
            return _fallback_rasterization(
                page_count_hint=page_count_hint,
                warnings=warnings,
                metadata={**metadata, "status": "poppler_missing"},
            )

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
                        metadata={
                            "rasterizer": self.name,
                            "engine": self.name,
                            "rendered": True,
                            "poppler_pdftoppm_on_path": True,
                        },
                    )
                )
            return RasterizationResult(
                page_images=page_images,
                metadata={
                    **metadata,
                    "status": "success",
                    "rendered_pages": len(page_images),
                },
            )
        except Exception as exc:
            warnings.append(f"PDF rasterization failed via `pdf2image`: {exc}")
            return _fallback_rasterization(
                page_count_hint=page_count_hint,
                warnings=warnings,
                metadata={**metadata, "status": "pdf2image_failed"},
            )


class PDFRasterizationService:
    def __init__(self, rasterizer: PDFRasterizer | None = None) -> None:
        self.rasterizer = rasterizer or PDF2ImageRasterizer()

    def rasterize(
        self,
        pdf_path: str | Path,
        output_dir: str | Path,
        page_count_hint: int | None = None,
    ) -> RasterizationResult:
        result = self.rasterizer.rasterize(pdf_path, output_dir, page_count_hint=page_count_hint)
        if result.page_images:
            return result
        if self.rasterizer.is_available():
            return result
        warnings = list(result.warnings)
        metadata = dict(result.metadata)
        if metadata.get("status") not in {"pdf2image_missing", "poppler_missing"}:
            if not _is_pdf2image_installed():
                warnings.append(
                    "Install optional dependency `pdf2image` to enable real PDF rasterization in OCR flows."
                )
                metadata["status"] = "pdf2image_missing"
            elif not shutil.which("pdftoppm"):
                warnings.append("Install Poppler and expose `pdftoppm` on PATH to enable PDF rasterization.")
                metadata["status"] = "poppler_missing"
        return _fallback_rasterization(
            page_count_hint=page_count_hint,
            warnings=warnings,
            metadata={
                "engine": self.rasterizer.name,
                "rendered_pages": 0,
                "poppler_pdftoppm_on_path": bool(shutil.which("pdftoppm")),
                **metadata,
            },
        )


def _fallback_rasterization(
    *,
    page_count_hint: int | None,
    warnings: list[str],
    metadata: dict[str, Any],
) -> RasterizationResult:
    page_total = page_count_hint or 1
    page_images = [
        PreparedPageImage(
            page_number=index,
            warnings=["No rendered page image available in the current environment."],
            metadata={**metadata, "rendered": False},
        )
        for index in range(1, page_total + 1)
    ]
    return RasterizationResult(
        page_images=page_images,
        warnings=_dedupe_preserve_order(warnings),
        metadata={
            "rendered_pages": 0,
            **metadata,
        },
    )


def _is_pdf2image_installed() -> bool:
    try:
        from pdf2image import convert_from_path  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
