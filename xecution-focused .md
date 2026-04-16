# LexiFusionNet — Phase 0 Stabilization & Data Quality Plan

## Objective

Bring the data pipeline to a **reliable, production-grade Phase 0 state** by:

* Ensuring data quality
* Eliminating fragile outputs
* Fixing infrastructure issues
* Adding defensive validation

This is NOT a modeling phase. Focus strictly on **data correctness and robustness**.

---

# 1. Advanced Data Audit (Quality Layer)

Extend the existing audit system to detect deeper data issues.

## 1.1 Required Checks

### A. Semantic Corruption

Detect nonsensical or statistically abnormal text.

* Extremely short/long average word length
* Empty or near-empty content

### B. Missing Sections

Check for absence of expected legal structure:

* JUDGMENT
* ORDER
* PETITIONER / RESPONDENT

### C. Broken Sentences

Detect abnormal sentence structure:

* Too many very short sentences
* Fragmented text

### D. Encoding Artifacts

Detect:

* Replacement characters (�)
* Null bytes
* Invalid Unicode remnants

### E. OCR Noise Patterns

Detect:

* Excessive special characters
* Random symbol bursts
* Spaced-out characters (e.g., "J U D G M E N T")

---

## 1.2 File Quality Scoring

For each file:

* Run all checks
* Assign a score (0–1)

### Classification:

* `OK` → score ≥ 0.8
* `REVIEW` → 0.6 ≤ score < 0.8
* `REJECT` → score < 0.6

---

## 1.3 Auto-Flagging

* Store quality flags in audit report
* Output list of:

  * rejected files
  * review-needed files

---

# 2. Data Format Refactor (CRITICAL)

## Problem

Current approach:

* Thousands of tiny `.json` files
* Heavy disk I/O
* Poor scalability

## Solution

### 2.1 Switch to JSONL

Store parsed data as:

* One file per year
* Each line = one record

### Structure:

```
artifacts/parsed/
  1950.jsonl
  1951.jsonl
```

### Record Example:

```json
{
  "title": "...",
  "date": "...",
  "body": "...",
  "quality_score": 0.87,
  "quality_flag": "OK"
}
```

---

## 2.2 Implementation Rules

* Buffer records in memory per year
* Write in batches (NOT per file)
* Avoid repeated open/close operations

---

## 2.3 Optional (Future)

* Parquet format for large-scale optimization

---

# 3. Infrastructure Fixes (MANDATORY)

## 3.1 Dependencies

Update `requirements.txt`:

```
PyMuPDF
```

---

## 3.2 Docker Fix

Fix incorrect entrypoint:

### Current (Broken):

```
run_phase1
```

### Correct:

```
run_phase0
```

Ensure container:

* starts successfully
* runs audit pipeline without crash

---

# 4. Defensive Testing (Parser Stability)

## Objective

Prevent silent parsing failures across messy legal text.

---

## 4.1 Create Test Suite

Directory:

```
tests/
```

File:

```
test_parser_headers.py
```

---

## 4.2 Required Test Cases

### Case 1 — Clean Input

* Proper header
* Valid metadata

### Case 2 — Missing Fields

* No date
* No citations

### Case 3 — OCR Noise

* Corrupted characters
* Broken formatting

### Case 4 — Irregular Formatting

* Extra whitespace
* Misaligned headers

### Case 5 — Edge Legal Formats

* Different eras
* Unusual structures

---

## 4.3 Validation Goals

Ensure:

* Parser does NOT crash
* Invalid data is flagged
* Valid data is correctly extracted

---

# 5. Execution Order (STRICT)

Follow this order exactly:

1. Fix infrastructure

   * requirements.txt
   * Docker CMD

2. Implement quality checks

   * scoring
   * auto-flagging

3. Refactor output format

   * switch to JSONL

4. Add defensive tests

5. Re-run full audit and validate outputs

---

# 6. Constraints

* Do NOT introduce ML models
* Do NOT optimize for scale prematurely
* Do NOT add orchestration tools (Airflow, etc.)
* Focus only on correctness and stability

---

# 7. Expected Outcome

After completion:

* Data pipeline runs reliably
* Dataset quality is measurable
* Bad data is automatically filtered
* Output format is scalable
* Parser is resistant to edge cases

---

# Final Instruction

Do NOT skip steps.
Do NOT optimize prematurely.
Do NOT add unnecessary complexity.

Focus on building a **clean, reliable data foundation**.
