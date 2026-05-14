# Execution Roadmap, Migration & Operations

> Companion to: `01_neo4j_architecture_and_schema.md`
> Source: `data/processed/phase1/citations_network.jsonl` (26,661 records)

---

## PART 1 — INGESTION PIPELINE DESIGN

### 1.1 ETL Overview

```
citations_network.jsonl
        |
        v
  [1. Parse & Validate]     Stream JSONL, validate schema, skip errors
        |
        v
  [2. Normalize]            Citation normalization, statute canonicalization
        |
        v
  [3. Build Lookup Index]   self_citations → file_id reverse map
        |
        v
  [4. Create Nodes]         Case, Citation, Statute, Act nodes (batch)
        |
        v
  [5. Create Edges]         CITES, HAS_CITATION, REFERENCES, PART_OF (batch)
        |
        v
  [6. Resolve & Materialize] MENTIONS_CASE derived edges
        |
        v
  [7. Post-Load Indexes]    Create remaining indexes after bulk load
        |
        v
  [8. Validate]             Integrity checks, count verification
```

### 1.2 Ingestion Stages — Detailed

#### Stage 1: Parse & Validate

- Stream the JSONL file line by line (not full load — saves memory)
- Validate each record has required fields: `file_id`, `year`, `self_citations`, `cited_cases`, `statutes`
- Skip records with `file_id = None` or duplicate `file_id` (log warnings)
- Cast `year` from string to int
- Collect all records into a list for multi-pass processing

**Error handling:** Log malformed records to `artifacts/phase2/ingestion_errors.jsonl`. Do not halt on individual record failures.

#### Stage 2: Normalize

**Citation normalization function:**
1. Uppercase all characters
2. Remove all brackets: `()[]`
3. Replace `SUPREME COURT` with `SC`
4. Collapse all whitespace to single spaces
5. Strip leading/trailing whitespace
6. Result: `"2006 10 SCC 261"` stays `"2006 10 SCC 261"`, `"(2006) 10 SCC 261"` becomes `"2006 10 SCC 261"`

**Statute normalization:**
1. Route by field name to determine parent Act
2. Extract section/article number via regex
3. Construct canonical name: `"Section {num}, {Act Full Name}"`
4. Build Act name registry from known mappings + dynamic extraction from `named_act_sections`

#### Stage 3: Build Lookup Index

- Single pass over all records
- For each `self_citations` entry, map `normalized_citation → file_id`
- Handle collisions: if same citation maps to multiple file_ids, prefer the one whose year matches the citation year. Log all collisions.
- Store as Python dict (in-memory, ~5 MB)
- Also build `file_id → [normalized_self_citations]` for fast reverse lookup

#### Stage 4: Create Nodes (Batch)

**Transaction strategy:** Batch commits of 5,000 nodes per transaction.

**Order matters — create in this sequence:**
1. **Act nodes** first (smallest set, ~500–800)
2. **Statute nodes** (reference Act nodes, ~15K–25K)
3. **Citation nodes** (independent, ~40K–60K)
4. **Case nodes** last (largest set, 26,661)

**Why this order:** Creating parent nodes first avoids dangling references. However, since we create edges separately, order is mainly for logical clarity.

**Deduplication:** Use `MERGE` semantics — if a node with the same unique property exists, skip creation.

#### Stage 5: Create Edges (Batch)

**Transaction strategy:** Batch commits of 10,000 edges per transaction.

**Edge creation order:**
1. `HAS_CITATION` edges (Case → Citation): 60,935 edges
2. `CITES` edges (Case → Citation): 165,440 edges
3. `REFERENCES` edges (Case → Statute): 200K–300K edges
4. `PART_OF` edges (Statute → Act): 15K–25K edges

**Each edge batch:**
- Collect (source_id, target_id, properties) tuples
- Use `UNWIND` with parameter lists for efficient batch insertion
- Periodic commit to avoid transaction memory overflow

#### Stage 6: Resolve & Materialize

