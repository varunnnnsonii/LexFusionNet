# Phase 0 Stabilization — Task Tracker

## Step 1: Infrastructure Fixes
- [ ] Add PyMuPDF to requirements.txt
- [ ] Fix Dockerfile CMD from run_phase1 → run_phase0

## Step 2: Advanced Quality Checks
- [ ] Create `src/diagnostics/quality_checker.py`
- [ ] Integrate quality checker into `data_audit.py`

## Step 3: Output Format Refactor (JSONL)
- [ ] Add `parse_corpus_jsonl()` to `parser.py`
- [ ] Update `run_phase0.py` orchestrator

## Step 4: Defensive Tests
- [ ] Create `tests/test_parser_headers.py`
- [ ] Create `tests/test_quality_checker.py`

## Step 5: Validation
- [ ] Run pytest suite
- [ ] Run phase 0 pipeline smoke test
