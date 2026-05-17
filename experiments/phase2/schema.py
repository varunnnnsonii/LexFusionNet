"""
Neo4j Schema Manager
=====================
Creates all constraints, indexes, and full-text indexes for the legal knowledge graph.

Implements the schema from the architecture doc PART 5 — INDEXING STRATEGY.

Strategy:
  - Constraints (unique + existence) are created BEFORE bulk load for data integrity.
  - Range/composite/full-text indexes are created AFTER bulk load for performance.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Schema definitions
# ═══════════════════════════════════════════════════════════════════════════

# Uniqueness constraints — created BEFORE ingestion
CONSTRAINTS = [
    ("case_file_id_unique",     "Case",     "file_id",        "CREATE CONSTRAINT case_file_id_unique IF NOT EXISTS FOR (c:Case) REQUIRE c.file_id IS UNIQUE"),
    ("citation_code_unique",    "Citation", "code",           "CREATE CONSTRAINT citation_code_unique IF NOT EXISTS FOR (ci:Citation) REQUIRE ci.code IS UNIQUE"),
    ("statute_canon_unique",    "Statute",  "canonical_name", "CREATE CONSTRAINT statute_canon_unique IF NOT EXISTS FOR (s:Statute) REQUIRE s.canonical_name IS UNIQUE"),
    ("act_name_unique",         "Act",      "name",           "CREATE CONSTRAINT act_name_unique IF NOT EXISTS FOR (a:Act) REQUIRE a.name IS UNIQUE"),
]

# Range/lookup indexes — created AFTER bulk load
POST_LOAD_INDEXES = [
    "CREATE INDEX case_year_idx IF NOT EXISTS FOR (c:Case) ON (c.year)",
    "CREATE INDEX case_citation_count_idx IF NOT EXISTS FOR (c:Case) ON (c.citation_count)",
    "CREATE INDEX case_statute_count_idx IF NOT EXISTS FOR (c:Case) ON (c.statute_count)",
    "CREATE INDEX citation_year_idx IF NOT EXISTS FOR (ci:Citation) ON (ci.year)",
    "CREATE INDEX citation_reporter_idx IF NOT EXISTS FOR (ci:Citation) ON (ci.reporter)",
    "CREATE INDEX statute_category_idx IF NOT EXISTS FOR (s:Statute) ON (s.category)",
    "CREATE INDEX statute_act_name_idx IF NOT EXISTS FOR (s:Statute) ON (s.act_name)",
    "CREATE INDEX act_type_idx IF NOT EXISTS FOR (a:Act) ON (a.act_type)",
    # Composite index for year-scoped authority queries
    "CREATE INDEX case_year_citations_idx IF NOT EXISTS FOR (c:Case) ON (c.year, c.citation_count)",
]

# Full-text indexes (backed by Lucene) — created AFTER bulk load
FULLTEXT_INDEXES = [
    "CREATE FULLTEXT INDEX case_title_ft IF NOT EXISTS FOR (c:Case) ON EACH [c.title]",
    "CREATE FULLTEXT INDEX statute_name_ft IF NOT EXISTS FOR (s:Statute) ON EACH [s.canonical_name]",
    "CREATE FULLTEXT INDEX act_name_ft IF NOT EXISTS FOR (a:Act) ON EACH [a.name]",
]


def create_constraints(client, verbose: bool = True):
    """Create uniqueness constraints BEFORE bulk load."""
    if verbose:
        print("  Creating uniqueness constraints...")
    for name, label, prop, cypher in CONSTRAINTS:
        try:
            client.run_write(cypher)
            if verbose:
                print(f"    ✓ {name} ({label}.{prop})")
        except Exception as e:
            if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                if verbose:
                    print(f"    ○ {name} already exists")
            else:
                logger.error("Failed to create constraint %s: %s", name, e)
                raise


def create_post_load_indexes(client, verbose: bool = True):
    """Create range and composite indexes AFTER bulk load."""
    if verbose:
        print("  Creating post-load indexes...")
    for cypher in POST_LOAD_INDEXES:
        try:
            client.run_write(cypher)
            # Extract index name for logging
            name = cypher.split("INDEX ")[1].split(" IF")[0] if "INDEX" in cypher else "?"
            if verbose:
                print(f"    ✓ {name}")
        except Exception as e:
            if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                name = cypher.split("INDEX ")[1].split(" IF")[0] if "INDEX" in cypher else "?"
                if verbose:
                    print(f"    ○ {name} already exists")
            else:
                logger.error("Failed to create index: %s — %s", cypher, e)
                raise


def create_fulltext_indexes(client, verbose: bool = True):
    """Create full-text search indexes AFTER bulk load."""
    if verbose:
        print("  Creating full-text indexes...")
    for cypher in FULLTEXT_INDEXES:
        try:
            client.run_write(cypher)
            name = cypher.split("INDEX ")[1].split(" IF")[0] if "INDEX" in cypher else "?"
            if verbose:
                print(f"    ✓ {name}")
        except Exception as e:
            if "already exists" in str(e).lower() or "equivalent" in str(e).lower():
                name = cypher.split("INDEX ")[1].split(" IF")[0] if "INDEX" in cypher else "?"
                if verbose:
                    print(f"    ○ {name} already exists")
            else:
                logger.error("Failed to create fulltext index: %s — %s", cypher, e)
                raise


def create_all_schema(client, verbose: bool = True):
    """Create ALL schema elements (constraints + indexes + fulltext)."""
    create_constraints(client, verbose)
    create_post_load_indexes(client, verbose)
    create_fulltext_indexes(client, verbose)


def drop_all_constraints_and_indexes(client, verbose: bool = True):
    """Drop ALL constraints and indexes — for a clean re-ingestion."""
    if verbose:
        print("  Dropping all constraints and indexes...")

    # Get all constraints
    constraints = client.run_query("SHOW CONSTRAINTS")
    for c in constraints:
        name = c.get("name", "")
        if name:
            try:
                client.run_write(f"DROP CONSTRAINT {name} IF EXISTS")
                if verbose:
                    print(f"    ✗ Dropped constraint: {name}")
            except Exception:
                pass

    # Get all indexes
    indexes = client.run_query("SHOW INDEXES")
    for idx in indexes:
        name = idx.get("name", "")
        # Skip internal indexes
        if name and not name.startswith("__"):
            try:
                client.run_write(f"DROP INDEX {name} IF EXISTS")
                if verbose:
                    print(f"    ✗ Dropped index: {name}")
            except Exception:
                pass