- For each `CITES` edge (Case → Citation), check if the Citation has an inbound `HAS_CITATION` from another Case
- If yes, create `MENTIONS_CASE` edge (Case A → Case B) with `via_citation` property
- This is a graph-internal operation using traversal, not JSONL data
- Run as a single post-load batch job
- Expected output: 50K–100K `MENTIONS_CASE` edges

#### Stage 7: Post-Load Indexes

Create all non-unique indexes AFTER bulk load (creating indexes before bulk load slows insertion):
- Range indexes on year, citation_count, statute_count
- Full-text indexes on title, canonical_name
- Composite indexes as needed

#### Stage 8: Validate

Run integrity checks (see Part 4).

### 1.3 Estimated Ingestion Time

| Stage | Estimated Duration |
|-------|--------------------|
| Parse & Validate | 5–10 seconds |
| Normalize | 10–20 seconds |
| Build Lookup | 2–5 seconds |
| Create Nodes (~120K) | 30–60 seconds |
| Create Edges (~500K) | 60–120 seconds |
| Resolve MENTIONS_CASE | 30–60 seconds |
| Create Indexes | 10–20 seconds |
| Validate | 10–20 seconds |
| **Total** | **~3–5 minutes** |

### 1.4 Incremental Ingestion (Future)

When new cases are added to the corpus:
1. Extract citations + statutes for new files (existing Phase 1 pipeline)
2. Append new records to citations_network.jsonl
3. Run ingestion pipeline with `MERGE` semantics — existing nodes/edges are skipped, only new ones created
4. Re-run MENTIONS_CASE resolution for new cases
5. Update graph embeddings if using node2vec

**Deduplication:** `MERGE` on unique constraints prevents duplicates. The `file_id` constraint on Case guarantees idempotency.

### 1.5 Conflict Handling

| Conflict Type | Strategy |
|---------------|----------|
| Duplicate file_id | Skip with warning (same case re-processed) |
| Citation collision (same code, multiple cases) | Create multiple HAS_CITATION edges (valid for parallel citations) |
| Statute normalization ambiguity | Prefer longest match; log ambiguous cases |
| Missing fields | Create node with available properties; set `data_quality: "partial"` |

---

## PART 2 — MIGRATION PLAN

### 2.1 Migration Philosophy

**Non-destructive, additive migration.** The existing JSONL pipeline continues to work. Neo4j is an additional layer, not a replacement. The JSONL file remains the source of truth.

### 2.2 Migration Phases

#### Phase 2A: Graph Foundation (Week 1–2)

**Goal:** Stand up Neo4j, ingest the full JSONL, verify the graph.

| Task | Duration | Dependency |
|------|----------|------------|
| Add Neo4j to docker-compose.yml | 1 hour | None |
| Create `src/graph/neo4j_client.py` (connection manager) | 2 hours | Docker Neo4j running |
| Create `src/graph/normalizer.py` (citation + statute normalization) | 4 hours | None |
| Create `src/graph/ingestion.py` (full ETL pipeline) | 8 hours | Client + Normalizer |
| Create `src/graph/schema.py` (constraints + indexes) | 2 hours | Client |
| Run full ingestion against citations_network.jsonl | 5 minutes | All above |
| Create `src/graph/validation.py` (integrity checks) | 4 hours | Ingestion complete |
| Run validation, fix issues | 4 hours | Validation |
| **Total** | **~3–4 days** | |

**Deliverables:**
- Neo4j populated with ~120K nodes, ~500K edges
- Validation report showing coverage and integrity
- MENTIONS_CASE resolved edges

#### Phase 2B: Query Layer (Week 3)

**Goal:** Build query functions that answer real legal questions.

| Task | Duration |
|------|----------|
| Create `src/graph/queries.py` (Cypher query builder) | 8 hours |
| Implement: citation chain traversal | 4 hours |
| Implement: authority ranking (in-degree) | 2 hours |
| Implement: statute co-occurrence | 4 hours |
| Implement: related cases (shared statutes + citations) | 4 hours |
| Implement: temporal queries | 2 hours |
| Tests for all query functions | 4 hours |
| **Total** | **~3–4 days** |

#### Phase 2C: Embedding + Retrieval Integration (Week 4–5)

**Goal:** Connect Neo4j graph signals with Qdrant vector search.

