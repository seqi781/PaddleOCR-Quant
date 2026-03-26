from __future__ import annotations

import re

from paddleocr_quant.models import Citation, QAResponse, SearchResult


def build_grounded_answer(document_id: str, question: str, search_result: SearchResult) -> QAResponse:
    citations = [
        Citation(
            chunk_id=chunk.chunk_id,
            seq=chunk.seq,
            snippet=_summarize_snippet(chunk.text),
        )
        for chunk in search_result.chunks
    ]
    if not citations:
        answer = "No grounded answer is available because no matching chunks were found."
    else:
        snippets = "; ".join(f"chunk {item.seq}: {item.snippet}" for item in citations)
        answer = f"Grounded answer based on retrieved text for '{question}': {snippets}"
    return QAResponse(
        document_id=document_id,
        question=question,
        answer=answer,
        citations=citations,
    )


def query_from_question(question: str) -> str:
    tokens = re.findall(r"[\w%.]+", question.lower())
    stopwords = {"what", "does", "the", "report", "say", "about", "and", "for", "with", "this", "that"}
    filtered = [token for token in tokens if len(token) > 2 and token not in stopwords]
    return " ".join(filtered[:4]) or question


def _summarize_snippet(text: str, max_len: int = 180) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_len:
        return compact
    return f"{compact[: max_len - 3]}..."
