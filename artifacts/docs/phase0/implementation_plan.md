# Phase 0 Stabilization & Data Quality Plan

Bring the data pipeline to a reliable, production-grade Phase 0 state by ensuring data quality, eliminating fragile outputs, fixing infrastructure issues, and adding defensive validation.

---

## User Review Required

> [!IMPORTANT]
> **Output format change**: The parsed data output switches from thousands of individual `.json` files to per-year `.jsonl` files. This affects any downstream code that reads parsed data. The old `parse_corpus()` function in `parser.py` will be replaced.

> [!WARNING]
> **Docker change**: The container entrypoint changes from `run_phase1` → `run_phase0`. If any CI/CD or deployment scripts reference the old command, they will need updating.

---

## Proposed Changes

Changes are grouped by component and ordered by execution dependency.

---

### Step 1: Infrastructure Fixes

#### [MODIFY] [requirements.txt](file:///home/vxrun/LexiFusionNet/requirements.txt)

Add `PyMuPDF` to the Phase 0 dependencies block:

```diff
 # === Phase 0: Data Audit & Parsing ===
 pyyaml>=6.0
 matplotlib>=3.8
+PyMuPDF>=1.24
```

#### [MODIFY] [Dockerfile](file:///home/vxrun/LexiFusionNet/Dockerfile)

Fix the incorrect entrypoint:

```diff
-# Default: run Phase 1 pipeline
-CMD ["python", "-m", "scripts.run_phase1"]
+# Default: run Phase 0 pipeline
+CMD ["python", "-m", "scripts.run_phase0"]
```

---

### Step 2: Advanced Quality Checks

#### [NEW] [quality_checker.py](file:///home/vxrun/LexiFusionNet/src/diagnostics/quality_checker.py)

New module implementing the 5-category quality scoring engine:

| Check | What it detects | Weight |
|---|---|---|
| **Semantic Corruption** | Abnormal avg word length (<2 or >15 chars), empty/near-empty content (<100 chars) | 0.20 |
| **Missing Legal Sections** | Absence of JUDGMENT/ORDER/PETITIONER/RESPONDENT keywords | 0.15 |
| **Broken Sentences** | >50% sentences under 4 words (fragmented text) | 0.20 |
| **Encoding Artifacts** | Replacement chars (`�`), null bytes, invalid Unicode sequences | 0.20 |
| **OCR Noise** | >15% special chars, spaced-out words (e.g. `J U D G M E N T`), random symbol bursts | 0.25 |

**Per-file output**:
```python
@dataclass
class QualityResult:
    score: float          # 0.0 – 1.0
    flag: str             # "OK" | "REVIEW" | "REJECT"
    issues: list[str]     # Human-readable list of detected problems
    check_scores: dict    # Per-check breakdown
```

**Classification thresholds**:
- `OK` → score ≥ 0.8
- `REVIEW` → 0.6 ≤ score < 0.8
- `REJECT` → score < 0.6

#### [MODIFY] [data_audit.py](file:///home/vxrun/LexiFusionNet/src/diagnostics/data_audit.py)

Integrate quality checker into the audit pipeline:
- Import and call `check_quality()` during the sample-based parsing phase
- Add `quality_summary` section to the audit report with counts of OK/REVIEW/REJECT files
- Output separate lists of rejected and review-needed files in the report

---

### Step 3: Output Format Refactor (JSONL)

#### [MODIFY] [parser.py](file:///home/vxrun/LexiFusionNet/src/data/parser.py)

Replace `parse_corpus()` function with `parse_corpus_jsonl()`:

- **Buffer records in memory per year** — accumulate all parsed records for a year
- **Write one `.jsonl` file per year** — each line is a JSON record
- **Embed quality scores** — each record includes `quality_score` and `quality_flag` fields
- **Batched writes** — single `open()` + write-all per year file (no per-file I/O)

Output structure:
```
data/processed/parsed/
  1950.jsonl
  1951.jsonl
  ...
  2025.jsonl
```

Each line in a `.jsonl` file:
```json
{
  "case_id": "...",
  "title": "...",
  "date_str": "1950-05-19",
  "year": 1950,
  "citations": [...],
  "author": "...",
  "bench": [...],
  "body": "...",
  "quality_score": 0.87,
  "quality_flag": "OK",
  "quality_issues": [],
  "is_valid": true
}
```

