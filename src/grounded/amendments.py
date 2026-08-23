"""Parsing and validation for independent amendment source files."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .models import AmendmentRecord, ApplicabilityRule, ProvisionRecord

_ISSUED_RE = re.compile(r"^\*\*Issued:\*\*\s*(.+)$")
_EFFECTIVE_RE = re.compile(r"^\*\*Effective:\*\*\s*(.+)$")
_AMENDMENT_RE = re.compile(r"^## Amendment No\.\s*(.+)$")
_PARAGRAPH_RE = re.compile(r"^\*\*(\d+(?:\.\d+)*)\*\*\s*(.*)$")
_TARGET_RE = re.compile(r"§\s*(\d+\.\d+(?:\.\d+)?)")
_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_MONTHS = {name: number for number, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}


def _parse_date(value: str) -> date:
    match = _DATE_RE.search(value)
    if not match or match.group(2) not in _MONTHS:
        raise ValueError(f"Could not parse date: {value!r}")
    return date(int(match.group(3)), _MONTHS[match.group(2)], int(match.group(1)))


def _first_group(lines: list[str], pattern: re.Pattern[str]) -> str | None:
    for line in lines:
        match = pattern.match(line.rstrip("\r\n"))
        if match:
            return match.group(1).strip()
    return None


def _applicability(paragraph: str, transition_5_3: str, effective_on: date) -> tuple[ApplicabilityRule, ...]:
    top = paragraph.split(".", 1)[0]
    if top in {"1", "3", "4"}:
        rules = [ApplicabilityRule(paragraph, "Paragraph 5.1: applies to determinations on or after the amendment effective date.", determination_on_or_after=effective_on)]
    elif top == "2":
        rules = [ApplicabilityRule(paragraph, "Paragraph 5.2: applies only to changes occurring on or after the amendment effective date.", change_on_or_after=effective_on)]
    else:
        rules = []
    if transition_5_3:
        rules.append(ApplicabilityRule("5.3", transition_5_3, covered_period_rule="Apply figures in force on each day of a period spanning the effective date and apportion."))
    return tuple(rules)


def parse_amendment(path: str | Path) -> list[AmendmentRecord]:
    """Parse amendment operations without applying them to the manual."""

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    amendment_id = _first_group(lines, _AMENDMENT_RE)
    issued_text = _first_group(lines, _ISSUED_RE)
    effective_text = _first_group(lines, _EFFECTIVE_RE)
    issued = _parse_date(issued_text) if issued_text else None
    effective = _parse_date(effective_text) if effective_text else None
    if not amendment_id or not issued or not effective:
        raise ValueError("Amendment must contain an ID, issued date, and effective date")

    offsets = _offsets(text)
    paragraphs = []
    for index, line in enumerate(lines):
        match = _PARAGRAPH_RE.match(line.rstrip("\r\n"))
        if match:
            paragraphs.append((index, match))
    transition_5_3 = ""
    for position, (start, match) in enumerate(paragraphs):
        if match.group(1) == "5.3":
            end = paragraphs[position + 1][0] if position + 1 < len(paragraphs) else len(lines)
            transition_5_3 = "".join(lines[start:end]).strip()

    records: list[AmendmentRecord] = []
    for position, (start, match) in enumerate(paragraphs):
        paragraph = match.group(1)
        statement = match.group(2)
        end = paragraphs[position + 1][0] if position + 1 < len(paragraphs) else len(lines)
        if paragraph in {"5.1", "5.2", "5.3"}:
            continue
        targets = tuple(dict.fromkeys(chr(0xA7) + value for value in _TARGET_RE.findall(statement)))
        if not targets:
            raise ValueError(f"Amendment paragraph {paragraph} has no target provision")
        operation, old_text, new_text, insertion_after = _operation_for(paragraph, statement, lines, start, end)
        records.append(AmendmentRecord(
            amendment_id=amendment_id,
            amendment_paragraph=paragraph,
            issued_on=issued,
            effective_on=effective,
            target_provision=targets[0] if operation != "insert" else chr(0xA7) + _inserted_number(lines, start, end),
            operation=operation,
            old_text=old_text,
            new_text=new_text,
            applicability=_applicability(paragraph, transition_5_3, effective),
            source_document=path.as_posix(),
            source_start=offsets[start],
            source_end=offsets[start] + len("".join(lines[start:end])),
            insertion_after=insertion_after,
        ))
    return records


def _operation_for(paragraph: str, statement: str, lines: list[str], start: int, end: int):
    block = "".join(lines[start:end]).strip()
    if "insert" in statement.lower():
        match = re.search(r"^>\s*\*\*(\d+\.\d+\.\d+[A-Z]?)\*\*\s+(.+?)(?=\n|$)", block, re.MULTILINE)
        if not match:
            raise ValueError(f"Could not parse insertion in amendment paragraph {paragraph}")
        after = next((chr(0xA7) + value for value in _TARGET_RE.findall(statement)), None)
        return "insert", None, match.group(2).strip(), after
    if "following" in statement.lower():
        return "replace_table", None, "".join(lines[start + 1:end]).strip(), None
    if "substitute" in statement.lower():
        before, new = statement.rsplit(" substitute ", 1)
        old_match = re.search(r'for ("[^"]+")', before)
        if not old_match:
            raise ValueError(f"Could not parse substitution in amendment paragraph {paragraph}")
        cleaned_new = new.strip().rstrip(".").strip().strip('"').strip("*").strip()
        return "substitute", old_match.group(1).strip('"'), cleaned_new, None
    raise ValueError(f"Unsupported amendment operation in paragraph {paragraph}: {statement}")


def _inserted_number(lines: list[str], start: int, end: int) -> str:
    block = "".join(lines[start:end]).strip()
    match = re.search(r"^>\s*\*\*(\d+\.\d+\.\d+[A-Z]?)\*\*", block, re.MULTILINE)
    if not match:
        raise ValueError("Insertion has no inserted provision number")
    return match.group(1)


def validate_amendment_targets(records: list[AmendmentRecord], provisions: list[ProvisionRecord]) -> None:
    """Validate targets and old-text integrity without mutating source records."""

    known = {provision.provision_no for provision in provisions}
    prior_text = {provision.provision_no: provision.original_text for provision in provisions}
    for record in records:
        if record.operation != "insert" and record.target_provision not in known:
            raise ValueError(f"Amendment {record.amendment_id} paragraph {record.amendment_paragraph} targets unknown provision {record.target_provision}")
        if record.operation == "insert" and record.insertion_after and record.insertion_after not in known:
            raise ValueError(f"Insertion {record.target_provision} follows unknown provision {record.insertion_after}")
        if record.old_text is not None:
            current = prior_text.get(record.target_provision)
            if current is None or record.old_text not in current:
                raise ValueError(
                    f"Amendment {record.amendment_id} paragraph {record.amendment_paragraph} "
                    f"old_text does not match target provision {record.target_provision}"
                )
            if record.operation == "substitute":
                prior_text[record.target_provision] = current.replace(record.old_text, record.new_text, 1)


def _offsets(text: str) -> list[int]:
    offsets = []
    current = 0
    for line in text.splitlines(keepends=True):
        offsets.append(current)
        current += len(line)
    return offsets
