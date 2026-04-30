# Phase 1: Citation Extraction & Network Graph Implementation Plan

This is the implementation plan for **Phase 1** of LexFusionNet, focusing on extracting citations accurately from the parsed jurisprudence text and constructing a robust citation network graph.

---

## User Review Required

> [!IMPORTANT]
> **No Code Changes Yet**: This plan outlines the next steps and infrastructure needed for Phase 1 as requested. Review this approach to ensure it aligns with your vision before we begin code modification.

> [!WARNING]
> **Tooling Selection**: The plan assumes using `networkx` for maintaining the graph due to the scale of the dataset (approx. 26k vertices). If you prefer another tool like graph-tool or neo4j, please let me know.

---

## Proposed Changes

We will approach Phase 1 logically across distinct stages, ensuring extraction and graphing are verifiable individually.

### Step 1: Deep Citation Extraction

#### [NEW] `src/pipeline/citation_extractor.py`
We need a more robust extraction engine to mine the body text of cases beyond standard header patterns.
- Regex rules for standard citation formats (e.g. `(1950) 1 SCR xyz`, `AIR 1950 SC xyz`).
- Normalization module to standardize citations across different permutations (e.g. reducing variations of the same volume/page format).
- Cross-referencing against existing cases' base citations.
- Outputs will be integrated into the `.jsonl` schemas updated in Phase 0.

### Step 2: Building the Citation Graph

#### [NEW] `src/network/citation_graph.py`
This module will handle generating the directed graph mapping documents.
- Nodes: Correspond to a Judgment `case_id` or canonical standard citation.
- Edges: Directed edges (A -> B means Case A cites Case B).
- Tools: Utilize `networkx` to represent and build the citation graph in-memory.
- Serialization: Methods to serialize the graph locally (e.g., as `.graphml` or `.gpickle` formats) to avoid costly full-rebuilds.

### Step 3: Network Analysis & Metrics

#### [NEW] `src/network/analysis.py`
Determine the "prestige" or historical importance of Indian Supreme Court cases.
- **PageRank Algorithm**: Computing global centrality and importance of cases.
- **Hubs & Authorities (HITS)**: Identify major precedent-setting authorities versus hub documents (cases that thoroughly survey law).
- **In-Degree/Out-Degree**: Basic volume metrics embedded into document metadata.
- Appending the network properties back to the case schemas so they can be exposed to searches (e.g., sorting by historical importance).

### Step 4: Integration with Pipeline orchestrator

#### [NEW] `scripts/run_phase1.py`
Orchestrator script for executing Phase 1 that will:
1. Load `parsed` jsonl data.
2. Execute batch deep citation extraction.
3. Build the directed citation network.
4. Compute network stats (PageRank).
5. Output final "enriched" `jsonl` files integrating PageRank scores.

---

## Open Questions

> [!IMPORTANT]
> **Data Granularity:** Should we keep non-Supreme Court canonical citations in the graph (e.g., British era PC citations, foreign citations, localized high courts), or focus edges strictly intra-corpus (Supreme Court to Supreme Court)?

---

## Verification Plan

### Automated Tests
```bash
python -m pytest tests/network/ -v
```

### Manual Verification
- Verify the graph file (`.graphml`) can be opened in a standard visualization tool like Gephi.
- Assert that foundational cases (e.g., Kesavananda Bharati) receive highest authoritative rankings from PageRank.
