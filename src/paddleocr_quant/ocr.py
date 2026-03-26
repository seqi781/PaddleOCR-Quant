from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from paddleocr_quant.models import OCRPageResult
from paddleocr_quant.pdf import PreparedPageImage


class OCRAdapterResult(BaseModel):
    adapter_name: str
    extracted_text: str = ""
    page_results: list[OCRPageResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OCRAdapter(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def run(self, page_images: list[PreparedPageImage]) -> OCRAdapterResult:
        raise NotImplementedError


class PaddleOCRAdapter(OCRAdapter):
    name = "paddleocr"

    def is_available(self) -> bool:
        try:
            from paddleocr import PaddleOCR  # type: ignore  # noqa: F401
        except ImportError:
            return False
        return True

    def run(self, page_images: list[PreparedPageImage]) -> OCRAdapterResult:
        page_results: list[OCRPageResult] = []
        if not self.is_available():
            warning = (
                "PaddleOCR is not installed in the current environment. "
                "Returning OCR fallback placeholders instead of crashing."
            )
            for page in page_images:
                page_warnings = [*page.warnings, warning]
                page_results.append(
                    OCRPageResult(
                        page_number=page.page_number,
                        status="unavailable",
                        image_path=page.image_path,
                        warnings=page_warnings,
                        metadata={"adapter": self.name, **page.metadata},
                    )
                )
            return OCRAdapterResult(adapter_name=self.name, page_results=page_results, warnings=[warning])

        try:
            from paddleocr import PaddleOCR  # type: ignore
        except ImportError:
            return OCRAdapterResult(
                adapter_name=self.name,
                warnings=["PaddleOCR import failed unexpectedly after availability check."],
            )

        try:
            ocr = PaddleOCR(use_angle_cls=True, lang="ch")
        except Exception as exc:
            warning = f"Failed to initialize PaddleOCR: {exc}"
            for page in page_images:
                page_results.append(
                    OCRPageResult(
                        page_number=page.page_number,
                        status="warning",
                        image_path=page.image_path,
                        warnings=[*page.warnings, warning],
                        metadata={"adapter": self.name, **page.metadata},
                    )
                )
            return OCRAdapterResult(adapter_name=self.name, page_results=page_results, warnings=[warning])

        page_texts: list[str] = []
        warnings: list[str] = []
        for page in page_images:
            if not page.image_path or not Path(page.image_path).exists():
                warning = "OCR skipped because no rendered page image is available."
                warnings.append(warning)
                page_results.append(
                    OCRPageResult(
                        page_number=page.page_number,
                        status="warning",
                        image_path=page.image_path,
                        warnings=[*page.warnings, warning],
                        metadata={"adapter": self.name, **page.metadata},
                    )
                )
                continue

            try:
                raw_result = ocr.ocr(page.image_path, cls=True)
                lines: list[str] = []
                for block in raw_result or []:
                    for line in block or []:
                        if len(line) >= 2 and isinstance(line[1], (list, tuple)) and line[1]:
                            text = str(line[1][0]).strip()
                            if text:
                                lines.append(text)
                extracted_text = "\n".join(lines)
                page_texts.append(extracted_text)
                page_results.append(
                    OCRPageResult(
                        page_number=page.page_number,
                        status="success" if extracted_text else "warning",
                        image_path=page.image_path,
                        extracted_text=extracted_text,
                        warnings=page.warnings,
                        metadata={"adapter": self.name, "line_count": str(len(lines)), **page.metadata},
                    )
                )
            except Exception as exc:
                warning = f"OCR failed for page {page.page_number}: {exc}"
                warnings.append(warning)
                page_results.append(
                    OCRPageResult(
                        page_number=page.page_number,
                        status="warning",
                        image_path=page.image_path,
                        warnings=[*page.warnings, warning],
                        metadata={"adapter": self.name, **page.metadata},
                    )
                )

        return OCRAdapterResult(
            adapter_name=self.name,
            extracted_text="\n\n".join(part for part in page_texts if part).strip(),
            page_results=page_results,
            warnings=warnings,
        )
