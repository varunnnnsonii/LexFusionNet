# Neo4j Architecture & Schema Design for LexiFusionNet

> Source file: `data/processed/phase1/citations_network.jsonl`
> Records: 26,661 | Years: 1950–2025 | Size: ~39.6 MB

---

## PART 1 — SOURCE DATA PROFILE

### 1.1 Record Schema (citations_network.jsonl)

```
{
  "file_id":        string,         // filename stem — PRIMARY KEY candidate
  "year":           string,         // "1950"–"2025" (string, not int)
  "self_citations": [string, ...],  // avg 2.3, max 5 — normalized reporter codes
  "cited_cases":    [string, ...],  // avg 6.2, max 351 — body citation codes
  "case_names":     [string, ...],  // avg 9.2, max 641 — "Party v. Party" strings
  "statutes": {
    "ipc_sections":        [string],  // 16.3% fill rate
    "bns_sections":        [string],  // 0.0% (new law, 4 files)
    "crpc_sections":       [string],  // 14.3%
    "bnss_sections":       [string],  // 0.1% (new law, 14 files)
    "cpc_sections":        [string],  // 5.4%
    "constitutional_refs": [string],  // 40.7%
    "order_rules":         [string],  // 5.0%
    "named_act_sections":  [string],  // 54.5% — richest category
    "rw_combinations":     [string],  // 13.0%
    "bare_section_lists":  [string],  // 10.5%
    "raw_act_block":       string,    // 42.9% — raw header text
    "additional_acts":     [string]   // 5.6% — fallback extraction
  }
}
```

### 1.2 Volume Summary

| Metric | Count |
|--------|-------|
| Case records | 26,661 |
| Total self_citations | 60,935 |
| Total cited_cases (outbound edges) | 165,440 |
| Total case_names | 244,611 |
| Records with any statute | 25,428 (95.4%) |
| Records with NO statute | 1,233 (4.6%) |
| Estimated unique citation strings | ~40,000–60,000 |
| Estimated unique statute strings | ~15,000–25,000 |
| Estimated unique Act names | ~500–800 |

### 1.3 Current Limitations to Solve

| Problem | Impact | Neo4j Solution |
|---------|--------|----------------|
| No join key between Phase 0 and Phase 1 data | Cannot merge parsed text with citation graph | `file_id` becomes canonical; Phase 0 data joined via filename stem reconstruction |
| Citations are flat string arrays | No graph traversal possible | Citation strings become edges; matching self_citations resolves case identity |
| `cited_cases` point to reporter codes, not file_ids | Cannot link citation → target Case node | Build a **Citation Resolution Index**: self_citations → file_id reverse lookup |
| No inverse lookups | "Who cites me?" requires full scan | Neo4j relationships are bidirectional by nature |
| Statute strings are verbose, un-normalized | "Section 302 IPC" vs "Section 302 of the Indian Penal Code" are separate | Canonicalization layer during ingestion |
| `case_names` extremely noisy | 244K strings, many garbage | Filter during ingestion; only create CaseName nodes for clean entries |
| `year` is string | Type inconsistency | Cast to integer during ingestion |

---

## PART 2 — GRAPH DATA MODEL

### 2.1 Node Types

#### Node: `Case`

The primary entity. One node per JSONL record.

| Property | Type | Source | Indexed? | Notes |
|----------|------|--------|----------|-------|
| `file_id` | STRING | `file_id` | **UNIQUE constraint** | Primary key. Filename stem. |
| `year` | INTEGER | `int(year)` | Range index | For temporal queries |
| `title` | STRING | Derived from `file_id` | Full-text index | Human-readable, reconstructed from filename |
| `self_citations` | LIST<STRING> | `self_citations` | — | Kept as property for reference |
| `citation_count` | INTEGER | `len(cited_cases)` | Range index | Outbound citation degree |
| `statute_count` | INTEGER | computed | Range index | Total statutes referenced |
| `has_raw_act_block` | BOOLEAN | `bool(raw_act_block)` | — | Pre-2000 indicator |

**Justification:** Each judgment is the fundamental unit of legal authority. The `file_id` is the only stable, unique identifier across the dataset. Year and citation counts enable efficient filtering and authority ranking.

