"""
Neo4j Validation Engine
========================
Post-ingestion integrity and data quality checks.
Implements PART 3 of the execution roadmap.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


def run_integrity_checks(client: Neo4jClient, verbose=True) -> dict:
    """Run all post-ingestion integrity checks (§3.1)."""
    if verbose:
        print(f"\n{'=' * 60}")
        print("  Stage 8: Post-Ingestion Validation")
        print(f"{'=' * 60}")

    checks = {}

    # Node counts
    for label, expected_min, expected_max in [
        ("Case",     25000, 27000),
        ("Citation", 30000, 80000),
        ("Statute",  5000,  40000),
        ("Act",      100,   2000),
    ]:
        count = client.count_nodes(label)
        ok = expected_min <= count <= expected_max
        checks[f"{label}_count"] = {"count": count, "expected": f"{expected_min}-{expected_max}", "ok": ok}
        if verbose:
            sym = "✓" if ok else "✗"
            print(f"    {sym} {label} nodes: {count:,} (expected {expected_min:,}-{expected_max:,})")

    # Edge counts
    for rel_type, expected_min in [
        ("HAS_CITATION", 40000),
        ("CITES",        100000),
        ("REFERENCES",   50000),
        ("PART_OF",      5000),
        ("MENTIONS_CASE", 10000),
    ]:
        count = client.count_relationships(rel_type)
        ok = count >= expected_min
        checks[f"{rel_type}_count"] = {"count": count, "min_expected": expected_min, "ok": ok}
        if verbose:
            sym = "✓" if ok else "⚠"
            print(f"    {sym} {rel_type} edges: {count:,} (min {expected_min:,})")

    # Cases with no CITES (expected ~7.7%)
    result = client.run_query("MATCH (c:Case) WHERE NOT (c)-[:CITES]->() RETURN count(c) AS cnt")
    no_cites = result[0]["cnt"] if result else 0
    total_cases = checks.get("Case_count", {}).get("count", 1)
    pct = no_cites / max(total_cases, 1) * 100
    checks["cases_no_cites"] = {"count": no_cites, "pct": round(pct, 1)}
    if verbose:
        print(f"    ○ Cases with no CITES: {no_cites} ({pct:.1f}%)")

    # Orphan Citations
    result = client.run_query("""
        MATCH (ci:Citation)
        WHERE NOT ()-[:HAS_CITATION]->(ci) AND NOT ()-[:CITES]->(ci)
        RETURN count(ci) AS cnt
    """)
    orphans = result[0]["cnt"] if result else 0
    checks["orphan_citations"] = {"count": orphans, "ok": orphans == 0}
    if verbose:
        sym = "✓" if orphans == 0 else "⚠"
        print(f"    {sym} Orphan Citation nodes: {orphans}")

    # Self-referencing MENTIONS_CASE
    result = client.run_query("""
        MATCH (c:Case)-[:MENTIONS_CASE]->(c) RETURN count(c) AS cnt
    """)
    self_refs = result[0]["cnt"] if result else 0
    checks["self_ref_mentions"] = {"count": self_refs, "ok": self_refs == 0}
    if verbose:
        sym = "✓" if self_refs == 0 else "✗"
        print(f"    {sym} Self-referencing MENTIONS_CASE: {self_refs}")

    # Statute→Act linkage (every Statute should have PART_OF)
    result = client.run_query("""
        MATCH (s:Statute) WHERE NOT (s)-[:PART_OF]->() RETURN count(s) AS cnt
    """)
    unlinked = result[0]["cnt"] if result else 0
    checks["unlinked_statutes"] = {"count": unlinked}
    if verbose:
        sym = "✓" if unlinked == 0 else "⚠"
        print(f"    {sym} Statutes without PART_OF→Act: {unlinked}")

    # MENTIONS_CASE resolution rate
    cites_count = checks.get("CITES_count", {}).get("count", 1)
    mc_count = checks.get("MENTIONS_CASE_count", {}).get("count", 0)
    res_rate = mc_count / max(cites_count, 1) * 100
    checks["resolution_rate"] = {"pct": round(res_rate, 1)}
    if verbose:
        sym = "✓" if res_rate >= 20 else "⚠"
        print(f"    {sym} Citation resolution rate: {res_rate:.1f}%")

    # Overall
    all_ok = all(c.get("ok", True) for c in checks.values() if isinstance(c, dict))
    checks["overall_ok"] = all_ok

    if verbose:
        print(f"\n  {'✓ All checks passed' if all_ok else '⚠ Some checks had warnings'}")

    return checks


def run_sample_comparison(client: Neo4jClient, jsonl_path: Path, sample_size=500, verbose=True) -> dict:
    """
    Cross-validate Neo4j against source JSONL for a random sample (§3.3).
    """
    if verbose:
        print(f"\n  Cross-validation: sampling {sample_size} records...")

    import random
    # Load JSONL
    all_records = {}
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                fid = rec.get("file_id")
                if fid and "error" not in rec:
                    all_records[fid] = rec
            except json.JSONDecodeError:
                continue

    sample_ids = random.sample(list(all_records.keys()), min(sample_size, len(all_records)))
    mismatches = []
    checked = 0

    for fid in sample_ids:
        rec = all_records[fid]
        # Check CITES count
        result = client.run_query(
            "MATCH (c:Case {file_id: $fid})-[:CITES]->(ci) RETURN count(ci) AS cnt",
            {"fid": fid}
        )
        neo4j_cites = result[0]["cnt"] if result else 0
        jsonl_cites = len(rec.get("cited_cases", []))
        if neo4j_cites != jsonl_cites:
            mismatches.append({
                "file_id": fid, "field": "cited_cases",
                "jsonl": jsonl_cites, "neo4j": neo4j_cites
            })
        checked += 1

    match_pct = (checked - len(mismatches)) / max(checked, 1) * 100
    stats = {
        "sample_size": checked,
        "mismatches": len(mismatches),
        "match_rate_pct": round(match_pct, 1),
    }

    if verbose:
        print(f"    Checked {checked} records")
        print(f"    Mismatches: {len(mismatches)}")
        print(f"    Match rate: {match_pct:.1f}%")
        if mismatches and len(mismatches) <= 5:
            for mm in mismatches[:5]:
                print(f"      {mm['file_id']}: JSONL={mm['jsonl']} Neo4j={mm['neo4j']}")

    return stats


def run_top_cited_analysis(client: Neo4jClient, top_n=20, verbose=True) -> list:
    """Find the most-cited cases by in-degree (MENTIONS_CASE)."""
    result = client.run_query(f"""
        MATCH (c:Case)<-[:MENTIONS_CASE]-(other)
        RETURN c.file_id AS file_id, c.year AS year, c.title AS title,
               count(other) AS in_degree
        ORDER BY in_degree DESC
        LIMIT {top_n}
    """)

    if verbose:
        print(f"\n  Top {top_n} most-cited cases (by MENTIONS_CASE in-degree):")
        for i, r in enumerate(result, 1):
            print(f"    {i:2}. [{r['year']}] {r['title'][:60]}... — {r['in_degree']} citations")

    return result


def run_full_validation(client, jsonl_path, verbose=True) -> dict:
    """Run all validation checks."""
    checks = run_integrity_checks(client, verbose)
    comparison = run_sample_comparison(client, jsonl_path, verbose=verbose)
    top_cited = run_top_cited_analysis(client, verbose=verbose)
    return {
        "integrity": checks,
        "comparison": comparison,
        "top_cited": [{"file_id": r["file_id"], "in_degree": r["in_degree"]} for r in top_cited],
    }
