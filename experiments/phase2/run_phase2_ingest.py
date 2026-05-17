#!/usr/bin/env python3
"""
Phase 2A Orchestrator — JSONL → Neo4j Graph Ingestion
======================================================
Run this to ingest citations_network.jsonl into Neo4j and validate the graph.

Usage:
    python experiments/phase2/run_phase2_ingest.py [--no-clear] [--skip-validation]

Requires:
    - Neo4j running (docker compose up neo4j)
    - pip install neo4j
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from experiments.phase2.neo4j_client import Neo4jClient
from experiments.phase2.ingestion import run_full_ingestion
from experiments.phase2.validation import run_full_validation


def main():
    parser = argparse.ArgumentParser(description="Phase 2A: Neo4j Graph Ingestion")
    parser.add_argument("--no-clear", action="store_true",
                        help="Don't clear existing graph (incremental mode)")
    parser.add_argument("--skip-validation", action="store_true",
                        help="Skip post-ingestion validation")
    parser.add_argument("--jsonl", type=str, default=None,
                        help="Path to citations_network.jsonl (default: auto)")
    args = parser.parse_args()

    # Resolve JSONL path
    jsonl_path = Path(args.jsonl) if args.jsonl else (
        PROJECT_ROOT / "data" / "processed" / "phase1" / "citations_network.jsonl"
    )
    if not jsonl_path.exists():
        print(f"ERROR: JSONL not found at {jsonl_path}")
        sys.exit(1)

    print(f"JSONL: {jsonl_path} ({jsonl_path.stat().st_size / 1024 / 1024:.1f} MB)")

    # Report output
    report_dir = PROJECT_ROOT / "data" / "processed" / "phase2"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Connect to Neo4j
    try:
        client = Neo4jClient()
        client.connect()
    except Exception as e:
        print(f"\nERROR: Cannot connect to Neo4j — {e}")
        print("Make sure Neo4j is running: docker compose up -d neo4j")
        sys.exit(1)

    try:
        # ── Run Ingestion ─────────────────────────────────────────────────
        summary = run_full_ingestion(
            jsonl_path=jsonl_path,
            client=client,
            clear_existing=not args.no_clear,
            verbose=True,
        )

        # Save ingestion report
        report_path = report_dir / "ingestion_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n  Ingestion report → {report_path}")

        # ── Run Validation ────────────────────────────────────────────────
        if not args.skip_validation:
            val_results = run_full_validation(client, jsonl_path, verbose=True)
            val_path = report_dir / "validation_report.json"
            with open(val_path, 'w', encoding='utf-8') as f:
                json.dump(val_results, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n  Validation report → {val_path}")

    finally:
        client.close()

    print("\n✓ Phase 2A complete!")


if __name__ == "__main__":
    main()