**Expected count:** 26,661 nodes.

---

#### Node: `Citation`

A canonical reporter citation code (e.g., "2006 10 SCC 261"). Serves as the **identity resolution bridge** — multiple Cases may share the same Citation (via self_citations), and body citations reference these codes.

| Property | Type | Source | Indexed? |
|----------|------|--------|----------|
| `code` | STRING | normalized citation string | **UNIQUE constraint** |
| `reporter` | STRING | extracted (AIR, SCC, SCR, etc.) | Index |
| `year` | INTEGER | extracted from code | Range index |

**Justification:** Citations are the currency of legal authority. A Citation node serves dual purpose: (1) identity anchor for Cases (a Case "has" its self_citations), and (2) target for citation edges. Without this node, citation resolution is impossible since `cited_cases` contains reporter codes, not file_ids.

**Expected count:** 40,000–60,000 nodes (union of all unique self_citations + cited_cases strings).

---

#### Node: `Statute`

A canonical statute/act reference. Created by normalizing and deduplicating the 11 list-type statute fields.

| Property | Type | Source | Indexed? |
|----------|------|--------|----------|
| `canonical_name` | STRING | normalized string | **UNIQUE constraint** |
| `category` | STRING | source field name (ipc_sections, crpc_sections, etc.) | Index |
| `act_name` | STRING | extracted Act name (e.g., "Indian Penal Code") | Index |
| `section` | STRING | extracted section number (e.g., "302") | Index |

**Justification:** Statutes referenced across cases form a parallel knowledge structure. Statute co-occurrence is a strong signal for case similarity. The `category` property preserves the extraction source for debugging.

**Expected count:** 15,000–25,000 nodes (after deduplication/normalization).

---

#### Node: `Act`

A named legislative Act or Code (e.g., "Indian Penal Code", "Constitution of India"). Parent of Statute nodes.

| Property | Type | Source | Indexed? |
|----------|------|--------|----------|
| `name` | STRING | extracted/normalized | **UNIQUE constraint** |
| `abbreviation` | STRING | "IPC", "CrPC", etc. | Index |
| `year_enacted` | INTEGER | extracted if available | Range index |
| `act_type` | STRING | "penal", "procedural", "constitutional", "regulatory" | Index |

**Justification:** Acts are the legislative containers for sections. Modeling them as separate nodes enables traversal from Act → Sections → Cases, and provides a natural grouping for legal topic clustering.

**Expected count:** 500–800 nodes.

---

### 2.2 Relationship Types

#### `(Case)-[:CITES]->(Citation)`

Created from each entry in `cited_cases[]`. This is the core citation network edge.

| Property | Type | Notes |
|----------|------|-------|
| (none initially) | — | Pure structural relationship |

**Cardinality:** avg 6.2, max 351 per Case. Total edges: ~165,440.

**Justification:** This is the directed citation graph. Combined with `HAS_CITATION`, it enables full citation chain traversal: Case A -[:CITES]-> Citation X <-[:HAS_CITATION]- Case B means "A cites B".

---

#### `(Case)-[:HAS_CITATION]->(Citation)`

Created from each entry in `self_citations[]`. Links a Case to its own identity citations.

| Property | Type | Notes |
|----------|------|-------|
| (none initially) | — | Identity relationship |

**Cardinality:** avg 2.3, max 5 per Case. Total edges: ~60,935.

**Justification:** This is the identity resolution mechanism. When Case A's `cited_cases` contains "2006 10 SCC 261", and Case B's `self_citations` contains the same string, then A cites B. The Citation node is the join point.

---

#### `(Case)-[:REFERENCES]->(Statute)`

Created from each statute mention across all 11 list-type statute fields.

| Property | Type | Notes |
|----------|------|-------|
| `category` | STRING | Which statute field it came from |
| `raw_text` | STRING | Original extracted string before normalization |

**Cardinality:** varies widely. Total edges: estimated 200,000–300,000.

**Justification:** Statute references are the primary structural signal for legal topic clustering. Two cases referencing the same Section 302 IPC are likely both murder cases, regardless of whether they cite each other.

---

#### `(Statute)-[:PART_OF]->(Act)`

