# Citation Header Analysis — Full Dataset Report

Comprehensive scan of all **26,661 files** in the dataset to understand citation header structures.

---

## Summary

| Metric | Count | % |
|---|---|---|
| Total files scanned | 26,661 | 100% |
| Has `Equivalent citations:` | 23,376 | **87.7%** |
| Has `CITATION:` block | 10,454 | 39.2% |
| Has BOTH | 10,454 | 39.2% |
| Has `CITATOR INFO` | 4,917 | 18.4% |
| **Has NEITHER (no citation header)** | **3,285** | **12.3%** |

> [!IMPORTANT]
> **3,285 files (12.3%)** have no `Equivalent citations:` or `CITATION:` header at all. But this does NOT mean they have no citation identity — see breakdown below.

---

## Three Eras of Citation Formatting

The dataset spans 1950–2025. IndianKanoon changed their text export format over the decades, creating **three distinct eras**:

### Era 1: Classic Format (1950–~2005)
```
Title vs Party on Date
Equivalent citations: 1969 AIR 560, 1969 SCR (1) 573
Author: ...
Bench: ...
           PETITIONER:
...
CITATION:
 1969 AIR  560            1969 SCR  (1) 573
 CITATOR INFO :
 R          1952 SC 119  (5)
ACT:
HEADNOTE:
JUDGMENT:
```
- **Both** `Equivalent citations:` AND `CITATION:` blocks present
- `CITATOR INFO` section lists forward citations (who cited this case later)
- Reporters: `AIR`, `SCR`, `SCC`, `SCALE`, `JT`, `ALL`, `BOM`, etc.

### Era 2: Transitional Format (~2006–2021)
```
Title vs Party on Date
Author: ...
Bench: ...
             CASE NO.:
Appeal (civil) 4570 of 2006
PETITIONER:
...
```
- **No** `Equivalent citations:` line
- **No** `CITATION:` block
- Uses `CASE NO.:` instead
- These files still have inline body citations (SCC references in the judgment text)

### Era 3: Modern INSC Format (2022–2025)
```
Title vs Party on Date
Author: ...
Bench: ...
2023 INSC 682                                            REPORTABLE
                         IN THE SUPREME COURT OF INDIA
```
- **No** `Equivalent citations:` line  
- The neutral citation `YYYY INSC NNN` appears as a standalone line near the top
- Supreme Court of India adopted the INSC neutral citation system in late 2023

---

## No-Citation Files by Year

| Year Range | Files with No Header Citation | Explanation |
|---|---|---|
| **2022** | 399/399 (100%) | Transition year — no INSC yet, no old format |
| **2023** | 400/400 (100%) | But 118 have `INSC` inline (not as `Equivalent citations:`) |
| **2024** | 395/395 (100%) | But 389 have `INSC` inline |
| **2025** | 397/397 (100%) | But 394 have `INSC` inline |
| **2021** | 159/400 (40%) | Mixed — some have old format, some transitional |
| **2010** | 91/400 (23%) | Transitional files |
| **2007–2008** | ~80/400 (20%) | Transitional files |
| **Pre-2005** | ~0-10% | Mostly complete headers |

---

## What This Means for Citation Extraction

### Files WITH header citations (~23,376 files)
These are straightforward — parse the `Equivalent citations:` line to get the **self-identity** of the case.

### Files WITHOUT header citations (~3,285 files) — breakdown:

| Category | Count | Strategy |
|---|---|---|
| Has `INSC` number inline | ~901 (2023-2025) | Extract `YYYY INSC NNN` via regex from first 500 chars |
| 2022 files (no INSC, no header) | ~399 | Use **filename + date** as identity; body still has SCC refs |
| Transitional 2006-2021 | ~1,500 | Use `CASE NO.:` + filename as identity; body has SCC refs |
| Other scattered | ~485 | Fallback to filename-derived ID |

> [!TIP]
> **Key Insight**: Even files with NO citation header still contain inline body citations (references to other cases using SCC/AIR/SCR format). The "header" tells us "who am I", while body extraction tells us "who do I cite". Both are needed for the network graph.

---

## Updated Count After This Analysis

- **Self-identifiable via header**: 23,376 + 901 (INSC) = **~24,277 files (91%)**
- **Require filename-derived identity**: **~2,384 files (9%)**
- **Body citations extractable from ALL files**: **~26,661 (100%)**
