"""
Neo4j Ingestion Pipeline
==========================
Full ETL from citations_network.jsonl -> Neo4j graph.
Implements the 8-stage pipeline from the execution roadmap.
"""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

from .neo4j_client import Neo4jClient
from .normalizer import (
    normalize_citation, normalize_record_citations, normalize_record_statutes,
    extract_reporter, extract_citation_year, extract_act_abbreviation,
    extract_act_year, classify_act_type, STATUTE_LIST_FIELDS,
)
from .resolvers import CitationResolver
from .schema import create_constraints, create_post_load_indexes, create_fulltext_indexes

logger = logging.getLogger(__name__)
NODE_BATCH_SIZE = 5000
EDGE_BATCH_SIZE = 10000


def parse_and_validate(jsonl_path: Path, verbose=True):
    """Stage 1: Stream JSONL, validate schema, skip errors."""
    if verbose:
        print(f"\n  Stage 1: Parse & Validate — {jsonl_path}")
    records, errors, seen_ids = [], [], set()
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append({"line": ln, "error": str(e)}); continue
            fid = rec.get("file_id")
            if not fid:
                errors.append({"line": ln, "error": "Missing file_id"}); continue
            if fid in seen_ids:
                errors.append({"line": ln, "error": f"Dup: {fid}"}); continue
            seen_ids.add(fid)
            if "error" in rec:
                errors.append({"line": ln, "file_id": fid, "error": rec["error"]}); continue
            try:
                rec["year"] = int(rec.get("year", 0))
            except (ValueError, TypeError):
                rec["year"] = 0
            records.append(rec)
    if verbose:
        print(f"    Valid: {len(records)} | Errors: {len(errors)}")
    return records, errors


def _title_from_file_id(fid):
    import re
    return re.sub(r'\s+\d+$', '', fid.replace("_", " "))


def normalize_and_index(records, verbose=True):
    """Stage 2-3: Normalize citations/statutes, build reverse lookup."""
    if verbose:
        print(f"\n  Stage 2-3: Normalize & Build Index")
    all_self, all_body, all_stat = {}, {}, {}
    all_codes, uniq_stat, uniq_acts = set(), {}, {}
    t0 = time.time()
    for i, rec in enumerate(records):
        fid = rec["file_id"]
        sc, bc = normalize_record_citations(rec)
        all_self[fid], all_body[fid] = sc, bc
        all_codes.update(sc); all_codes.update(bc)
        ns = normalize_record_statutes(rec)
        all_stat[fid] = ns
        for s in ns:
            cn = s["canonical_name"]
            if cn not in uniq_stat:
                uniq_stat[cn] = s
            a = s["act_name"]
            if a and a not in uniq_acts:
                uniq_acts[a] = a
        if verbose and (i+1) % 5000 == 0:
            print(f"    ... {i+1}/{len(records)}")
    if verbose:
        print(f"    Done in {time.time()-t0:.1f}s — codes:{len(all_codes)} stats:{len(uniq_stat)} acts:{len(uniq_acts)}")
    resolver = CitationResolver()
    resolver.build_index(records, verbose=verbose)
    if verbose:
        rs = resolver.compute_resolution_stats(records)
        print(f"    Resolution: {rs['resolved']}/{rs['total_body_citations']} ({rs['resolution_rate_pct']}%)")
    return all_self, all_body, all_stat, all_codes, uniq_stat, uniq_acts, resolver


def _batch_write(client, cypher, data, batch_size, label, verbose):
    created = 0
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        client.run_write(cypher, {"batch": batch})
        created += len(batch)
        if verbose and created % (batch_size * 3) == 0:
            print(f"    ... {label}: {created}/{len(data)}")
    if verbose:
        print(f"    ✓ {label}: {len(data)}")


