from __future__ import annotations

from paddleocr_quant.extraction import CANONICAL_FIELD_LABELS, FIELD_ALIASES
from paddleocr_quant.models import NormalizedField, ParsedField


def normalize_field_name(name: str) -> tuple[str, str, str]:
    key = name.strip().lower()
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]
    return (key.replace(" ", "_"), name, name)


def normalize_fields(fields: list[ParsedField]) -> list[NormalizedField]:
    normalized: list[NormalizedField] = []
    for field in fields:
        if field.canonical_code and field.canonical_code in CANONICAL_FIELD_LABELS:
            label_zh, label_en = CANONICAL_FIELD_LABELS[field.canonical_code]
            canonical_code = field.canonical_code
        else:
            canonical_code, label_zh, label_en = normalize_field_name(field.name)
        normalized.append(
            NormalizedField(
                canonical_code=canonical_code,
                label_zh=label_zh,
                label_en=label_en,
                value=field.value,
                unit=field.unit,
                source_name=field.name,
            )
        )
    return normalized
