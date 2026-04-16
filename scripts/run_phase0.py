"""Phase 0 orchestrator — runs data audit, quality scoring, and JSONL corpus parse."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_config
from src.diagnostics.data_audit import run_audit
from src.data.parser import parse_corpus_jsonl


if __name__ == '__main__':
    import random
    random.seed(42)

    cfg = get_config()

    print("=" * 60)
    print("PHASE 0: Data Reality & Diagnostics")
    print("=" * 60)

    # ── Step 1: Run expanded audit (with quality scoring) ────────────────
    print("\n▶ STEP 1: Running data audit with quality scoring...\n")
    t0 = time.time()
    audit_report = run_audit()
    audit_time = time.time() - t0
    print(f"\n  Audit completed in {audit_time:.1f}s")

    # ── Step 2: Parse entire corpus → JSONL ──────────────────────────────
    print(f"\n{'=' * 60}")
    print("▶ STEP 2: Parsing corpus → JSONL")
    print("=" * 60)
    print()

    t0 = time.time()
    parse_summary = parse_corpus_jsonl(
        raw_data_dir=cfg.paths.raw_data,
        output_dir=cfg.paths.parsed_data,
        verbose=True,
    )
    parse_time = time.time() - t0
    print(f"\n  Parsing completed in {parse_time:.1f}s")

    # ── Step 3: Write quality summary report ─────────────────────────────
    quality_report_dir = cfg.paths.audit_report.parent.parent / "quality_reports"
    quality_report_dir.mkdir(parents=True, exist_ok=True)
    quality_report_path = quality_report_dir / "quality_summary.json"

    quality_report = {
        "total_files": parse_summary["total"],
        "valid_files": parse_summary["valid"],
        "invalid_files": parse_summary["invalid"],
        "quality_distribution": parse_summary["quality_counts"],
        "quality_percentages": {
            k: round(v / max(parse_summary["total"], 1) * 100, 1)
            for k, v in parse_summary["quality_counts"].items()
        },
        "error_files_sample": parse_summary["error_files"][:30],
    }

    with open(quality_report_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2, ensure_ascii=False)

    print(f"\n  Quality report written to: {quality_report_path}")

    # ── Step 4: Final summary ────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("PHASE 0 COMPLETE — FINAL SUMMARY")
    print("=" * 60)

    print(f"\n  Corpus:")
    print(f"    Total files:   {parse_summary['total']}")
    print(f"    Valid:         {parse_summary['valid']}")
    print(f"    Invalid:       {parse_summary['invalid']}")

    qc = parse_summary['quality_counts']
    total = max(parse_summary['total'], 1)
    print(f"\n  Quality Distribution:")
    print(f"    OK:     {qc['OK']:>6}  ({qc['OK']/total*100:.1f}%)")
    print(f"    REVIEW: {qc['REVIEW']:>6}  ({qc['REVIEW']/total*100:.1f}%)")
    print(f"    REJECT: {qc['REJECT']:>6}  ({qc['REJECT']/total*100:.1f}%)")

    print(f"\n  Outputs:")
    print(f"    Parsed JSONL:   {cfg.paths.parsed_data}/*.jsonl")
    print(f"    Audit report:   {cfg.paths.audit_report}")
    print(f"    Quality report: {quality_report_path}")

    print(f"\n  Total time: {audit_time + parse_time:.1f}s")
    print("=" * 60)
