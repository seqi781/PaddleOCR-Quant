from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from paddleocr_quant.models import DocumentMetadata, DocumentMetadataIn
from paddleocr_quant.storage import LocalObjectStore


def build_document_metadata(
    payload: DocumentMetadataIn,
    object_store: LocalObjectStore,
) -> DocumentMetadata:
    metadata = DocumentMetadata(**payload.model_dump())
    if payload.source_path:
        source_path = Path(payload.source_path).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise FileNotFoundError(f"Local file not found: {source_path}")
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        suffix = source_path.suffix.lower()
        stored_path = object_store.put_file(source_path, f"raw/{digest}{suffix}")
        mime_type, _ = mimetypes.guess_type(str(source_path))
        metadata.source_type = "local"
        metadata.source_fixture = None
        metadata.source_path = str(source_path)
        metadata.file_hash = digest
        metadata.stored_path = str(stored_path)
        metadata.detected_extension = suffix or None
        metadata.mime_type = mime_type or "application/octet-stream"
        return metadata

    if not metadata.source_fixture:
        raise ValueError("Either source_path or source_fixture must be provided.")

    metadata.source_type = "fixture"
    if metadata.source_fixture:
        metadata.detected_extension = Path(metadata.source_fixture).suffix.lower() or ".json"
    return metadata
