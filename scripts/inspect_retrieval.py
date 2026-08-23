"""Inspect deterministic retrieval for representative policy questions."""

from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grounded.amendments import parse_amendment
from grounded.ingest import parse_policy_manual
from grounded.retrieval import LexicalRetriever


root = Path(__file__).resolve().parents[1]
provisions = parse_policy_manual(root / "source/original/policy-manual.md")
amendments = parse_amendment(root / "source/amendment/Amendment No. 2026-01.md")
retriever = LexicalRetriever(provisions, amendments)
section = chr(0xA7)

for question in (section + "4.3.2", "How many days must I report a change?", "What changes on 1 March 2026?"):
    print(f"\nQUERY: {question}")
    for result in retriever.retrieve(question, top_k=5):
        if hasattr(result.record, "provision_no"):
            label = result.record.provision_no
        else:
            label = f"Amendment {result.record.amendment_id} {section}{result.record.amendment_paragraph}"
        print(f"{result.rank}. {label} score={result.relevance_score:g} signals={','.join(result.matched_signals)} refs={','.join(result.cross_references)}")
