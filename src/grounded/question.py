"""Deterministic policy-question and fact-slot analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum

from .temporal import DateFacts


class PolicyIntent(str, Enum):
    ELIGIBILITY = "eligibility"
    REPORTING_OBLIGATION = "reporting_obligation"
    DEADLINE = "deadline"
    EARNINGS_INCOME = "earnings_income"
    DISREGARD = "disregard"
    SANCTION = "sanction"
    AWARD_CALCULATION = "award_calculation"
    STUDENT_STATUS = "student_status"
    AMENDMENT_COMPARISON = "amendment_comparison"
    GENERAL_POLICY_LOOKUP = "general_policy_lookup"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExtractedFact:
    kind: str
    value: str
    raw_text: str
    role: str | None = None


@dataclass(frozen=True)
class SubQuestion:
    text: str
    intents: tuple[PolicyIntent, ...]


@dataclass(frozen=True)
class QuestionSpec:
    raw_question: str
    intents: tuple[PolicyIntent, ...]
    sub_questions: tuple[SubQuestion, ...]
    facts_present: tuple[ExtractedFact, ...]
    required_facts: tuple[str, ...]
    determination_date: date | None
    change_date: date | None
    reporting_date: date | None
    period_start: date | None
    period_end: date | None
    requested_version: str | None
    requested_provision: str | None
    missing_required_facts: tuple[str, ...]
    ambiguity_flags: tuple[str, ...]
    clarification_may_be_required: bool

    def to_date_facts(self) -> DateFacts:
        """Convert extracted temporal slots for the existing resolver."""

        return DateFacts(
            determination_date=self.determination_date,
            change_date=self.change_date,
            reporting_date=self.reporting_date,
            period_start=self.period_start,
            period_end=self.period_end,
        )


_DATE_RE = re.compile(
    r"(?P<iso>\b\d{4}-\d{2}-\d{2}\b)|"
    r"(?P<month_day>\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b)|"
    r"(?P<day_month>\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b)",
    re.IGNORECASE,
)
_PROVISION_RE = re.compile(r"(?:\u00a7\s*)?(\d+\.\d+(?:\.\d+)?)(?![\d])", re.IGNORECASE)
_MONEY_RE = re.compile(r"\$\s*\d(?:[\d,]*\d)?(?:\.\d+)?")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_MONTHS = {name.lower(): number for number, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
_DATE_CUE_RE = re.compile(r"\b(determination|determined|decision|decided|change|changed|occurred|happened|reported|reporting|notification|notified|period|from|between|to)\b", re.IGNORECASE)


def _parse_date(raw: str) -> date:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return date.fromisoformat(raw)
    cleaned = raw.replace(",", "")
    parts = cleaned.split()
    if parts[0].isalpha():
        month, day, year = parts[0].lower(), int(parts[1]), int(parts[2])
    else:
        day, month, year = int(parts[0]), parts[1].lower(), int(parts[2])
    return date(year, _MONTHS[month], day)


def _canonical_provision(value: str) -> str:
    return chr(0xA7) + value


def _date_occurrences(question: str):
    occurrences = []
    for match in _DATE_RE.finditer(question):
        raw = match.group(0)
        try:
            parsed = _parse_date(raw)
        except ValueError:
            continue
        occurrences.append((match.start(), match.end(), raw, parsed))
    return occurrences


def _date_role(question: str, start: int, end: int) -> tuple[str | None, str | None]:
    before = question[max(0, start - 70):start].lower()
    after = question[end:min(len(question), end + 70)].lower()
    window = before + " " + after
    if re.search(r"\b(reported|reporting|notification|notified)\b[^.;!?]{0,45}$", before):
        return "reporting_date", None
    if re.search(r"\b(determination|determined|decision|decided)\b[^.;!?]{0,45}$", before):
        return "determination_date", None
    if re.search(r"\b(change|changed|occurred|happened)\b[^.;!?]{0,45}$", before):
        return "change_date", None
    if re.search(r"\b(to|through|until)\b[^.;!?]{0,35}$", before) and re.search(r"\b(from|between)\b", before):
        return "period_end", None
    if re.search(r"\b(from|between)\b[^.;!?]{0,35}$", before):
        return "period_start", None
    roles: list[str] = []
    if re.search(r"\b(determination|determined|decision|decided)\b", window):
        roles.append("determination_date")
    if re.search(r"\b(change|changed|occurred|happened)\b", window):
        roles.append("change_date")
    if re.search(r"\b(reported|reporting|notification|notified)\b", window):
        roles.append("reporting_date")
    unique = tuple(dict.fromkeys(roles))
    if len(unique) == 1:
        return unique[0], None
    if len(unique) > 1:
        return None, "Date role is ambiguous: " + ", ".join(unique)
    return None, None


def _intents(text: str) -> tuple[PolicyIntent, ...]:
    lower = text.lower()
    found: list[PolicyIntent] = []
    def add(intent: PolicyIntent, condition: bool):
        if condition and intent not in found:
            found.append(intent)

    add(PolicyIntent.ELIGIBILITY, bool(re.search(r"\b(eligib|qualif|resident|residence|resource limit)\w*\b", lower)))
    add(PolicyIntent.REPORTING_OBLIGATION, bool(re.search(r"\b(report|reporting|notify|notification)\w*\b", lower) and re.search(r"\b(change|circumstance|days|deadline|failure)\w*\b", lower)))
    add(PolicyIntent.DEADLINE, bool(re.search(r"\b(days|deadline|time limit|how long|within)\b", lower)))
    add(PolicyIntent.EARNINGS_INCOME, bool(re.search(r"\b(earnings?|income|wages?|receipts?|self-employment)\b", lower)))
    add(PolicyIntent.DISREGARD, bool(re.search(r"\b(disregard|disregarded|ignore|excluded from income)\w*\b", lower)))
    add(PolicyIntent.SANCTION, "sanction" in lower or "penalty" in lower)
    add(PolicyIntent.AWARD_CALCULATION, bool(re.search(r"\b(award|calculate|calculation|needs figure|how much assistance|monthly amount)\b", lower)))
    add(PolicyIntent.STUDENT_STATUS, bool(re.search(r"\b(student|full-time education|higher education)\b", lower)))
    add(PolicyIntent.AMENDMENT_COMPARISON, bool(re.search(r"\b(amendment|amended|version|before|after|effective)\b", lower)))
    add(PolicyIntent.GENERAL_POLICY_LOOKUP, bool(re.search(r"\b(policy|manual|program|rule|provision|section)\b", lower)))
    return tuple(found) or (PolicyIntent.UNKNOWN,)


def _split_subquestions(question: str) -> tuple[str, ...]:
    parts = re.split(r"\s+and\s+(?=(?:when|how|what|whether|can|do|does|must|is|are|who|which)\b)|\s*;\s*", question, flags=re.IGNORECASE)
    cleaned = tuple(part.strip(" ,") for part in parts if part.strip(" ,"))
    return cleaned or (question.strip(),)


def analyze_question(question: str) -> QuestionSpec:
    """Build a deterministic QuestionSpec without answering the question."""

    raw = question.strip()
    intents = _intents(raw)
    subtexts = _split_subquestions(raw)
    subs = tuple(SubQuestion(text=text, intents=_intents(text)) for text in subtexts)
    facts: list[ExtractedFact] = []
    dates_by_role: dict[str, list[date]] = {}
    ambiguity: list[str] = []
    occurrences = _date_occurrences(raw)
    for start, end, date_text, parsed in occurrences:
        role, issue = _date_role(raw, start, end)
        facts.append(ExtractedFact("date", parsed.isoformat(), date_text, role))
        if issue:
            ambiguity.append(issue)
        elif role is None:
            ambiguity.append("Date role is ambiguous or not explicitly stated.")
        if role:
            dates_by_role.setdefault(role, []).append(parsed)

    requested = _PROVISION_RE.search(raw)
    requested_provision = _canonical_provision(requested.group(1)) if requested else None
    if requested and re.search(r"\b(section|provision)\b", raw, re.IGNORECASE):
        requested_provision = _canonical_provision(requested.group(1))
    version_match = re.search(r"\b(Amendment\s+No\.\s*[0-9]{4}-[0-9]{2}|amendment\s+[0-9]{4}-[0-9]{2})\b", raw, re.IGNORECASE)
    requested_version = version_match.group(1) if version_match else None
    if requested_provision:
        facts.append(ExtractedFact("provision", requested_provision, requested.group(0), "requested_provision"))
    if requested_version:
        facts.append(ExtractedFact("version", requested_version, version_match.group(0), "requested_version"))

    for match in _MONEY_RE.finditer(raw):
        facts.append(ExtractedFact("money", match.group(0).replace(" ", ""), match.group(0), None))
    money_spans = [(match.start(), match.end()) for match in _MONEY_RE.finditer(raw)]
    date_spans = [(start, end) for start, end, _, _ in occurrences]
    provision_span = (requested.start(), requested.end()) if requested else None
    for match in _NUMBER_RE.finditer(raw):
        if any(start <= match.start() < end for start, end in money_spans):
            continue
        if any(start <= match.start() < end for start, end in date_spans):
            continue
        if provision_span and provision_span[0] <= match.start() < provision_span[1]:
            continue
        facts.append(ExtractedFact("number", match.group(0), match.group(0), None))

    determination = dates_by_role.get("determination_date", [])
    change = dates_by_role.get("change_date", [])
    reporting = dates_by_role.get("reporting_date", [])
    period_start = dates_by_role.get("period_start", [])
    period_end = dates_by_role.get("period_end", [])
    if len(determination) > 1:
        ambiguity.append("Multiple determination dates were supplied.")
    if len(change) > 1:
        ambiguity.append("Multiple change dates were supplied.")
    if len(reporting) > 1:
        ambiguity.append("Multiple reporting dates were supplied.")
    if len(period_start) > 1 or len(period_end) > 1:
        ambiguity.append("Multiple period boundaries were supplied.")

    required: list[str] = []
    if PolicyIntent.REPORTING_OBLIGATION in intents or PolicyIntent.DEADLINE in intents:
        required.append("change_date")
    if any(intent in intents for intent in (PolicyIntent.EARNINGS_INCOME, PolicyIntent.DISREGARD, PolicyIntent.SANCTION, PolicyIntent.AWARD_CALCULATION, PolicyIntent.ELIGIBILITY, PolicyIntent.AMENDMENT_COMPARISON)):
        required.append("determination_date")
    if period_start or period_end or re.search(r"\b(period|from .* to|between .* and)\b", raw, re.IGNORECASE):
        required.extend(["period_start", "period_end"])
    required = list(dict.fromkeys(required))
    values = {
        "determination_date": determination,
        "change_date": change,
        "reporting_date": reporting,
        "period_start": period_start,
        "period_end": period_end,
    }
    missing = tuple(slot for slot in required if not values[slot])
    if missing:
        ambiguity.append("Required fact(s) not supplied: " + ", ".join(missing))
    if occurrences and not any(role for role in dates_by_role):
        ambiguity.append("The supplied date has no safely identifiable policy role.")

    return QuestionSpec(
        raw_question=raw,
        intents=intents,
        sub_questions=subs,
        facts_present=tuple(facts),
        required_facts=tuple(required),
        determination_date=determination[0] if determination else None,
        change_date=change[0] if change else None,
        reporting_date=reporting[0] if reporting else None,
        period_start=period_start[0] if period_start else None,
        period_end=period_end[0] if period_end else None,
        requested_version=requested_version,
        requested_provision=requested_provision,
        missing_required_facts=missing,
        ambiguity_flags=tuple(dict.fromkeys(ambiguity)),
        clarification_may_be_required=bool(missing or ambiguity),
    )
