"""Inspect deterministic QuestionSpec extraction."""

from dataclasses import asdict
from pathlib import Path
import pprint
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grounded.question import analyze_question


questions = (
    "What is the household resource limit?",
    "What does §4.3.2 say?",
    "What is the earnings disregard for a determination on 1 March 2026?",
    "What is the earnings disregard and when must I report a change?",
    "How many days must I report a change?",
    "Can I disregard $175, and does the $4,000 resource limit apply?",
)

for question in questions:
    print(f"\nQUESTION: {question}")
    pprint.pprint(asdict(analyze_question(question)), sort_dicts=False, width=120)