| Task | Duration |
|------|----------|
| Create chunking pipeline (from Phase 0 JSONL body text) | 4 hours |
| Generate embeddings (BAAI/bge-base-en-v1.5) | 8 hours (GPU) |
| Load embeddings into Qdrant | 2 hours |
| Create `src/retrieval/hybrid.py` (graph + vector fusion) | 8 hours |
| Implement graph-enhanced RAG pipeline | 8 hours |
| Implement reranker integration | 4 hours |
| End-to-end testing | 4 hours |
| **Total** | **~5–6 days** |

#### Phase 2D: Graph Analytics (Week 6)

**Goal:** Run graph algorithms for authority and community detection.

| Task | Duration |
|------|----------|
| Install Neo4j Graph Data Science library | 1 hour |
| Run PageRank on MENTIONS_CASE subgraph | 2 hours |
| Run community detection (Louvain/Leiden) on citation graph | 4 hours |
| Generate node2vec embeddings | 4 hours |
| Store graph metrics as Case node properties | 2 hours |
| Integrate graph scores into fusion weights | 4 hours |
| **Total** | **~2–3 days** |

### 2.3 Folder Structure (New Files)

```
src/graph/
├── __init__.py
├── neo4j_client.py        # Connection manager, session factory
├── schema.py              # Constraint + index creation
├── normalizer.py          # Citation & statute normalization
├── ingestion.py           # Full ETL from JSONL → Neo4j
├── queries.py             # Query builder functions
├── validation.py          # Integrity checks
├── analytics.py           # PageRank, community detection
└── resolvers.py           # Citation resolution logic

src/retrieval/
├── __init__.py
├── hybrid.py              # Graph + vector fusion
├── graph_expander.py      # Graph-based candidate expansion
└── context_assembler.py   # Build RAG context from graph + text

scripts/
├── run_phase2_ingest.py   # Orchestrator: JSONL → Neo4j
├── run_phase2_analytics.py # Orchestrator: graph algorithms
└── run_phase2_retrieval.py # Orchestrator: hybrid search demo

configs/config.yaml        # Add neo4j section:
                           #   neo4j:
                           #     uri: bolt://localhost:7687
                           #     user: neo4j
                           #     password: lexifusionnet
                           #     database: neo4j
```

### 2.4 Rollback Plan

Since the migration is additive:
- **Rollback = stop Neo4j container.** The JSONL pipeline still works independently.
- Neo4j data is in a Docker volume (`neo4j_data`). To reset, delete the volume.
- No existing code is modified — all new functionality is in `src/graph/` and `src/retrieval/`
- The existing `config.yaml` gets new keys but existing keys are untouched

### 2.5 Dual-Write Strategy

During migration, both JSONL and Neo4j are kept in sync:
1. New cases are added to JSONL first (source of truth)
2. Incremental ingestion pipeline reads new JSONL records and upserts into Neo4j
3. If Neo4j is down, the system degrades gracefully — JSONL queries still work
4. Once Neo4j is validated, it becomes the primary query layer; JSONL becomes the backup/archive

---

## PART 3 — VALIDATION STRATEGY

### 3.1 Post-Ingestion Integrity Checks

| Check | Expected | Method |
|-------|----------|--------|
| Case node count | 26,661 | `MATCH (c:Case) RETURN count(c)` |
| Citation node count | 40K–60K | `MATCH (ci:Citation) RETURN count(ci)` |
| Statute node count | 15K–25K | `MATCH (s:Statute) RETURN count(s)` |
| Act node count | 500–800 | `MATCH (a:Act) RETURN count(a)` |
| CITES edge count | 165,440 | `MATCH ()-[r:CITES]->() RETURN count(r)` |
| HAS_CITATION edge count | ~60,935 | `MATCH ()-[r:HAS_CITATION]->() RETURN count(r)` |
| Every Case has ≥0 CITES | 100% | `MATCH (c:Case) WHERE NOT (c)-[:CITES]->() RETURN count(c)` — should be ~7.7% (no cited_cases) |
| Every Citation has ≥1 inbound edge | 100% | No orphan Citation nodes |
| No duplicate Case file_ids | 0 duplicates | Constraint enforces this |
| MENTIONS_CASE resolution rate | 30–60% | Compare resolved count vs total CITES |