def create_nodes(client, records, all_body, all_stat, all_codes, uniq_stat, uniq_acts, verbose=True):
    """Stage 4: Create Act, Statute, Citation, Case nodes."""
    if verbose:
        print(f"\n  Stage 4: Creating nodes")

    # Acts
    acts = [{"name": a, "abbreviation": extract_act_abbreviation(a) or "",
             "year_enacted": extract_act_year(a) or 0, "act_type": classify_act_type(a)}
            for a in uniq_acts if "Unknown" not in a]
    _batch_write(client, """
        UNWIND $batch AS r MERGE (a:Act {name: r.name})
        ON CREATE SET a.abbreviation=r.abbreviation, a.year_enacted=r.year_enacted, a.act_type=r.act_type
    """, acts, NODE_BATCH_SIZE, "Act nodes", verbose)

    # Statutes
    stats = [{"canonical_name": cn, "category": i["category"], "act_name": i["act_name"], "section": i["section"]}
             for cn, i in uniq_stat.items()]
    _batch_write(client, """
        UNWIND $batch AS r MERGE (s:Statute {canonical_name: r.canonical_name})
        ON CREATE SET s.category=r.category, s.act_name=r.act_name, s.section=r.section
    """, stats, NODE_BATCH_SIZE, "Statute nodes", verbose)

    # Citations
    cites = [{"code": c, "reporter": extract_reporter(c) or "", "year": extract_citation_year(c) or 0}
             for c in all_codes if c]
    _batch_write(client, """
        UNWIND $batch AS r MERGE (ci:Citation {code: r.code})
        ON CREATE SET ci.reporter=r.reporter, ci.year=r.year
    """, cites, NODE_BATCH_SIZE, "Citation nodes", verbose)

    # Cases
    cases = [{"file_id": r["file_id"], "year": r["year"], "title": _title_from_file_id(r["file_id"]),
              "self_citations": r.get("self_citations", []),
              "citation_count": len(all_body.get(r["file_id"], [])),
              "statute_count": len(all_stat.get(r["file_id"], [])),
              "has_raw_act_block": bool(r.get("statutes", {}).get("raw_act_block", ""))}
             for r in records]
    _batch_write(client, """
        UNWIND $batch AS r MERGE (c:Case {file_id: r.file_id})
        ON CREATE SET c.year=r.year, c.title=r.title, c.self_citations=r.self_citations,
            c.citation_count=r.citation_count, c.statute_count=r.statute_count, c.has_raw_act_block=r.has_raw_act_block
    """, cases, NODE_BATCH_SIZE, "Case nodes", verbose)


def create_edges(client, all_self, all_body, all_stat, uniq_stat, verbose=True):
    """Stage 5: Create HAS_CITATION, CITES, REFERENCES, PART_OF edges."""
    if verbose:
        print(f"\n  Stage 5: Creating edges")

    # HAS_CITATION
    hc = [{"file_id": fid, "code": c} for fid, cs in all_self.items() for c in cs]
    _batch_write(client, """
        UNWIND $batch AS r MATCH (c:Case {file_id: r.file_id}) MATCH (ci:Citation {code: r.code})
        MERGE (c)-[:HAS_CITATION]->(ci)
    """, hc, EDGE_BATCH_SIZE, "HAS_CITATION", verbose)

    # CITES
    ci = [{"file_id": fid, "code": c} for fid, cs in all_body.items() for c in cs]
    _batch_write(client, """
        UNWIND $batch AS r MATCH (c:Case {file_id: r.file_id}) MATCH (ci:Citation {code: r.code})
        MERGE (c)-[:CITES]->(ci)
    """, ci, EDGE_BATCH_SIZE, "CITES", verbose)

    # REFERENCES
    ref = [{"file_id": fid, "canonical_name": s["canonical_name"], "category": s["category"], "raw_text": s["raw_text"]}
           for fid, ss in all_stat.items() for s in ss]
    _batch_write(client, """
        UNWIND $batch AS r MATCH (c:Case {file_id: r.file_id}) MATCH (s:Statute {canonical_name: r.canonical_name})
        MERGE (c)-[e:REFERENCES]->(s) ON CREATE SET e.category=r.category, e.raw_text=r.raw_text
    """, ref, EDGE_BATCH_SIZE, "REFERENCES", verbose)

    # PART_OF
    po = [{"canonical_name": cn, "act_name": i["act_name"]}
          for cn, i in uniq_stat.items() if i.get("act_name") and "Unknown" not in i["act_name"]]
    _batch_write(client, """
        UNWIND $batch AS r MATCH (s:Statute {canonical_name: r.canonical_name}) MATCH (a:Act {name: r.act_name})
        MERGE (s)-[:PART_OF]->(a)
    """, po, EDGE_BATCH_SIZE, "PART_OF", verbose)