Links a specific section/article to its parent Act.

| Property | Type | Notes |
|----------|------|-------|
| (none) | — | Hierarchical containment |

**Cardinality:** 1:1 for each Statute. Total edges: 15,000–25,000.

**Justification:** Enables "show me all sections of the Evidence Act cited across the corpus" queries and Act-level aggregation.

---

#### `(Case)-[:MENTIONS_CASE]->(Case)` (Optional/Derived)

Resolved citation links — only created when a `cited_cases` entry matches a known `self_citations` entry and the target Case exists in the graph.

| Property | Type | Notes |
|----------|------|-------|
| `via_citation` | STRING | The citation code that linked them |

**Cardinality:** This is the resolved subset of CITES. Expected: 30–60% of CITES edges may resolve.

**Justification:** Direct case-to-case links enable shortest-path queries, PageRank, and authority computation without traversing through Citation nodes. Created as a **derived/materialized** relationship after initial load.

---

### 2.3 Graph Hierarchy Diagram

```
        [Act]
          |
       PART_OF
          |
      [Statute]
          ^
          |
      REFERENCES
          |
       [Case] ---CITES--->    [Citation]
          |                        ^
          |                        |
          +----HAS_CITATION--------+
          |
          +---MENTIONS_CASE--->[Case]  (derived)
```

### 2.4 Scale Estimates

| Element | Count | Growth Rate |
|---------|-------|-------------|
| Case nodes | 26,661 → millions | ~500–2,000/year (SC only) |
| Citation nodes | 40,000–60,000 | Grows with cases |
| Statute nodes | 15,000–25,000 | Slow (finite statute space) |
| Act nodes | 500–800 | Very slow |
| CITES edges | 165,440 | Grows O(cases × avg_citations) |
| HAS_CITATION edges | 60,935 | Grows O(cases × avg_self_cites) |
| REFERENCES edges | 200,000–300,000 | Grows O(cases × avg_statutes) |
| MENTIONS_CASE edges | 50,000–100,000 | Grows with resolution rate |
| **Total graph elements** | **~600,000** | — |

---

## PART 3 — CITATION RESOLUTION STRATEGY

This is the most critical design challenge. The JSONL has `cited_cases` as reporter code strings (e.g., "2000 7 SCC 561"), and we need to resolve these to actual Case nodes.

### 3.1 Resolution Algorithm

**Step 1: Build Reverse Lookup Index**

During ingestion, for every Case record, index each `self_citations` string → `file_id`:

```
"2006 10 SCC 261" → "Pitta_Naveen_Kumar_Ors_vs_Raja_Narasaiah_Zangiti_Ors_on_14_September_2006_1"
"2006 AIR SCW 4930" → "Pitta_Naveen_Kumar_Ors_vs_Raja_Narasaiah_Zangiti_Ors_on_14_September_2006_1"
```

This is a Python dict: `{citation_code: file_id}`.

With 60,935 self_citations across 26,661 cases, this is a small in-memory index (~5 MB).

**Step 2: Resolve cited_cases**

For each `cited_cases` entry, look up in the reverse index. If found, create a `MENTIONS_CASE` edge. If not found, the Citation node remains as an "unresolved" external reference (which is still valuable — it may point to a High Court judgment or a case not in our corpus).

**Step 3: Estimate Resolution Rate**

- 165,440 total body citations
- ~60,935 unique self_citation codes in the corpus
- Expected resolution: 30–60% (many citations point outside the SC corpus — to High Courts, Privy Council, foreign courts, etc.)
- Unresolved citations remain as Citation nodes with no inbound HAS_CITATION edge

### 3.2 Collision Handling

Multiple Cases may share the same self_citation code (e.g., if the same citation is extracted differently). Strategy:
- If one citation_code maps to multiple file_ids, prefer the one whose `year` matches the citation year
- Log collisions for manual review
- In Neo4j, a Citation node can have multiple HAS_CITATION edges (this is a valid 1:N case — parallel citations)

---

## PART 4 — STATUTE NORMALIZATION STRATEGY

### 4.1 The Problem

