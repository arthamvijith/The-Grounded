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
    retrieval_kind: str = "direct"
    expanded_from: str | None = None
    expansion_reason: str | None = None
    expansion_depth: int = 0


@dataclass(frozen=True)
class _Candidate:
    score: float
    index: int
    item: _IndexedRecord
    matched_terms: tuple[str, ...]
    matched_signals: tuple[str, ...]
    retrieval_kind: str = "direct"
    expanded_from: str | None = None
    expansion_reason: str | None = None
    expansion_depth: int = 0


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

    def __init__(
        self,
        provisions: list[ProvisionRecord],
        amendments: list[AmendmentRecord] | None = None,
        index_artifact: list[dict] | None = None,
    ):
        if index_artifact is None:
            self._records = tuple(_provision_index(record) for record in provisions)
            self._records += tuple(_amendment_index(record) for record in (amendments or []))
        else:
            self._records = self._records_from_artifact(provisions, amendments or [], index_artifact)

    @staticmethod
    def _record_key(record: PolicyRecord) -> str:
        if isinstance(record, ProvisionRecord):
            return f"provision:{record.provision_no}"
        return f"amendment:{record.amendment_id}:{record.amendment_paragraph}"

    def export_index(self) -> list[dict]:
        """Serialize the already-built lexical index in stable record order."""

        return [
            {
                "body": item.body,
                "cross_references": list(item.cross_references),
                "heading": item.heading,
                "identifier": item.identifier,
                "record_key": self._record_key(item.record),
                "tokens": list(item.tokens),
            }
            for item in self._records
        ]

    @classmethod
    def _records_from_artifact(
        cls,
        provisions: list[ProvisionRecord],
        amendments: list[AmendmentRecord],
        payload: list[dict],
    ) -> tuple[_IndexedRecord, ...]:
        records = {cls._record_key(record): record for record in (*provisions, *amendments)}
        loaded: list[_IndexedRecord] = []
        for item in payload:
            record = records.get(item["record_key"])
            if record is None:
                raise ValueError(f"Search index references unknown record {item['record_key']}")
            tokens = tuple(item["tokens"])
            loaded.append(_IndexedRecord(
                record=record,
                body=item["body"],
                heading=item["heading"],
                tokens=tokens,
                token_set=frozenset(tokens),
                identifier=item["identifier"],
                cross_references=tuple(item["cross_references"]),
            ))
        if len(loaded) != len(records):
            raise ValueError("Search index does not contain every stored record")
        return tuple(loaded)

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
        return self._finalize_results(scored, query, top_k)

    def _finalize_results(self, scored, query: str, top_k: int) -> list[RetrievalResult]:
        """Add bounded one-hop related candidates and return stable results."""

        direct = [
            _Candidate(score, index, item, terms, signals)
            for score, index, item, terms, signals in scored
        ]
        direct_keys = {self._record_key(candidate.item.record) for candidate in direct}
        candidates = list(direct)
        seen_keys = set(direct_keys)

        index_by_target: dict[str, list[tuple[int, _IndexedRecord]]] = {}
        for index, item in enumerate(self._records):
            index_by_target.setdefault(self._record_label(item.record), []).append((index, item))

        # Only direct lexical hits are expansion seeds. This is a bounded
        # one-hop traversal and therefore cannot recurse through a reference
        # chain or cycle.
        seed_limit = max(top_k * 2, 10)
        for seed in direct[:seed_limit]:
            for target in seed.item.cross_references:
                for index, item in index_by_target.get(target, ()):
                    key = self._record_key(item.record)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    candidates.append(_Candidate(
                        score=1.0,
                        index=index,
                        item=item,
                        matched_terms=(),
                        matched_signals=("explicit_cross_reference",),
                        retrieval_kind="cross_reference",
                        expanded_from=self._record_label(seed.item.record),
                        expansion_reason=f"explicit_cross_reference:{target}",
                        expansion_depth=1,
                    ))

        candidates.sort(key=lambda candidate: (-candidate.score, candidate.index))
        selected = self._select_clause_coverage(candidates, query, top_k)
        return [
            RetrievalResult(
                record=candidate.item.record,
                relevance_score=candidate.score,
                matched_terms=candidate.matched_terms,
                matched_signals=candidate.matched_signals,
                rank=rank,
                cross_references=candidate.item.cross_references,
                retrieval_kind=candidate.retrieval_kind,
                expanded_from=candidate.expanded_from,
                expansion_reason=candidate.expansion_reason,
                expansion_depth=candidate.expansion_depth,
            )
            for rank, candidate in enumerate(selected, start=1)
        ]

    @staticmethod
    def _record_label(record: PolicyRecord) -> str:
        return record.provision_no if isinstance(record, ProvisionRecord) else record.target_provision

    @staticmethod
    def _query_clauses(query: str) -> tuple[frozenset[str], ...]:
        parts = tuple(
            part.strip()
            for part in re.split(r"(?:;|\band\b|\balso\b)", query, flags=re.IGNORECASE)
            if part.strip()
        )
        clauses = tuple(frozenset(tokenize(part)) for part in parts)
        return tuple(clause for clause in clauses if clause)

    @classmethod
    def _select_clause_coverage(
        cls,
        candidates: list[_Candidate],
        query: str,
        top_k: int,
    ) -> list[_Candidate]:
        clauses = cls._query_clauses(query)
        if len(clauses) <= 1:
            return candidates[:top_k]

        protected: list[_Candidate] = []
        protected_keys: set[str] = set()
        for clause in clauses:
            matching = [
                candidate for candidate in candidates
                if clause.intersection(candidate.matched_terms)
                and candidate.retrieval_kind == "direct"
            ]
            if not matching:
                continue
            best = matching[0]
            key = cls._record_key(best.item.record)
            if key not in protected_keys:
                protected.append(best)
                protected_keys.add(key)

        ordered = protected + [
            candidate for candidate in candidates
            if cls._record_key(candidate.item.record) not in protected_keys
        ]
        return ordered[:top_k]

    @staticmethod
    def _record_key(record: PolicyRecord) -> str:
        if isinstance(record, ProvisionRecord):
            return f"provision:{record.provision_no}"
        return f"amendment:{record.amendment_id}:{record.amendment_paragraph}"


def retrieve(
    query: str,
    provisions: list[ProvisionRecord],
    amendments: list[AmendmentRecord] | None = None,
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Convenience wrapper around :class:`LexicalRetriever`."""

    return LexicalRetriever(provisions, amendments).retrieve(query, top_k=top_k)