def create_mentions_case(client, records, all_body, resolver, verbose=True):
    """Stage 6: Resolve and materialize MENTIONS_CASE edges."""
    if verbose:
        print(f"\n  Stage 6: Resolving MENTIONS_CASE")
    edges = []
    for rec in records:
        src = rec["file_id"]
        for code in all_body.get(src, []):
            tgt = resolver.resolve(code)
            if tgt and tgt != src:
                edges.append({"source_id": src, "target_id": tgt, "via_citation": code})
    if verbose:
        print(f"    Resolved {len(edges)} direct Case→Case links")
    _batch_write(client, """
        UNWIND $batch AS r MATCH (a:Case {file_id: r.source_id}) MATCH (b:Case {file_id: r.target_id})
        MERGE (a)-[e:MENTIONS_CASE]->(b) ON CREATE SET e.via_citation=r.via_citation
    """, edges, EDGE_BATCH_SIZE, "MENTIONS_CASE", verbose)
    return len(edges)


def run_full_ingestion(jsonl_path, client, clear_existing=True, verbose=True):
    """Run the complete 8-stage ingestion pipeline."""
    t_start = time.time()
    if verbose:
        print("=" * 70)
        print("PHASE 2A: Neo4j Graph Ingestion Pipeline")
        print("=" * 70)

    if clear_existing:
        if verbose:
            print("\n  Clearing existing database...")
        from .schema import drop_all_constraints_and_indexes
        drop_all_constraints_and_indexes(client, verbose=verbose)
        client.clear_database()

    # Stage 1
    records, errors = parse_and_validate(jsonl_path, verbose)
    # Constraints before bulk
    create_constraints(client, verbose)
    # Stage 2-3
    all_self, all_body, all_stat, all_codes, uniq_stat, uniq_acts, resolver = normalize_and_index(records, verbose)
    # Stage 4
    create_nodes(client, records, all_body, all_stat, all_codes, uniq_stat, uniq_acts, verbose)
    # Stage 5
    create_edges(client, all_self, all_body, all_stat, uniq_stat, verbose)
    # Stage 6
    mc = create_mentions_case(client, records, all_body, resolver, verbose)
    # Stage 7
    if verbose:
        print(f"\n  Stage 7: Post-load indexes")
    create_post_load_indexes(client, verbose)
    create_fulltext_indexes(client, verbose)

    rs = resolver.compute_resolution_stats(records)
    total = time.time() - t_start
    summary = {
        "records_parsed": len(records), "parse_errors": len(errors),
        "unique_citations": len(all_codes), "unique_statutes": len(uniq_stat),
        "unique_acts": len(uniq_acts), "mentions_case": mc,
        "resolution": rs, "collisions": len(resolver.collisions),
        "total_time_seconds": round(total, 1),
    }
    if verbose:
        print(f"\n{'=' * 70}")
        print(f"  DONE in {total:.1f}s | Cases:{len(records)} Cites:{len(all_codes)} Stats:{len(uniq_stat)} Acts:{len(uniq_acts)}")
        print(f"  Resolution: {rs['resolution_rate_pct']}% | MENTIONS_CASE: {mc}")
        print(f"{'=' * 70}")
    return summary
