"""Print a compact inspection of the parsed source artifacts."""

from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grounded.amendments import parse_amendment, validate_amendment_targets
from grounded.ingest import parse_policy_manual


root = Path(__file__).resolve().parents[1]
provisions = parse_policy_manual(root / "source/original/policy-manual.md")
amendments = parse_amendment(root / "source/amendment/Amendment No. 2026-01.md")
validate_amendment_targets(amendments, provisions)
section = chr(0xA7)
print(f"provisions: {len(provisions)}")
print("provision_ids:", ", ".join(p.provision_no for p in provisions))
print(f"amendments: {len(amendments)}")
for record in amendments:
    print(f"- {record.amendment_id} {section}{record.amendment_paragraph}: {record.operation} -> {record.target_provision}")
