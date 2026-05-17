"""
Neo4j Query Layer
==================
Implements the 6 query patterns from the architecture doc PART 6.

1. Precedent Search
2. Citation Chain (shortest path)
3. Authority Ranking
4. Statute Co-occurrence
5. Legal Issue Clustering (related cases)
6. Temporal Evolution
"""

import logging
from typing import Optional

from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphQueryEngine:
    """Query builder for the legal knowledge graph."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    # ── 1. Precedent Search ───────────────────────────────────────────────

    def find_precedents(self, file_id: str, limit: int = 20) -> list[dict]:
        """
        Find cases cited by the same cases that cite the query case.
        Pattern: Case A → CITES → Citation X ← HAS_CITATION ← Case B
        """
        return self.client.run_query("""
            MATCH (query:Case {file_id: $fid})<-[:MENTIONS_CASE]-(citing:Case)-[:MENTIONS_CASE]->(related:Case)
            WHERE related.file_id <> $fid
            WITH related, count(citing) AS shared_citers
            RETURN related.file_id AS file_id, related.year AS year,
                   related.title AS title, shared_citers
            ORDER BY shared_citers DESC
            LIMIT $limit
        """, {"fid": file_id, "limit": limit})

    # ── 2. Citation Chain ─────────────────────────────────────────────────

    def find_citation_chain(self, source_id: str, target_id: str, max_depth: int = 6) -> list[dict]:
        """
        Find the shortest path of authority from source to target case.
        """
        return self.client.run_query("""
            MATCH path = shortestPath(
                (a:Case {file_id: $src})-[:MENTIONS_CASE*1..6]->(b:Case {file_id: $tgt})
            )
            RETURN [n IN nodes(path) | n.file_id] AS chain,
                   length(path) AS hops
        """, {"src": source_id, "tgt": target_id})

    # ── 3. Authority Ranking ──────────────────────────────────────────────

    def rank_authority_by_statute(self, statute_canonical: str, limit: int = 20) -> list[dict]:
        """
        Most authoritative cases citing a given statute, ranked by in-degree.
        """
        return self.client.run_query("""
            MATCH (c:Case)-[:REFERENCES]->(s:Statute {canonical_name: $statute})
            OPTIONAL MATCH (c)<-[:MENTIONS_CASE]-(other)
            WITH c, count(other) AS in_degree
            RETURN c.file_id AS file_id, c.year AS year, c.title AS title, in_degree
            ORDER BY in_degree DESC
            LIMIT $limit
        """, {"statute": statute_canonical, "limit": limit})

    def rank_authority_global(self, year_min: int = 0, year_max: int = 9999, limit: int = 20) -> list[dict]:
        """Top cases by global in-degree within a year range."""
        return self.client.run_query("""
            MATCH (c:Case)<-[:MENTIONS_CASE]-(other)
            WHERE c.year >= $ymin AND c.year <= $ymax
            WITH c, count(other) AS in_degree
            RETURN c.file_id AS file_id, c.year AS year, c.title AS title, in_degree
            ORDER BY in_degree DESC
            LIMIT $limit
        """, {"ymin": year_min, "ymax": year_max, "limit": limit})

    # ── 4. Statute Co-occurrence ──────────────────────────────────────────

    def statute_cooccurrence(self, statute_canonical: str, min_count: int = 5, limit: int = 30) -> list[dict]:
        """
        Find statutes commonly cited alongside the query statute.
        """
        return self.client.run_query("""
            MATCH (s1:Statute {canonical_name: $statute})<-[:REFERENCES]-(c:Case)-[:REFERENCES]->(s2:Statute)
            WHERE s2.canonical_name <> $statute
            WITH s2, count(c) AS cooccurrence
            WHERE cooccurrence >= $min_count
            RETURN s2.canonical_name AS statute, s2.act_name AS act, cooccurrence
            ORDER BY cooccurrence DESC
            LIMIT $limit
        """, {"statute": statute_canonical, "min_count": min_count, "limit": limit})

    # ── 5. Related Cases (Legal Issue Clustering) ─────────────────────────

    def find_related_cases(self, file_id: str, min_shared: int = 3, limit: int = 20) -> list[dict]:
        """
        Find cases sharing 3+ statute references with the query case.
        """
        return self.client.run_query("""
            MATCH (query:Case {file_id: $fid})-[:REFERENCES]->(s:Statute)<-[:REFERENCES]-(other:Case)
            WHERE other.file_id <> $fid
            WITH other, collect(s.canonical_name) AS shared_statutes, count(s) AS shared_count
            WHERE shared_count >= $min_shared
            RETURN other.file_id AS file_id, other.year AS year, other.title AS title,
                   shared_count, shared_statutes[..5] AS sample_statutes
            ORDER BY shared_count DESC
            LIMIT $limit
        """, {"fid": file_id, "min_shared": min_shared, "limit": limit})

    # ── 6. Temporal Evolution ─────────────────────────────────────────────

    def temporal_evolution(self, statute_canonical: str, limit: int = 50) -> list[dict]:
        """
        How has interpretation of a statute evolved over time?
        Returns cases citing it ordered by year, with their in-degree.
        """
        return self.client.run_query("""
            MATCH (c:Case)-[:REFERENCES]->(s:Statute {canonical_name: $statute})
            OPTIONAL MATCH (c)<-[:MENTIONS_CASE]-(other)
            WITH c, count(other) AS in_degree
            RETURN c.file_id AS file_id, c.year AS year, c.title AS title, in_degree
            ORDER BY c.year ASC
            LIMIT $limit
        """, {"statute": statute_canonical, "limit": limit})

    # ── Utility queries ───────────────────────────────────────────────────

    def case_profile(self, file_id: str) -> dict:
        """Get a full profile of a case: citations, statutes, neighbors."""
        basic = self.client.run_query("""
            MATCH (c:Case {file_id: $fid})
            RETURN c.file_id AS file_id, c.year AS year, c.title AS title,
                   c.citation_count AS citation_count, c.statute_count AS statute_count
        """, {"fid": file_id})

        statutes = self.client.run_query("""
            MATCH (c:Case {file_id: $fid})-[:REFERENCES]->(s:Statute)
            RETURN s.canonical_name AS statute, s.act_name AS act
            ORDER BY s.act_name, s.canonical_name
        """, {"fid": file_id})

        cited_by = self.client.run_query("""
            MATCH (c:Case {file_id: $fid})<-[:MENTIONS_CASE]-(other:Case)
            RETURN other.file_id AS file_id, other.year AS year
            ORDER BY other.year DESC
            LIMIT 20
        """, {"fid": file_id})

        cites = self.client.run_query("""
            MATCH (c:Case {file_id: $fid})-[:MENTIONS_CASE]->(other:Case)
            RETURN other.file_id AS file_id, other.year AS year
            ORDER BY other.year DESC
            LIMIT 20
        """, {"fid": file_id})

        return {
            "case": basic[0] if basic else {},
            "statutes": statutes,
            "cited_by": cited_by,
            "cites": cites,
        }

    def search_cases_fulltext(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search on case titles."""
        return self.client.run_query("""
            CALL db.index.fulltext.queryNodes('case_title_ft', $q)
            YIELD node, score
            RETURN node.file_id AS file_id, node.year AS year,
                   node.title AS title, score
            LIMIT $limit
        """, {"q": query, "limit": limit})

    def search_statutes_fulltext(self, query: str, limit: int = 10) -> list[dict]:
        """Full-text search on statute canonical names."""
        return self.client.run_query("""
            CALL db.index.fulltext.queryNodes('statute_name_ft', $q)
            YIELD node, score
            RETURN node.canonical_name AS statute, node.act_name AS act,
                   node.category AS category, score
            LIMIT $limit
        """, {"q": query, "limit": limit})

    def graph_stats(self) -> dict:
        """Get comprehensive graph statistics."""
        nodes = {}
        for label in ["Case", "Citation", "Statute", "Act"]:
            nodes[label] = self.client.count_nodes(label)
        edges = {}
        for rel in ["HAS_CITATION", "CITES", "REFERENCES", "PART_OF", "MENTIONS_CASE"]:
            edges[rel] = self.client.count_relationships(rel)
        return {"nodes": nodes, "edges": edges,
                "total_nodes": sum(nodes.values()),
                "total_edges": sum(edges.values())}
