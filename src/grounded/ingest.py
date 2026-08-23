"""Provision-level ingestion for the original policy manual."""

from __future__ import annotations

import re
from pathlib import Path

from .models import ProvisionRecord

_PROVISION_RE = re.compile(r"^\*\*(?P<number>\d+\.\d+\.\d+)\*\*(?P<body>.*)$")
_PART_RE = re.compile(r"^# Part (?P<number>\d+)\b")
_SECTION_RE = re.compile(r"^## (?P<number>\d+\.\d+)\s+(?P<title>.+?)\s*$")
_CROSS_REF_RE = re.compile(r"§\s*(\d+\.\d+(?:\.\d+)?)")


def _line_offsets(text: str) -> list[int]:
    offsets: list[int] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        offsets.append(offset)
        offset += len(line)
    if not offsets or offset < len(text):
        offsets.append(offset)
    return offsets


def parse_policy_manual(path: str | Path) -> list[ProvisionRecord]:
    """Parse the original manual into one record per numbered provision."""

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    offsets = _line_offsets(text)
    starts: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = _PROVISION_RE.match(line.rstrip("\r\n"))
        if match:
            starts.append((index, match))

    records: list[ProvisionRecord] = []
    for position, (start_line, match) in enumerate(starts):
        end_line = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        raw_text = "".join(lines[start_line:end_line])
        body_lines = [match.group("body")] + [line.rstrip("\r\n") for line in lines[start_line + 1:end_line]]
        original_text = "\n".join(body_lines).rstrip("\n")
        provision_no = chr(0xA7) + match.group("number")
        references = tuple(dict.fromkeys(chr(0xA7) + ref for ref in _CROSS_REF_RE.findall(original_text)))
        part, part_heading, section, section_heading = _context_at_line(lines, start_line)
        source_start = offsets[start_line]
        records.append(ProvisionRecord(
            provision_no=provision_no,
            original_text=original_text,
            source_document=path.as_posix(),
            part=part,
            part_heading=part_heading,
            section=section,
            section_heading=section_heading,
            source_start=source_start,
            source_end=source_start + len(raw_text),
            raw_text=raw_text,
            cross_references=references,
        ))
    return records


def _context_at_line(lines: list[str], target: int):
    part = None
    part_heading = None
    section = None
    section_heading = None
    for line in lines[:target + 1]:
        content = line.rstrip("\r\n")
        part_match = _PART_RE.match(content)
        if part_match:
            part = int(part_match.group("number"))
            part_heading = content
            section = None
            section_heading = None
        section_match = _SECTION_RE.match(content)
        if section_match:
            section = section_match.group("number")
            section_heading = content
    return part, part_heading, section, section_heading
