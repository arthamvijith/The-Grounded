"""Deterministic lexical retrieval over policy provisions and amendments.

This module returns evidence candidates only. It does not apply amendments,
resolve conflicts, decide applicability, or determine whether a candidate is
sufficient authority for an answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TypeAlias

from .models import AmendmentRecord, ProvisionRecord

PolicyRecord: TypeAlias = ProvisionRecord | AmendmentRecord

_TOKEN_RE = re.compile(
    r"(?:§\s*)?\d+(?:\.\d+){1,2}|\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|\$?\d[\d,]*(?:\.\d+)?|[a-z]+(?:-[a-z]+)?",
    re.IGNORECASE,
)
_PROVISION_ID_RE = re.compile(r"^§?\s*(\d+\.\d+(?:\.\d+)?)$", re.IGNORECASE)
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "be", "by", "can", "do", "does", "for", "from",
    "how", "if", "in", "is", "it", "me", "must", "of", "on", "or", "the", "to",
    "what", "when", "where", "which", "who", "with", "would",
})


@dataclass(frozen=True)
class RetrievalResult:
    """One ranked candidate returned by retrieval."""

    record: PolicyRecord
    relevance_score: float
    matched_terms: tuple[str, ...]
    matched_signals: tuple[str, ...]
    rank: int
    cross_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class _IndexedRecord:
    record: PolicyRecord
    body: str
    heading: str
    tokens: tuple[str, ...]
    token_set: frozenset[str]
    identifier: str | None
    cross_references: tuple[str, ...]


def tokenize(text: str) -> tuple[str, ...]:
    """Return conservative, lower-case lexical tokens.

    Provision identifiers, numeric values, and dates remain intact as tokens;
    ordinary punctuation and Markdown markers are ignored. No stemming or
    synonym expansion is performed.
    """

    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).lower().replace(" ", "")
        token = token.lstrip("§$")
        if token and token not in _STOPWORDS:
            tokens.append(token)
    return tuple(tokens)


def _identifier(text: str) -> str | None:
    match = _PROVISION_ID_RE.match(text.strip())
    return match.group(1) if match else None


def _provision_index(record: ProvisionRecord) -> _IndexedRecord:
    heading = " ".join(part for part in (record.part_heading, record.section_heading) if part)
    body = f"{record.provision_no} {heading} {record.original_text}"
    return _IndexedRecord(
        record=record,
        body=body,
        heading=heading,
        tokens=tokenize(body),
        token_set=frozenset(tokenize(body)),
        identifier=_identifier(record.provision_no),
        cross_references=record.cross_references,
    )


def _amendment_index(record: AmendmentRecord) -> _IndexedRecord:
    applicability = " ".join(rule.raw_text for rule in record.applicability)
    body = " ".join([
        record.amendment_id,
        record.amendment_paragraph,
        record.target_provision,
        record.operation,
        record.old_text or "",
        record.new_text,
        record.issued_on.isoformat(),
        record.effective_on.isoformat(),
        applicability,
    ])
    return _IndexedRecord(
        record=record,
        body=body,
        heading=f"Amendment {record.amendment_id} paragraph {record.amendment_paragraph}",
        tokens=tokenize(body),
        token_set=frozenset(tokenize(body)),
        identifier=_identifier(record.target_provision),
        cross_references=(record.target_provision,),
    )


class LexicalRetriever:
    """In-memory deterministic lexical retriever for source records."""

    def __init__(self, provisions: list[ProvisionRecord], amendments: list[AmendmentRecord] | None = None):
        self._records = tuple(_provision_index(record) for record in provisions)
        self._records += tuple(_amendment_index(record) for record in (amendments or []))

    def retrieve(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        """Return ranked non-zero candidates without applying policy changes."""

        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        query_tokens = tokenize(query)
        query_set = frozenset(query_tokens)
        query_ids = {token for token in query_tokens if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", token)}
        query_text = " ".join(query_tokens)
        scored: list[tuple[float, int, _IndexedRecord, tuple[str, ...], tuple[str, ...]]] = []

        for index, item in enumerate(self._records):
            overlap = query_set & item.token_set
            if not overlap:
                continue
            score = 0.0
            signals: list[str] = []
            matched_terms = tuple(sorted(overlap))

            word_overlap = [token for token in overlap if not re.fullmatch(r"\d+(?:\.\d+){1,2}|\d[\d,]*(?:\.\d+)?", token)]
            numeric_overlap = [token for token in overlap if token not in word_overlap]
            if word_overlap:
                score += len(word_overlap)
                signals.append(f"term_overlap:{len(word_overlap)}")
            if numeric_overlap:
                score += 4 * len(numeric_overlap)
                signals.append(f"numeric_overlap:{len(numeric_overlap)}")

            if query_ids and item.identifier and item.identifier in query_ids:
                score += 20
                label = item.record.provision_no if isinstance(item.record, ProvisionRecord) else item.record.target_provision
                signals.append(f"exact_provision:{label}")

            heading_tokens = set(tokenize(item.heading))
            heading_hits = query_set & heading_tokens
            if heading_hits:
                score += 2 * len(heading_hits)
                signals.append(f"heading_overlap:{len(heading_hits)}")

            if len(query_tokens) >= 2 and query_text in " ".join(item.tokens):
                score += 5
                signals.append("exact_token_phrase")

            if isinstance(item.record, ProvisionRecord):
                referenced = set(item.cross_references)
                queried_refs = {"§" + token for token in query_ids}
                if referenced & queried_refs:
                    score += 8
                    signals.append("cross_reference_match")

            scored.append((score, index, item, matched_terms, tuple(signals)))

        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        return [
            RetrievalResult(
                record=item.record,
                relevance_score=score,
                matched_terms=terms,
                matched_signals=signals,
                rank=rank,
                cross_references=item.cross_references,
            )
            for rank, (score, _, item, terms, signals) in enumerate(scored[:top_k], start=1)
        ]


def retrieve(
    query: str,
    provisions: list[ProvisionRecord],
    amendments: list[AmendmentRecord] | None = None,
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Convenience wrapper around :class:`LexicalRetriever`."""

    return LexicalRetriever(provisions, amendments).retrieve(query, top_k=top_k)
