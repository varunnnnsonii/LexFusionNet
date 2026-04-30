# ACT / STATUTE / TOPIC EXTRACTION — REALITY ANALYSIS

> **Generated**: 2026-04-21 | **Dataset**: 26,661 Supreme Court judgment text files (1950–2025)
> **Sample**: 350 files (300 random + 25 smallest + 25 largest)
> **Purpose**: Validate whether the current extraction pipeline design matches REAL data.

---

## Dataset Sample Overview

| Metric | Value |
|---|---|
| Total files in corpus | 26,661 |
| Files sampled | 350 |
| Year range | 1950–2025 (76 year directories) |
| File size — Minimum | 528 bytes |
| File size — Maximum | 2,583,365 bytes (2.5 MB) |
| File size — Median | 22,218 bytes |
| File size — Mean | 33,793 bytes |
| Files < 500 bytes | 0 |
| Files < 1 KB | 45 (0.17%) |
| Files < 5 KB | 1,610 (6.0%) |
| Files > 500 KB | 59 (0.22%) |
| Files > 1 MB | 7 |

> [!NOTE]
> No files are under 500 bytes — the pipeline's `< 500` reject threshold is never triggered.
> However, 1,610 files (6%) are under 5KB — many of these are short orders, dismissals, or stubs that may contain no extractable statutes or doctrine.

---

## Case Type Distribution

| Classification | Count | Percentage |
|---|---|---|
| **Mixed** (statutes + doctrine) | 263 | 75.1% |
| **Statute-based** (statutes, no doctrine) | 65 | 18.6% |
| **Unstructured** (no signals detected) | 19 | 5.4% |
| **Doctrine-only** | 2 | 0.6% |
| **ACT-based** (only ACT section) | 1 | 0.3% |

> [!IMPORTANT]
> **75% of files are Mixed** — they contain BOTH statute references AND doctrine language.
> "Doctrine-only" is virtually non-existent as a standalone category.
> The pipeline's bucket design (ACT → Statute → Doctrine → Fallback) implies these are separable. **They are not.** Almost every judgment mixes all three.

### Pre-2000 vs Post-2000 Structural Divide

| Era | Files in Sample | Has ACT: section | Has Pre-2000 format markers |
|---|---|---|---|
| Pre-2000 | 209 | 130 (62.2%) | 138 (66.0%) |
| Post-2000 | 141 | **0 (0.0%)** | 38 (27.0%, 2000s decade only) |

> [!CAUTION]
> **The ACT: section does NOT exist in ANY post-2000 file.** This is a complete structural break.
> Any pipeline logic that depends on the `ACT:` header block will silently produce nothing for ~60% of the corpus (post-2000 files).

---

## ACT Pattern Reality

### ACT: Section Presence

- Files with `ACT:` section: **130 / 350 (37.1%)**
- When present, 100% are clean and usable (multi-line structured text)
- **ACT: section ONLY exists in pre-2000 IndianKanoon format files**

### Decade-Level ACT Availability

| Decade | Total | Has ACT: | % |
|---|---|---|---|
| 1950s | 14 | 9 | 64.3% |
| 1960s | 45 | 38 | 84.4% |
| 1970s | 59 | 34 | 57.6% |
| 1980s | 52 | 29 | 55.8% |
| 1990s | 39 | 20 | 51.3% |
| **2000s** | **49** | **0** | **0.0%** |
| **2010s** | **60** | **0** | **0.0%** |
| **2020s** | **32** | **0** | **0.0%** |

