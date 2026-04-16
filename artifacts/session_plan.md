# LexiFusionNet — Session Plan

> Each session is scoped to ~1-2 hours. Start by telling me which session you're on.

---

## Session 1 (DONE) — Setup + Data Audit

**Completed:**
- Repo restructured with full package layout
- Config system (YAML + Python dataclass loader)
- Infrastructure files (Dockerfile, docker-compose, pyproject.toml, requirements.txt)
- Data cleaner (`src/data/cleaner.py`) — strips IndianKanoon page markers
- Judgment parser (`src/data/parser.py`) — extracts title, date, citations, bench, author, headnote, acts, body
- Data audit (`src/diagnostics/data_audit.py`) — run completed, report at `artifacts/data_audit_report.json`

**Audit Results (key findings):**
| Metric | Result |
|---|---|
| Total files | 26,688 |
| Corrupt files (< 500B) | 8 |
| Duplicate groups | 6 |
| Title extraction | 100% |
| Date extraction | 100% |
| Bench extraction | 95% |
| Citation extraction | 88% |
| Author extraction | 69% (expected — many old files lack Author line) |
| Headnote extraction | 41% (expected — only pre-2000 files have HEADNOTE) |
| Act extraction | 94% |
| Body valid | 100% |

---

## Session 2 — Full Corpus Parse + Metadata Store

**Goal:** Parse all 26,688 files into structured JSON. Build SQLite metadata store.

**Steps:**
1. Add a `parse_all` script that calls `parse_corpus()` from parser.py
2. Run full parse: `python3 scripts/run_phase0.py` (add corpus parse step)
3. Implement `src/data/metadata_store.py` — SQLite with schema:
   ```sql
   CREATE TABLE cases (
     case_id TEXT PRIMARY KEY,
     title TEXT, date_str TEXT, year INTEGER,
     author TEXT, file_path TEXT, file_size INTEGER,
     body_length INTEGER, is_valid BOOLEAN
   );
   CREATE TABLE citations (case_id TEXT, citation TEXT);
   CREATE TABLE bench (case_id TEXT, judge TEXT);
   CREATE TABLE acts (case_id TEXT, act_ref TEXT);
   ```
4. Load all parsed JSON into SQLite
5. Write `tests/test_parser.py` — hand-verify 10 files from different eras

**Verify before moving on:**
- `data/processed/parsed/` has 76 year-directories with JSON files
- SQLite DB at `data/processed/metadata.db` is queryable
- `SELECT COUNT(*) FROM cases WHERE is_valid = 1` returns ~26,680

**Estimated time:** 1–1.5 hours (parsing takes ~10-15 minutes on 26K files)

---

## Session 3 — Chunker + BM25 Index

**Goal:** Chunk all documents, build searchable BM25 index.

**Steps:**
1. `pip install tiktoken rank-bm25`
2. Implement `src/data/chunker.py` — 400-token chunks, 40-token overlap, max 50/case
3. Run chunking on all parsed cases → `data/processed/chunks/`
4. Implement `src/index/bm25_index.py` — build index, serialize to pickle
5. Smoke test: query 3 cases, check top-10 results

**Verify before moving on:**
- Total chunks count is ~400K–600K (sanity: avg 33KB file ÷ ~1.5KB/chunk ≈ 22 chunks/case)
- BM25 returns topically related cases for test queries
- Index serialized to `data/processed/bm25_index.pkl`

**Estimated time:** 1–1.5 hours

---

## Session 4 — Dense Embeddings + Qdrant

**Goal:** Encode all chunks with bge-base, store in Qdrant.

**Steps:**
1. `pip install sentence-transformers torch qdrant-client`
2. Start Qdrant: `docker compose up -d qdrant`
3. Implement `src/index/dense_index.py`
4. Batch-encode all chunks (GPU) — **this takes 2-3 hours on RTX 2000**
   - Option: run encoding as a background job, come back later
5. Upload to Qdrant collection
6. Test: query 3 cases via dense retrieval

**Verify before moving on:**
- Qdrant has collection `lexifusionnet_chunks` with ~500K vectors
- Dense retrieval returns results for test queries
- `docker stats` shows Qdrant using < 4GB RAM

**Estimated time:** 1 hour of coding + 2-3 hours of encoding (can run unattended)

---

## Session 5 — Hybrid Retrieval + Phase 1 Eval

**Goal:** Combine BM25 + Dense into hybrid retriever. Run first evaluation.

**Steps:**
1. Implement `src/retrieval/hybrid.py` — Reciprocal Rank Fusion
2. Implement `src/eval/manual_eval.py` — takes case_id, shows top-10 with metadata
3. Select 10 test cases (1 per legal domain: Constitutional, Criminal, Tax, Property, Labor, Family, Environmental, Contract, IP, Administrative)
4. Run evaluation, record results in `artifacts/eval_results/phase1_eval.json`

**Verify before moving on:**
- Hybrid retrieval returns results in < 5 seconds per query
- At least 6/10 test cases have >50% topically relevant results in top-10

**Estimated time:** 1.5 hours

**→ PHASE 1 COMPLETE: Working MVP similarity system**

---

## Session 6 — Citation Extraction + Graph (Phase 2 start)

**Steps:**
1. Implement `src/extraction/citation_extractor.py` (Tier 1: CITATOR INFO, Tier 2: regex)
2. Implement `src/extraction/statute_extractor.py`
3. Build citation graph with NetworkX
4. Compute PageRank, in-degree for all cases

---

## Session 7 — Cross-Encoder Reranker + Fused Scoring (Phase 2 complete)

**Steps:**
1. Implement `src/retrieval/reranker.py`
2. Implement `src/retrieval/fused_scorer.py`
3. Re-run evaluation, compare Phase 1 vs Phase 2

---

## Session 8+ — Phase 3 (only if Phase 2 shows strong results)

- Synthetic training pair generation
- Fine-tune bi-encoder
- node2vec graph embeddings
- Multi-signal fusion