The same legal provision appears in many forms:
- "Section 302 IPC"
- "Section 302 of the Indian Penal Code"
- "Section 302 of the Indian Penal Code, 1860"
- "section 302 I.P.C."
- "s. 302 IPC"

These should all map to ONE Statute node with canonical_name = `"Section 302, Indian Penal Code, 1860"`.

### 4.2 Normalization Pipeline

**Layer 1: Category-Based Routing**
The JSONL already categorizes statutes into 11 fields. Use the field name to determine the parent Act:
- `ipc_sections` → Act: "Indian Penal Code, 1860"
- `bns_sections` → Act: "Bharatiya Nyaya Sanhita, 2023"
- `crpc_sections` → Act: "Code of Criminal Procedure, 1973"
- `bnss_sections` → Act: "Bharatiya Nagarik Suraksha Sanhita, 2023"
- `cpc_sections` → Act: "Code of Civil Procedure, 1908"
- `constitutional_refs` → Act: "Constitution of India, 1950"
- `order_rules` → Act: "Code of Civil Procedure, 1908" (Orders are part of CPC)

**Layer 2: Section Number Extraction**
From each statute string, extract the section/article number using regex:
- "Section 302 IPC" → section = "302"
- "Article 14 of the Constitution" → section = "14"
- "Section 302(1)(a)" → section = "302(1)(a)"

**Layer 3: Canonical Name Construction**
`canonical_name = f"Section {section}, {act_full_name}"`

Example: `"Section 302, Indian Penal Code, 1860"`

**Layer 4: named_act_sections Handling**
This field contains diverse Act references. Parse the Act name from the string:
- "Section 30 of the Indian Evidence Act, 1872" → Act: "Indian Evidence Act, 1872", Section: "30"
- Build an Act synonym registry: {"Evidence Act" → "Indian Evidence Act, 1872", "NDPS Act" → "Narcotic Drugs and Psychotropic Substances Act, 1985", ...}

**Layer 5: raw_act_block and additional_acts**
These are lower-quality extractions. Parse with best-effort regex, tag with `quality: "low"` property.

### 4.3 Supernode Risk: High-Frequency Statutes

Some statutes will be referenced by thousands of Cases:
- Article 14 (equality): referenced in 10,845 files (40.7% of corpus)
- Section 302 IPC (murder): referenced in 4,344+ files

These become **supernodes** in the graph. Mitigation strategies:
- Do NOT traverse through Statute supernodes for case similarity (use property-based filtering instead)
- For "find similar cases", use statute co-occurrence vectors, not raw graph traversal
- Consider a `popularity` property on Statute nodes to flag supernodes (>1000 references)

---

## PART 5 — INDEXING STRATEGY

### 5.1 Constraints (Uniqueness + Existence)

| Node Label | Property | Constraint Type |
|------------|----------|-----------------|
| Case | file_id | UNIQUE |
| Citation | code | UNIQUE |
| Statute | canonical_name | UNIQUE |
| Act | name | UNIQUE |

### 5.2 Indexes

| Index Type | Node/Rel | Property | Purpose |
|------------|----------|----------|---------|
| Range | Case | year | Temporal filtering |
| Range | Case | citation_count | Authority ranking |
| Range | Case | statute_count | Complexity filtering |
| Range | Citation | year | Temporal citation queries |
| Text | Case | title | Free-text case search |
| Text | Statute | canonical_name | Statute lookup |
| Composite | Case | (year, citation_count) | Year-scoped authority queries |
| Lookup | Statute | category | Category filtering |
| Lookup | Act | act_type | Act type filtering |

### 5.3 Full-Text Search Indexes

Create Neo4j full-text indexes (backed by Lucene) on:
- `Case.title` — for case name search
- `Statute.canonical_name` — for statute lookup
- `Act.name` — for Act discovery

---

## PART 6 — QUERY STRATEGY (Patterns, Not Cypher)

### 6.1 Precedent Search

**"Find cases that are cited by the same cases that cite my query case"**
- Pattern: Case A → CITES → Citation X ← HAS_CITATION ← Case B → CITES → Citation Y ← HAS_CITATION ← Case C
- Depth: 2 hops through Citation resolution
- Filter: Year range, statute overlap
- Rank by: In-degree of target case (authority), statute overlap score