> [!WARNING]
> The ACT: block is a legacy IndianKanoon artifact. It was progressively less common even in the 1970s-1990s (the older format wasn't always used). Post-2000, it is **categorically absent**.

### What the ACT: Block Actually Contains

When present, it contains a **natural-language summary** of the relevant statutory provisions, NOT a machine-parseable list. Example from a 1966 file:

```
ACT:
Insurance-Acceptance  and  covers notes issued  by  insurer-
Policy not issued-Conditions of policy whether applicable to
contract-Condition  allowing  parties  to  cancel   contract
whether reasonable-Cancellation by insurer when valid.
```

This is a **prose summary of legal issues**, not structured act/section data. Extracting specific statute names from this requires NLP, not regex.

### All Observed Header Variations

| Marker | Files | % of Sample |
|---|---|---|
| `Bench:` | 334 | 95.4% |
| `Equivalent citations:` | 308 | 88.0% |
| `Author:` | 265 | 75.7% |
| `RESPONDENT:` | 176 | 50.3% |
| `DATE OF JUDGMENT` | 176 | 50.3% |
| `ACT:` (standalone) | 130 | 37.1% |
| `HEADNOTE:` | 129 | 36.9% |
| `JUDGMENT:` | 122 | 34.9% |
| `JUDGMENT` (standalone) | 56 | 16.0% |
| `CITATOR INFO` | 53 | 15.1% |
| `PETITIONER:` | 43 | 12.3% |
| `ORDER` (standalone) | 25 | 7.1% |

---

## Statute Pattern Reality

### Detection Rates by Pattern

| Pattern | Files Present | % of Sample | Pipeline Catches? |
|---|---|---|---|
| `section X` / `Section X` | 283 | 80.9% | ✅ Yes |
| `S. X` / `s. X` | 287 | 82.0% | ❌ **No** |
| `Article X` | 135 | 38.6% | ✅ Yes |
| `Clause (x)` | 99 | 28.3% | ❌ No |
| `Rule X` | 87 | 24.9% | ✅ Yes |
| `Art. X` | 66 | 18.9% | ❌ No |
| `Clause X` | 43 | 12.3% | ❌ No |
| `Sec. X` | 29 | 8.3% | ❌ No |
| `Order X` (numeric) | 28 | 8.0% | ✅ Yes |
| `Order` (Roman numeral) | 25 | 7.1% | ❌ No |
| `u/s X` | 12 | 3.4% | ❌ **No** |

> [!WARNING]
> **`S. X` appears in 82% of files** — MORE than `section X` (80.9%). This is the most common abbreviated form in Indian legal writing. The pipeline regex **completely misses it**. The forms `Sec.`, `Art.`, `Clause`, and `u/s` are also missed.

### Pipeline Regex Coverage

- Files with **ANY** statute reference: **328 / 350 (93.7%)**
- Files caught by pipeline regex: **325 / 350 (92.9%)**
- Files **MISSED** by pipeline regex: **9 files (2.6%)**
- These 9 files use only abbreviated forms (`s.`, `Sec.`, `u/s`) that the pipeline regex doesn't cover

The pipeline catches most files because `Section X` and the full-name `XYZ Act, YYYY` patterns are so common. But it **misses significant detail within files** — abbreviated forms within individual judgments go undetected, meaning extracted statute lists are incomplete even when the file is "caught."

### Named Act Extraction Issues

> [!CAUTION]
> The pipeline's named act regex `[\w\s]+Act,?\s+\d{4}` is dangerously greedy. Observed problems:

**1. Partial name capture** — The regex often captures only the tail of an act name:
- "Application Act, 1937" instead of "Muslim Personal Law (Shariat) Application Act, 1937"
- "Conciliation Act, 1996" instead of "Arbitration and Conciliation Act, 1996"
- "the People Act, 1951" instead of "Representation of the People Act, 1951"
- "Information Act, 2005" instead of "Right to Information Act, 2005"
- "Public Property Act, 1984" instead of "Prevention of Damage to Public Property Act, 1984"

**2. Line-break corruption** — OCR/PDF conversion inserts newlines mid-name:
- `"India Act,\n1935"` — 15 occurrences
- `"India\nAct, 1935"` — 14 occurrences
- `"the Arms Act,\n1959"` — 8 occurrences

**3. Duplicates from variations** — The same act appears as multiple distinct entries:
- "the Limitation Act, 1963" (33x) vs "Limitation Act, 1963" (11x)
- "the Evidence Act, 1872" (13x) vs "the Indian Evidence Act, 1872" (15x) vs "the Evidence Act 1872" (10x)

**4. Abbreviations completely missed** — The most commonly referenced codes/acts use abbreviations:
- `IPC` — 110 files (31.4%), never caught as a named act
- `CrPC` — 79 files (22.6%), never caught
- `CPC` — 39 files (11.1%), never caught

### Named Code Pattern Issues

The Indian Penal Code appears in **19 different string variations** in just 350 files:
```
"the Indian Penal Code, 1860"  (19x)
"Indian Penal  Code, 1860"     (3x) — double space
"Indian Penal Code, 1860"      (3x) — no "the"
"Indian  Penal  Code\n1860"    (1x) — double space + newline
"Indian   Penal   Code,   1860" (1x) — triple spaces
```

---

## Doctrine Reality

### Frequency

- Files with doctrine-like language: **232 / 350 (66.3%)**
- Doctrine-ONLY files (no statutes at all): **2 / 350 (0.6%)**
- **Doctrine is almost NEVER standalone.** It co-occurs with statute references in virtually every case.

### Top Doctrine Phrases (occurrence counts across 350 files)

| Phrase | Occurrences | Category |
|---|---|---|
| fundamental rights | 2,173 | Constitutional |
| fundamental right | 1,014 | Constitutional |
| right to privacy | 724 | Constitutional |
| basic structure | 706 | Constitutional |
| right to life | 380 | Constitutional |
| ultra vires | 365 | Administrative |
| proportionality | 361 | Administrative |
| mala fide | 315 | Latin maxim |
| bona fide | 282 | Latin maxim |
| prima facie | 251 | Evidentiary |
| locus standi | 247 | Procedural |
| due process | 231 | Constitutional |
| natural justice | 210 | Administrative |
| res judicata | 112 | Procedural |
| right to die | 100 | Constitutional |
| burden of proof | 74 | Evidentiary |
| doctrine of separation | 63 | Constitutional |
| stare decisis | 50 | Procedural |
| beyond reasonable doubt | 48 | Evidentiary |
| ratio decidendi | 45 | Procedural |
| suo motu | 45 | Procedural |

### Newline Corruption in Doctrine Phrases

Same phrase appears as separate entries due to line breaks:
- `"fundamental rights"` (2,173x) + `"fundamental\nrights"` (156x) + `"fundamental\nright"` (68x)
- `"basic structure"` (706x) + `"basic\nstructure"` (91x)
- `"right to privacy"` (724x) + `"right to\nprivacy"` (70x)

> [!TIP]
> Any extraction for doctrine/statute MUST normalize whitespace (collapse `\n`, `\s+` → single space) BEFORE pattern matching. The current pipeline does not do this.

---

## Failure Cases

### Category 1: ACT Missing But Topics Exist in Body
- **183 files** — ACT: header absent but 5+ statute references found in body text
- This is the MAJORITY of the dataset. The pipeline cannot rely on ACT: blocks for topic identification.

### Category 2: Line-Break Corruption
- Named acts broken across lines: `India\nAct, 1935`, `the Arms Act,\n1959`
- Codes broken: `Indian Penal Code\n1860`, `Civil\nProcedure Code, 1908`
- Section references broken: `s.\n6`, `Sec.\n19`
- **This is an IndianKanoon page-breaking artifact.** The cleaner removes page markers but does **NOT** rejoin broken text lines.

### Category 3: Abbreviation Gap
- IPC, CrPC, CPC are used in **31%, 23%, 11%** of files respectively
- Pipeline has **zero** abbreviation handling
- `section 302 IPC` is a very common Indian legal phrase — the pipeline would extract `section 302` but lose `IPC` as the act name

### Category 4: No Header Markers at All
- **6 files** have absolutely no standard header markers
- These appear to be post-2020 files where the IndianKanoon format simplified further (no `Equivalent citations:`, no `Author:`, no `Bench:` in the original positions)

### Category 5: Giant Files
- 25 files > 500KB in sample (59 in full corpus)
- These are landmark constitutional law cases (Kesavananda Bharati, Puttaswamy, Ayodhya)
- They produce thousands of regex matches for a single file
- Current pipeline caps at 50 acts per file — **this silently drops data for the most important cases**

### Category 6: Very Small Files
- 25 files < 1KB in sample (45 in full corpus)
- These are typically short dismissal orders: "Leave dismissed" or "Appeal dismissed"
- They contain no statutes, no doctrine, no substantive content
- Pipeline marks them as `is_valid=False` correctly, but they still enter the quality scoring system as `REJECT`

---

## What Assumptions Are Wrong

### ❌ WRONG: "ACT: section is a reliable data source"
Reality: ACT: blocks exist in only **37% of files** and exclusively in **pre-2000 files**. The entire post-2000 corpus (60%+ of dataset) has no ACT section at all. The parser's `_extract_acts()` function actually extracts from **body text** using regex (not from the ACT: block), so the ACT: block is already effectively unused — but the mental model is wrong.

### ❌ WRONG: "Document formats are binary (pre-2000 vs post-2000)"
Reality: There are actually **three** distinct formats:
1. **1950s–1990s** (old IndianKanoon): PETITIONER/RESPONDENT/DATE OF JUDGMENT/ACT/HEADNOTE/CITATOR INFO/JUDGMENT
2. **2000s** (transitional): Has RESPONDENT/DATE OF JUDGMENT but NO ACT/HEADNOTE/CITATOR. Has Equivalent citations/Author/Bench.
3. **2010s–2020s** (modern): Only has Equivalent citations/Author/Bench (if even that). Body text starts immediately.

The 2000s decade is a hybrid that matches neither format cleanly.

### ❌ WRONG: "Doctrine is a separate extraction category"
Reality: Doctrine language appears in **66% of files** but is standalone in only **0.6%**. It's not a category — it's a **feature** that should be extracted alongside statutes, not instead of them.

### ❌ WRONG: "Pipeline regex covers sufficient statute patterns"
Reality: The pipeline misses `S. X`, `s. X`, `Sec. X`, `Art. X`, `u/s X`, `Clause X`, `Clause (x)`, and `Order (Roman numeral)`. These abbreviated forms are extremely common in Indian legal writing. The pipeline's `_STATUTE_RE` is far too conservative.

### ❌ WRONG: "Named act regex captures act names accurately"
Reality: The greedy `[\w\s]+Act,?\s+\d{4}` pattern produces **truncated names** (capturing only the tail) and **fails across line breaks**. The same act produces 3-5 different string variants.

### ⚠️ OVER-ENGINEERED: "CITATOR INFO extraction"
Found in only **15% of files** (53/350), exclusively pre-1990. The `_extract_citator_info()` function is well-implemented but covers a tiny minority of the corpus. Not wrong, just low-impact.

### ⚠️ MISSING: "Abbreviation handling (IPC, CrPC, CPC)"
These three abbreviations alone cover **31%, 23%, 11%** of files. The phrase `section 302 IPC` is possibly the most common statute citation in Indian criminal law. Not having abbreviation → full name mapping is a significant gap.

### ⚠️ MISSING: "Whitespace normalization before extraction"
Line-break corruption affects act names, code names, doctrine phrases, and section references. The cleaner does NOT rejoin text that was split by IndianKanoon page breaks. This creates duplicate entries for the same entity.

---

## What Must Be Fixed (Priority)

### 🔴 Critical (Must Fix Before Production)

1. **Add abbreviated statute patterns to regex**: `s.`, `S.`, `Sec.`, `Art.`, `u/s`, `Clause`, `Order [Roman]`. These cover **80%+ of files**. Without this, the extracted statute list for each judgment is incomplete.

2. **Add whitespace normalization BEFORE all extraction**: Collapse `\n`, `\r`, and multi-space into single space in a preprocessing step. This alone would eliminate thousands of false duplicates in acts, codes, and doctrine phrases.

3. **Add abbreviation lookup table**: Map `IPC` → `Indian Penal Code, 1860`, `CrPC` → `Code of Criminal Procedure, 1973`, `CPC` → `Code of Civil Procedure, 1908`. These are used in **31%+ of files** and are completely invisible to the current pipeline.

4. **Fix named act regex**: The greedy `[\w\s]+Act,?\s+\d{4}` captures partial names. Use a curated list of ~100 known Indian acts as primary lookup, with regex as fallback. This is more reliable than unbounded regex.

### 🟡 Important (Should Improve)

5. **Recognize three document formats, not two**: The parser currently has pre-2000/post-2000 logic. Add a 2000s-decade transitional format handler. The 2000s files have some but not all pre-2000 markers.

6. **Extract doctrine as features, not category**: Instead of classifying files as "Doctrine-only" (0.6% of cases), extract doctrine phrases as a separate field alongside statutes. They co-occur in 66% of files.

7. **Remove the 50-act cap or make it intelligent**: The current `result[:50]` cap silently drops statute references for landmark cases. Either raise the cap significantly or implement deduplication first, then cap.

8. **Normalize extracted act names**: Deduplicate `"the Limitation Act, 1963"` / `"Limitation Act, 1963"` / `"the Limitation Act 1908"` into canonical forms.

### 🟢 Optional (Nice to Have)

9. **Handle OCR corruption patterns**: `sectlon`, `sect1on`, `5ection` — these exist but are rare in this dataset (IndianKanoon text is generally clean, not raw OCR). Low priority.

10. **Extract section-act pairs**: Instead of just "Section 302" and "IPC" separately, extract the compound reference "Section 302 IPC" as a linked pair. This is the actual useful legal citation format.

11. **Year-aware parsing strategy**: Use decade-specific extraction logic rather than a one-size-fits-all approach. Pre-2000 files have rich structured headers; post-2010 files need body-first extraction.

---

## Final Verdict

### Reality Scores

| Dimension | Score | Assessment |
|---|---|---|
| ACT extraction reliability | **3 / 10** | Only works for 37% of corpus. Completely absent post-2000. |
| Statute extraction reliability | **7 / 10** | Pipeline catches most files but misses common abbreviations (`s.`, `u/s`, `Art.`). String normalization is absent. |
| Doctrine detection reliability | **6 / 10** | Patterns exist and are detectable, but the "doctrine-only" category is fictitious. Newline corruption creates duplicates. |
| Overall pipeline readiness | **5 / 10** | Core approach is sound. Execution has fixable gaps. |

### Are We Building the Right Pipeline for THIS Dataset?

**The overall architecture is correct. The implementation has significant blind spots.**

**What's right:**
- Regex-based statute extraction from body text works. 93.7% of files contain detectable statutes.
- The pre-2000 structured header parsing (HEADNOTE, CITATOR INFO) is well-done for the segments that have it.
- Quality scoring and validation framework is appropriate.
- The `_extract_body()` logic for finding judgment text works reasonably.

**What's wrong:**
- The pipeline mentally treats ACT/Statute/Doctrine as separate categories with a fallback chain. Reality: they are **concurrent features** in 75% of files. The extraction should be parallel (extract ALL signals from every file), not sequential (try ACT → try statute → try doctrine → fallback).
- The statute regex is too conservative — it misses the most common Indian legal abbreviations.
- No text normalization step before extraction means line-break artifacts create massive duplication.
- Abbreviation handling (IPC, CrPC, CPC) is entirely absent despite being used in 30%+ of files.

**Bottom line:** The pipeline needs **3-4 targeted fixes**, not a redesign. Fix the regex, add abbreviation handling, normalize whitespace, and treat all extraction as parallel features. The dataset is clean enough that regex-based extraction will work for 90%+ of cases. NLP fallback is needed only for the ~5% of truly unstructured files (short orders and dismissals that have no extractable legal content anyway).

> **BLUNT ASSESSMENT**: The pipeline is 70% of the way there. The remaining 30% is abbreviation handling, regex expansion, and text normalization — all straightforward engineering work, not architectural redesign. Ship the fixes, not a rewrite.

---

## Appendix: Two Real File Structures Observed

### Format 1: Pre-2000 (PETITIONER/ACT/HEADNOTE)
```
General Assurance Society Ltd vs Chandumull Jain And Anr on 7 February, 1966
Equivalent citations: 1966 AIR 1644, 1966 SCR (3) 500
Author: M. Hidayatullah
Bench: M. Hidayatullah, P.B. Gajendragadkar, K.N. Wanchoo, V. Ramaswami
           PETITIONER:
GENERAL ASSURANCE SOCIETY Ltd.
        Vs.
RESPONDENT:
CHANDUMULL JAIN AND ANR.
DATE OF JUDGMENT:
07/02/1966
...
ACT:
Insurance-Acceptance  and  covers notes issued  by  insurer-
Policy not issued-Conditions of policy whether applicable...
HEADNOTE:
Letters of acceptance of the proposals and cover notes  were
issued by the appellant Society...
JUDGMENT:
...
```

### Format 2: Post-2010 (Simple header, immediate body)
```
Abhilasha vs Parkash on 15 September, 2020
Equivalent citations: AIR 2020 SUPREME COURT 4355
Author: Ashok Bhushan
Bench: M.R. Shah, R. Subhash Reddy, Ashok Bhushan
                                                           REPORTABLE
                       IN THE SUPREME COURT OF INDIA
                      CRIMINAL APPELLATE JURISDICTION
                  CRIMINAL APPEAL NO. 615    of 2020
ASHOK BHUSHAN,J.
Leave granted.
2. This appeal has been filed by the appellant...
```

### Format 3: Post-2020 (Minimal/Missing headers)
```
[Case title] on [date]
[Immediate judgment text — no Equivalent citations, no Author, no Bench]
```
