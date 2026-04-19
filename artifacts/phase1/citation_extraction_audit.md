# Citation Extraction Audit — Where We Actually Stand

## The Verdict: You're at ~40, Not 70

The **extraction** is at ~85. The **graph** is at ~5. Overall, the system is non-functional for its intended purpose (building a usable citation network). But the good news: the fixes are surgical, not architectural.

---

## What Works Well ✅

| Aspect | Score | Evidence |
|---|---|---|
| **File coverage** | 92.4% | 24,622 / 26,661 files have self-citations extracted |
| **Body citation extraction** | 92.4% | 24,642 / 26,661 files have body citations found |
| **Case name extraction** | 97.6% | 26,030 files have `v.`/`vs.` references captured |
| **Zero errors** | 100% | 0 processing errors across all 26,661 files |
| **Reporter diversity** | Good | SCC (44.7%), AIR (19.7%), SCR (10.4%), SCALE (6.6%), JT (6.2%) |
| **Total citations extracted** | 172,612 | Avg ~7 body-cites per file — reasonable for SC judgments |
| **Three-era analysis** | Excellent | The header analysis doc is thorough and accurate |

> [!TIP]
> The extraction itself went from 25% recall → ~50%+ after optimization. The regex patterns in `extract_citations.py` are reasonably comprehensive. This is **good enough** for the network task.

---

## What's Critically Broken 🔴

### 1. **Graph Linkability: 1.3%** — THE Showstopper

```
Total body citations:  172,612
Resolved to known case:  2,199 (1.3%)
Unresolved (dangling):  170,413 (98.7%)
```

> [!CAUTION]
> **98.7% of citation edges cannot be created.** The entire point of extracting citations — building a PageRank/HITS network — is completely non-functional right now.

**Root cause: format mismatch between self-citations and body-citations.**

The `Equivalent citations:` header uses one format. The body text uses another. After extraction, they're stored as raw strings with no normalization, so they don't match:

```
SELF-CITATION (from header):    "2006 (10) SCC 261"
BODY-CITATION (from judgment):  "(2006) 10 SCC 261"
                                  ↑ parens moved    ↑ no parens
```

Same reporter, same year, same volume, same page — **same case** — but different string → no graph edge.

A simple normalizer that strips `()[]`, normalizes `SUPREME COURT → SC`, and collapses whitespace fixes this:

```python
# After normalization:
"2006 (10) SCC 261"  →  "2006 10 SCC 261"
"(2006) 10 SCC 261"  →  "2006 10 SCC 261"  ✅ MATCH
```

### 2. **2,028 Garbage Self-Citations** — Data Corruption

```
Bad/short self-cites (≤6 chars):  2,028 files
Examples:
  "2006"        ← just a bare year, not a citation
  "AIR"         ← just a reporter prefix
  "(2007) 2"    ← truncated parse
  "AIRONLINE"   ← not a citation, it's a website name
```

> [!WARNING]
> These pollute the self-citation index. When you build the graph, a node labeled `"2006"` will spuriously match thousands of body citations containing the substring "2006".

**Cause:** The `Equivalent citations:` header line gets comma-split, and fragments like `"2006 (10) SCC 261"` become `["2006 (10) SCC 261"]` — but sometimes the comma-split produces garbage like `"2006"` or `"AIR"` when the header line has ambiguous formatting.

### 3. **Orphaned Dummy Extractor in `src/pipeline/`**

| File | Lines | Used for output? |
|---|---|---|
| `src/pipeline/citation_extractor.py` | 46 | ❌ NO — this is the "dummy" from Turn 3 |
| `experiments/citations/extract_citations.py` | 146 | ✅ YES — this produced the JSONL |

The production-grade extractor lives in `experiments/` while a stale 46-line dummy sits in `src/pipeline/`. This will cause confusion. The `src/pipeline` version:
- Has fewer reporter patterns
- Has no self-citation extraction (no header parsing)
- Has no concurrent processing
- Has no JSONL output
- Was never used for the actual extraction run

### 4. **`case_names` Field is Noisy**

The `RE_CASE_NAMES` regex produces 251,335 case name entries — almost 10 per file. Many are:
- Truncated: `"In State of M.P. v. Mansingh & Ors"` → good
- Garbage: `"SCC Hasham Abbas vs Usman Abbas"` → contains reporter name
- Self-references: The case citing itself → should be filtered

These aren't usable for graph matching yet and aren't normalized.

---

## What's Missing From the Plan 🟡

The [implementation_plan.md](file:///home/vxrun/LexiFusionNet/artifacts/phase1/implementation_plan.md) outlines 4 steps. Here's where each actually stands:

| Step | Status | Notes |
|---|---|---|
| **Step 1: Citation Extraction** | 🟡 ~80% done | Extraction works, normalization broken |
| **Step 2: Citation Graph** | 🔴 0% done | `src/network/citation_graph.py` doesn't exist |
| **Step 3: Network Analysis** | 🔴 0% done | `src/network/analysis.py` doesn't exist |
| **Step 4: Pipeline Orchestrator** | 🔴 0% done | `scripts/run_phase1.py` doesn't exist |

The plan also has an **unanswered open question**:
> Should we keep non-Supreme Court canonical citations in the graph (British era PC citations, foreign citations, localized high courts)?

---

## Prioritized Action Plan

### 🔴 Priority 1: Fix Normalization (turns 1.3% → ~40-60% linkability)

Create a proper `normalize_citation()` function:
1. Strip all `()[]` characters
2. Normalize `SUPREME COURT` → `SC`
3. Collapse whitespace
4. Uppercase
5. Validate: must have `YEAR + REPORTER + PAGE` structure, else discard

Apply this to **both** self-citations and body-citations at extraction time.

### 🔴 Priority 2: Clean Garbage Self-Citations

Filter out self-citations that are:
- ≤ 6 characters (bare years, bare reporter names)
- Don't contain both a year (`\d{4}`) and a page number
- Are website names (`AIRONLINE`)

### 🟡 Priority 3: Promote Extractor to `src/pipeline/`

Replace the 46-line dummy with the real 146-line extractor, with normalization integrated. The single source of truth should be `src/pipeline/citation_extractor.py`.

### 🟡 Priority 4: Build the Graph (Step 2-4 of the plan)

Only **after** normalization is fixed. Otherwise you'll build a graph with 2,199 edges when you should have ~50,000+.

---

## Expected Outcome After Fixes

| Metric | Current | After Fix |
|---|---|---|
| Self-citation coverage | 92.4% | ~93-94% (garbage removed) |
| Body citation extraction | 92.4% | Same |
| **Graph linkability** | **1.3%** | **~40-60%** |
| Usable graph edges | ~2,199 | **~70,000-100,000** |
| Garbage self-cites | 2,028 | ~0 |

> [!IMPORTANT]
> The ceiling for linkability is ~40-60%, not 100%. Many body citations reference cases **outside your corpus** (High Court cases, British Privy Council, US Supreme Court). That's expected and correct — those become dangling leaf nodes in the graph, which is fine for PageRank computation.

---

## Verdict

This is **not** a "90 to 92" situation. The extraction coverage is strong, but the **core deliverable** (a usable citation network graph) is at **1.3% functionality** due to a normalization bug. The fix is straightforward — a ~20-line normalization function applied consistently. After that, you can proceed to graph construction (Step 2-4) with confidence.