#### [MODIFY] [config.yaml](file:///home/vxrun/LexiFusionNet/configs/config.yaml)

No structural change needed — `parsed_data` path already points to `data/processed/parsed`. The `.jsonl` files will be written there instead of individual `.json` files.

#### [MODIFY] [run_phase0.py](file:///home/vxrun/LexiFusionNet/scripts/run_phase0.py)

Update the orchestrator to:
1. Run the audit (with quality checks)
2. Run the JSONL corpus parse
3. Print a final summary (total files, valid/invalid/rejected counts)

---

### Step 4: Defensive Parser Tests

#### [NEW] [test_parser_headers.py](file:///home/vxrun/LexiFusionNet/tests/test_parser_headers.py)

Test suite with 5 required test cases:

| Case | Description | Validation |
|---|---|---|
| **Clean Input** | Well-formed header, valid metadata, proper body | All fields extracted correctly, `is_valid=True` |
| **Missing Fields** | No date, no citations, minimal header | Parser doesn't crash, fallback values used, errors logged |
| **OCR Noise** | Corrupted chars (`�`), broken formatting | Parser doesn't crash, invalid data flagged |
| **Irregular Formatting** | Extra whitespace, misaligned headers, inconsistent casing | Parser handles gracefully, body extracted |
| **Edge Legal Formats** | Pre-1960 PETITIONER/RESPONDENT blocks, modern minimal format | Both eras parsed without crash |

#### [NEW] [test_quality_checker.py](file:///home/vxrun/LexiFusionNet/tests/test_quality_checker.py)

Tests for the quality scoring engine:
- Clean text → score ≥ 0.8 (OK)
- Encoding garbage → score < 0.6 (REJECT)
- Partial noise → 0.6 ≤ score < 0.8 (REVIEW)
- Empty text → score = 0 (REJECT)
- Boundary conditions for each check

---

### Step 5: Full Pipeline Validation

#### [MODIFY] [run_phase0.py](file:///home/vxrun/LexiFusionNet/scripts/run_phase0.py)

After all changes, the full pipeline will:
1. Run expanded audit (with quality scoring on sample)
2. Parse entire corpus → JSONL
3. Print final quality distribution summary
4. Write updated audit report to `artifacts/data_audit_report.json`

---

## Files Summary

| Action | File | Purpose |
|---|---|---|
| MODIFY | [requirements.txt](file:///home/vxrun/LexiFusionNet/requirements.txt) | Add PyMuPDF |
| MODIFY | [Dockerfile](file:///home/vxrun/LexiFusionNet/Dockerfile) | Fix CMD to run_phase0 |
| NEW | [quality_checker.py](file:///home/vxrun/LexiFusionNet/src/diagnostics/quality_checker.py) | Quality scoring engine |
| MODIFY | [data_audit.py](file:///home/vxrun/LexiFusionNet/src/diagnostics/data_audit.py) | Integrate quality checks |
| MODIFY | [parser.py](file:///home/vxrun/LexiFusionNet/src/data/parser.py) | Add JSONL output + quality embedding |
| MODIFY | [run_phase0.py](file:///home/vxrun/LexiFusionNet/scripts/run_phase0.py) | Orchestrate full pipeline |
| NEW | [test_parser_headers.py](file:///home/vxrun/LexiFusionNet/tests/test_parser_headers.py) | Parser stability tests |
| NEW | [test_quality_checker.py](file:///home/vxrun/LexiFusionNet/tests/test_quality_checker.py) | Quality checker tests |

---

## Open Questions

> [!IMPORTANT]
> **Full corpus parse**: The JSONL refactor includes parsing all 26,688 files. Should I run the full parse during this session, or only implement the code and validate with a small subset? A full run on the entire corpus will take several minutes.

---

## Verification Plan

### Automated Tests
```bash
cd /home/vxrun/LexiFusionNet
source venv/bin/activate
python -m pytest tests/ -v
```

### Infrastructure Verification
```bash
# Verify Docker builds & entrypoint
docker build -t lexifusionnet-test .
docker run --rm lexifusionnet-test python -c "import fitz; print('PyMuPDF OK')"
```

### Pipeline Smoke Test
```bash
# Run phase 0 on a small sample
python -m scripts.run_phase0
# Verify JSONL output exists
ls -la data/processed/parsed/*.jsonl | head -5
```