### 6.2 Citation Chain

**"What is the chain of authority from Case A to Case B?"**
- Pattern: Shortest path from A to B through MENTIONS_CASE relationships
- Depth: Capped at 5–6 hops (legal citation chains rarely exceed this)
- Output: The intermediate cases forming the chain

### 6.3 Authority Ranking

**"What are the most authoritative cases on Section 302 IPC?"**
- Pattern: Find Statute(canonical_name="Section 302, IPC, 1860") ← REFERENCES ← Cases
- Rank by: In-degree count of each Case (how many other cases cite it)
- This is a localized PageRank / in-degree computation

### 6.4 Statute Co-Occurrence

**"What other statutes are commonly cited alongside Section 21 NDPS Act?"**
- Pattern: Statute S ← REFERENCES ← Cases → REFERENCES → Other Statutes
- Aggregate: Count co-occurrence frequency
- Filter: Minimum co-occurrence threshold

### 6.5 Legal Issue Clustering

**"Find cases dealing with similar legal issues"**
- Pattern: Cases sharing 3+ Statute references AND within same Act
- Enrichment: Combine with semantic similarity from embeddings
- This is a hybrid graph + vector query

### 6.6 Temporal Evolution

**"How has the interpretation of Article 21 evolved over time?"**
- Pattern: Find all Cases referencing Article 21, ordered by year
- Overlay: Citation links between these cases show the doctrinal evolution chain
- Filter: Only cases with high in-degree (seminal judgments)

### 6.7 Query Performance Expectations

| Query Type | Expected Latency | Traversal Depth | Notes |
|------------|-----------------|-----------------|-------|
| Direct citation lookup | <10ms | 1 hop | Simple property match |
| Citation resolution | <50ms | 2 hops | Through Citation nodes |
| Authority ranking | 50–200ms | 2 hops + aggregation | Needs in-degree computation |
| Shortest path | 100–500ms | 3–6 hops | BFS with depth limit |
| Statute co-occurrence | 200–1000ms | 2 hops + aggregation | Watch for supernodes |
| Community detection | seconds | Full graph | Batch job, not real-time |

---

## PART 7 — RAG + EMBEDDING ARCHITECTURE

### 7.1 Where Neo4j Helps and Where It Does NOT

| Capability | Neo4j | Vector DB (Qdrant) | Winner |
|------------|-------|-------------------|--------|
| "Cases citing this case" | Excellent (traversal) | Cannot do | Neo4j |
| "Cases on same topic" | Good (statute overlap) | Excellent (semantic) | Hybrid |
| "Similar legal reasoning" | Cannot do | Excellent (embedding similarity) | Qdrant |
| "Citation chain A→B" | Excellent (shortest path) | Cannot do | Neo4j |
| "All cases under Section 302" | Excellent (index lookup) | Can do with metadata filter | Neo4j |
| "Fuzzy legal concept search" | Cannot do | Excellent | Qdrant |
| "Authority/influence ranking" | Excellent (PageRank) | Cannot do | Neo4j |

**Conclusion:** Neither Neo4j nor Qdrant alone is sufficient. The architecture MUST be hybrid.

### 7.2 Hybrid Retrieval Architecture

```
User Query
    |
    v
+-------------------+
| Query Router      |  Determines query type
+-------------------+
    |           |
    v           v
+--------+ +--------+
| Neo4j  | | Qdrant |
| Graph  | | Vector |
| Query  | | Search |
+--------+ +--------+
    |           |
    v           v
+-------------------+
| Result Merger     |  RRF or weighted fusion
+-------------------+
    |
    v
+-------------------+
| Context Assembler |  Pulls full text, citations, statute context
+-------------------+
    |
    v
+-------------------+
| Reranker          |  cross-encoder scoring
+-------------------+
    |
    v
  Final Results
```

### 7.3 Graph-Enhanced RAG Strategy

**Step 1: Seed Retrieval**
- Vector search in Qdrant returns top-K semantically similar chunks
- Each chunk is linked to a Case via `file_id`

**Step 2: Graph Expansion**
- For each seed Case, traverse Neo4j:
  - Get cases that cite it (1-hop inbound MENTIONS_CASE)
  - Get cases it cites (1-hop outbound)
  - Get cases sharing 2+ Statute references
