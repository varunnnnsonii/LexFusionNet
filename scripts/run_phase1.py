"""Phase 1 orchestrator — runs citation extraction, then statutory extraction."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_config
from src.extraction.citations import run_citation_extraction
from src.extraction.statutes import run_statutory_extraction


if __name__ == '__main__':
    cfg = get_config()

    phase1_dir = cfg.paths.parsed_data.parent / "phase1"
    phase1_dir.mkdir(parents=True, exist_ok=True)
    citations_jsonl = phase1_dir / "citations_network.jsonl"

    print("=" * 60)
    print("PHASE 1: Citation & Statutory Extraction")
    print("=" * 60)

    # ── Step 1: Citation Extraction ──────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("▶ STEP 1: Extracting citations (self-citations, body-citations, case names)")
    print("=" * 60)
    print()

    t0 = time.time()
    cite_summary = run_citation_extraction(
        raw_data_dir=cfg.paths.raw_data,
        output_file=citations_jsonl,
        verbose=True,
    )
    cite_time = time.time() - t0
    print(f"\n  Citation extraction completed in {cite_time:.1f}s")

    # ── Step 2: Statutory Extraction ─────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("▶ STEP 2: Extracting statutory references (IPC, CrPC, Constitution, Acts, ...)")
    print("=" * 60)
    print()

    t0 = time.time()
    stat_summary = run_statutory_extraction(
        raw_data_dir=cfg.paths.raw_data,
        jsonl_path=citations_jsonl,
        verbose=True,
    )
    stat_time = time.time() - t0
    print(f"\n  Statutory extraction completed in {stat_time:.1f}s")

    # ── Step 3: Write phase 1 summary report ─────────────────────────────
    report_dir = phase1_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "phase1_summary.json"

    phase1_report = {
        "citation_extraction": cite_summary,
        "statutory_extraction": stat_summary,
        "total_time_seconds": round(cite_time + stat_time, 1),
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(phase1_report, f, indent=2, ensure_ascii=False)

    print(f"\n  Phase 1 report written to: {report_path}")

    # ── Step 4: Final summary ────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("PHASE 1 COMPLETE — FINAL SUMMARY")
    print("=" * 60)

    print(f"\n  Citation Extraction:")
    print(f"    Total files:              {cite_summary['total_files']}")
    print(f"    Processed:                {cite_summary['processed']}")
    print(f"    Errors:                   {cite_summary['errors']}")
    missing_pct = (
        cite_summary['missing_self_citations'] / max(cite_summary['total_files'], 1) * 100
    )
    print(f"    Missing self-citations:   {cite_summary['missing_self_citations']} ({missing_pct:.1f}%)")

    print(f"\n  Statutory Extraction:")
    print(f"    Total files on disk:      {stat_summary['total_files']}")
    print(f"    Existing JSONL records:   {stat_summary['existing_records']}")
    print(f"    Auto-healed (missing):    {stat_summary['healed_count']}")

    print(f"\n  Outputs:")
    print(f"    Citations + Statutes JSONL: {citations_jsonl}")
    print(f"    Phase 1 report:             {report_path}")

    print(f"\n  Total time: {cite_time + stat_time:.1f}s")
    print("=" * 60)