### 3.2 Data Quality Checks

| Check | Method |
|-------|--------|
| Orphan Citation nodes (no HAS_CITATION and no CITES) | Find and flag — these are ingestion errors |
| Self-referencing MENTIONS_CASE | A case citing itself — should be zero (self_cites are excluded in extraction) |
| Year consistency | Case.year should match the year extracted from its Citation codes |
| Statute → Act linkage | Every Statute has exactly one PART_OF → Act |
| Dangling edges | No relationships pointing to non-existent nodes |

### 3.3 Comparison Validation

Cross-validate Neo4j against the source JSONL:
1. For a random sample of 500 cases, verify that the number of CITES edges matches `len(cited_cases)` in the JSONL record
2. Verify that every `self_citations` entry has a corresponding HAS_CITATION edge
3. Verify statute counts match the sum of all statute list lengths
4. Compare the top-20 most-cited cases (by in-degree) with manual analysis

---

## PART 4 — RISK ANALYSIS

### 4.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Citation resolution rate too low (<20%)** | Medium | High — graph becomes sparse | Implement fuzzy citation matching (edit distance on normalized codes). Add case_names-based resolution as fallback. |
| **Statute normalization errors** | High | Medium — wrong statute links | Build a curated Act synonym dictionary (~200 entries). Human-review the top-100 most frequent statutes. |
| **Supernode performance degradation** | Medium | Medium — slow queries on Article 14, Section 302 | Avoid traversal through supernodes. Use property-based filtering. Add `popularity` flag. |
| **case_names noise creating false MENTIONS_CASE edges** | Medium | Medium — incorrect links | Do NOT use case_names for edge creation in Phase 2A. Use only reporter codes for resolution. Add case_name-based resolution later with confidence scoring. |
| **Memory pressure at scale** | Low (current) | High (future) | Monitor heap + page cache usage. Set alerts at 80% utilization. |
| **JSONL-Neo4j drift** | Medium | Medium — stale graph | Automated sync pipeline with hash-based change detection. |

### 4.2 Data Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| **Duplicate cases in JSONL** | Multiple records for same judgment (known: 6 duplicate groups found in Phase 0 audit) | Dedup by file_id before ingestion. If same judgment has multiple file_ids, merge during resolution. |
| **Missing self_citations** | 7.6% of cases have no self_citations — these become unlinkable | Use case_names + year as fallback identity. Log for manual enrichment. |
| **String encoding issues** | Some JSONL records may have malformed Unicode from OCR source | Validate all strings during parse stage. Replace invalid characters. |
| **Temporal gaps** | 2009 has anomalously low data (956 KB vs 10+ MB for surrounding years) | Investigate and document. May indicate data collection gap. |

### 4.3 Operational Risks

| Risk | Description | Mitigation |
|------|-------------|------------|
| **Neo4j container instability** | Docker memory limits may cause OOM kills | Set `mem_limit: 4g` in docker-compose. Monitor with `docker stats`. |
| **Ingestion idempotency failure** | Re-running ingestion creates duplicates | All operations use MERGE + UNIQUE constraints. Ingestion is idempotent by design. |
| **No backup strategy** | Neo4j data loss | Docker volume persistence + periodic `neo4j-admin dump` to artifacts directory. |

---

## PART 5 — OPEN QUESTIONS