- Collect expanded candidate set

**Step 3: Graph-Aware Reranking**
- Score candidates using the fusion weights from config.yaml:
  - α=0.3: hybrid RRF score (BM25 + dense)
  - β=0.2: citation proximity (graph distance)
  - γ=0.1: statute overlap count
  - δ=0.4: reranker score

**Step 4: Context Assembly**
- For final top-K results, assemble context including:
  - Case body text chunk
  - Citation chain to query case (if exists)
  - Shared statute references
  - Authority signal (in-degree)

### 7.4 Embedding Strategy

| Component | Model | Dimension | Storage |
|-----------|-------|-----------|---------|
| Chunk embeddings | BAAI/bge-base-en-v1.5 | 768 | Qdrant |
| Graph embeddings (node2vec) | gensim Word2Vec | 128 | Neo4j node property or separate |
| Statute embeddings | Same as chunk model | 768 | Optional, for statute similarity |

**Graph embeddings** encode structural position (who cites whom, which statutes co-occur). **Text embeddings** encode semantic meaning. The fusion of both provides citation-aware semantic retrieval.

### 7.5 Chunking Strategy for Vector DB

- Source: Phase 0 JSONL body text (from `data/processed/phase0/yearwise_headnotes(extracted)/`)
- Chunk size: 400 tokens (as configured)
- Overlap: 40 tokens
- Max chunks per case: 50
- Each chunk metadata includes: `file_id`, `year`, `chunk_index`
- `file_id` is the join key to Neo4j Case nodes

---

## PART 8 — SCALABILITY & PERFORMANCE

### 8.1 Current Scale Assessment

With ~600K total graph elements (nodes + edges), this is a **small graph** for Neo4j. It fits entirely in memory on a machine with 8GB+ RAM. No sharding or Fabric needed at this scale.

### 8.2 Memory Sizing

| Component | Estimate |
|-----------|----------|
| Node store | ~5 MB (26K Case + 60K Citation + 25K Statute + 800 Act) |
| Relationship store | ~15 MB (~500K edges) |
| Property store | ~50 MB (strings, lists) |
| Indexes | ~30 MB |
| Page cache recommended | 256 MB |
| Heap recommended | 1–2 GB |
| **Total Neo4j memory** | **~2 GB comfortable** |

### 8.3 At Scale (Millions of Cases)

If the system scales to all Indian courts (millions of cases, hundreds of millions of edges):

| Concern | Strategy |
|---------|----------|
| Supernode problem | Statute nodes like "Article 14" could have millions of edges. Use relationship type partitioning or avoid traversal through supernodes for similarity queries. |
| Memory pressure | Move to Neo4j Aura Professional or self-hosted with 32+ GB RAM. |
| Write throughput | Batch ingestion with `UNWIND` + periodic commit (10K records per transaction). |
| Read latency | Ensure hot working set fits in page cache. Profile and tune HNSW if using Neo4j vector index. |
| Sharding | Neo4j Fabric for federation across databases (e.g., by decade or court). |

### 8.4 Deployment Recommendation

| Scale | Recommendation |
|-------|---------------|
| Current (26K cases) | Neo4j Community Edition, single instance, 4GB RAM, local SSD |
| Medium (100K–500K cases) | Neo4j Enterprise or Aura Professional, 16GB RAM |
| Large (1M+ cases) | Neo4j Aura Enterprise or self-hosted cluster, 64GB+ RAM, Fabric sharding |

### 8.5 Docker Integration

Add Neo4j to the existing `docker-compose.yml`:

```yaml
neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"   # Browser
    - "7687:7687"   # Bolt
  volumes:
    - neo4j_data:/data
    - neo4j_plugins:/plugins
  environment:
    - NEO4J_AUTH=neo4j/lexifusionnet
    - NEO4J_PLUGINS=["apoc","graph-data-science"]
    - NEO4J_server_memory_heap_initial__size=1g
    - NEO4J_server_memory_heap_max__size=2g
    - NEO4J_server_memory_pagecache_size=256m
  mem_limit: 4g
```
