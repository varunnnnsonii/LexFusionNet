# LexiFusionNet — Execution Task Tracker

## Day 1: Project Setup + Config ✅
- [x] Restructure repo to match planned folder structure
- [x] Create `configs/config.yaml` with all paths and parameters
- [x] Create `src/config.py` (YAML → Python dataclass)
- [x] Update `requirements.txt`
- [x] Update `docker-compose.yml`
- [x] Update `Dockerfile`
- [x] Create `pyproject.toml` for package structure
- [x] Update `.gitignore`

## Day 2: Phase 0 — Data Audit ✅
- [x] Implement `src/data/cleaner.py`
- [x] Implement `src/data/parser.py`
- [x] Implement `src/diagnostics/data_audit.py`
- [x] Create `scripts/run_phase0.py`
- [x] Run audit — report generated at `artifacts/data_audit_report.json`

## Day 3: Full Corpus Parse + Metadata Store (NEXT SESSION)
- [ ] Run parser on all 26,688 files → `data/processed/parsed/`
- [ ] Implement `src/data/metadata_store.py` (SQLite)
- [ ] Load all parsed metadata into SQLite
- [ ] Write `tests/test_parser.py` — validate against known files

## Day 4: Chunker + BM25 Index
- [ ] Implement `src/data/chunker.py`
- [ ] Run chunking on all cases → `data/processed/chunks/`
- [ ] Implement `src/index/bm25_index.py`
- [ ] Build and serialize BM25 index

## Day 5: Dense Embeddings + Qdrant
- [ ] Start Qdrant via docker-compose
- [ ] Implement `src/index/dense_index.py`
- [ ] Batch-encode all chunks with bge-base-en-v1.5
- [ ] Upload vectors to Qdrant

## Day 6: Hybrid Retriever + First Eval
- [ ] Implement `src/retrieval/hybrid.py`
- [ ] Implement `src/eval/manual_eval.py`
- [ ] Select 10 test cases, run evaluation