### 5.1 Requiring Decision

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| 1 | Should `case_names` be used for graph construction? | (A) Ignore — too noisy. (B) Create CaseName nodes for clean entries only. (C) Use for fuzzy citation resolution. | **Start with A**, evolve to C with confidence scoring. |
| 2 | Where to store the `raw_act_block` text? | (A) Neo4j Case property. (B) Separate file. (C) Discard. | **A** — it's useful for debugging statute extraction. |
| 3 | Should `additional_acts` (fallback extraction) be treated same as primary statutes? | (A) Yes, same Statute nodes. (B) No, separate node label. (C) Store as Case property only. | **C** — quality is too low for graph edges. Review for promotion later. |
| 4 | Neo4j Community vs Enterprise? | (A) Community (free, sufficient for current scale). (B) Enterprise (clustering, security). (C) Aura (managed). | **A for now**, migrate to C when scaling beyond 500K cases. |
| 5 | Should the graph include Phase 0 metadata (body text, headnote, quality_score)? | (A) Yes, enrich Case nodes. (B) No, keep Neo4j lean. (C) Add selectively (quality_score, body length). | **C** — add `quality_score`, `quality_flag`, `body_length`, `has_headnote` to Case nodes. Requires joining with Phase 0 data via filename stem. |
| 6 | How to handle the 2009 data gap? | (A) Investigate and fill. (B) Document and proceed. | **B** — it doesn't affect graph correctness. |
| 7 | Should judge names be graph nodes? | (A) Yes, with normalization. (B) No, too noisy currently. | **B for Phase 2A.** Judge nodes are high-value but require a normalization effort that should be a separate project. |

### 5.2 Requiring Investigation

- What is the actual citation resolution rate? Must run the reverse lookup to measure.
- How many unique citation strings exist after normalization? Affects Citation node count.
- What is the actual collision rate for citation → file_id mapping?
- What percentage of `named_act_sections` strings can be parsed into (section, act) pairs?

---

## PART 6 — FINAL RECOMMENDATIONS

### 6.1 Priority Order

1. **Get Neo4j running in Docker** — zero-risk, takes 30 minutes
2. **Build the normalizer** — citation + statute normalization is the highest-value, highest-risk component. Get it right before anything else.
3. **Ingest and validate** — load the full JSONL, run validation checks, measure citation resolution rate. This answers the open questions.
4. **Build query layer** — implement the 6 query patterns from the architecture doc
5. **Connect to vector search** — this is where the real value appears (hybrid retrieval)
6. **Graph analytics** — PageRank, community detection, node2vec are polish, not foundation

### 6.2 Anti-Patterns to Avoid

| Anti-Pattern | Why It's Dangerous | What to Do Instead |
|-------------|--------------------|--------------------|
| Storing full body text in Neo4j | Bloats the property store, kills page cache efficiency | Keep body text in JSONL or Qdrant. Neo4j stores metadata only. |
| Traversing through Statute supernodes for similarity | Article 14 has 10K+ edges — query will timeout | Use statute co-occurrence vectors, not traversal. |
| Creating MENTIONS_CASE from case_names | 244K noisy strings create false connections | Use only reporter codes for resolution. |
| Loading all nodes in a single transaction | Out-of-memory risk | Batch commits of 5K–10K per transaction. |
| Skipping normalization "to save time" | Duplicate nodes, fragmented graph, unusable data | Normalization IS the product. Budget 30–40% of development time here. |
| Using Neo4j as the sole data store | Single point of failure, hard to rebuild | JSONL is the source of truth. Neo4j is a materialized view. |

### 6.3 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Citation resolution rate | ≥40% | Resolved MENTIONS_CASE edges ÷ total CITES edges |
| Graph density | ≥3 edges per Case node | Total edges ÷ Case nodes |
| Statute normalization accuracy | ≥90% | Manual review of top-200 statute canonical names |
| Query latency (single case lookup) | <100ms | Benchmark with Neo4j profiler |
| Query latency (citation chain, depth 4) | <500ms | Benchmark |
| Hybrid retrieval MRR improvement | ≥15% over vector-only | Evaluation on labeled query set |
| Ingestion idempotency | 100% | Run ingestion twice, verify zero changes |

### 6.4 Timeline Summary

| Phase | Duration | Outcome |
|-------|----------|---------|
| 2A: Graph Foundation | 1–2 weeks | Neo4j populated, validated, MENTIONS_CASE resolved |
| 2B: Query Layer | 1 week | 6 query patterns implemented and tested |
| 2C: Hybrid Retrieval | 2 weeks | Graph + vector fusion working end-to-end |
| 2D: Graph Analytics | 1 week | PageRank, communities, node2vec |
| **Total Phase 2** | **5–6 weeks** | Production-ready legal knowledge graph with hybrid retrieval |
