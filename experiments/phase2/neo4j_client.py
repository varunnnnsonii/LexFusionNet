"""
Neo4j Connection Manager
========================
Provides a thread-safe, context-managed Neo4j driver for LexiFusionNet.

Usage:
    from experiments.phase2.neo4j_client import Neo4jClient

    client = Neo4jClient()          # reads from config
    with client.session() as sess:
        sess.run("MATCH (n) RETURN count(n)")
    client.close()

    # or as context manager:
    with Neo4jClient() as client:
        with client.session() as sess:
            ...
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

import yaml

try:
    from neo4j import GraphDatabase, Driver
except ImportError:
    raise ImportError(
        "neo4j driver not installed. Run: pip install neo4j"
    )

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_neo4j_config() -> dict:
    """Load Neo4j connection settings from config.yaml or environment."""
    config_path = _PROJECT_ROOT / "configs" / "config.yaml"
    neo4j_cfg = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            raw = yaml.safe_load(f)
        neo4j_cfg = raw.get("neo4j", {})

    # Environment overrides (useful for Docker / CI)
    return {
        "uri": os.getenv("NEO4J_URI", neo4j_cfg.get("uri", "bolt://localhost:7687")),
        "user": os.getenv("NEO4J_USER", neo4j_cfg.get("user", "neo4j")),
        "password": os.getenv("NEO4J_PASSWORD", neo4j_cfg.get("password", "lexifusionnet")),
        "database": os.getenv("NEO4J_DATABASE", neo4j_cfg.get("database", "neo4j")),
    }


# ---------------------------------------------------------------------------
# Client class
# ---------------------------------------------------------------------------

class Neo4jClient:
    """Thread-safe Neo4j connection manager."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        cfg = _load_neo4j_config()
        self._uri = uri or cfg["uri"]
        self._user = user or cfg["user"]
        self._password = password or cfg["password"]
        self._database = database or cfg["database"]
        self._driver: Optional[Driver] = None

    # -- lifecycle ----------------------------------------------------------

    def connect(self) -> "Neo4jClient":
        """Open the driver connection."""
        if self._driver is not None:
            return self
        logger.info("Connecting to Neo4j at %s (db=%s)", self._uri, self._database)
        self._driver = GraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
        )
        # Verify connectivity
        self._driver.verify_connectivity()
        logger.info("Neo4j connection verified ✓")
        return self

    def close(self):
        """Close the driver."""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed.")

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # -- session helpers ----------------------------------------------------

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self.connect()
        return self._driver

    @contextmanager
    def session(self, **kwargs):
        """Yield a Neo4j session bound to the configured database."""
        sess = self.driver.session(database=self._database, **kwargs)
        try:
            yield sess
        finally:
            sess.close()

    # -- convenience --------------------------------------------------------

    def run_query(self, cypher: str, parameters: Optional[dict] = None) -> list:
        """Run a single Cypher query and return all records as dicts."""
        with self.session() as sess:
            result = sess.run(cypher, parameters or {})
            return [record.data() for record in result]

    def run_write(self, cypher: str, parameters: Optional[dict] = None):
        """Run a single write transaction."""
        with self.session() as sess:
            sess.execute_write(lambda tx: tx.run(cypher, parameters or {}))

    def clear_database(self):
        """Delete ALL nodes and relationships — USE WITH CAUTION."""
        logger.warning("Clearing entire Neo4j database!")
        with self.session() as sess:
            sess.execute_write(
                lambda tx: tx.run("MATCH (n) DETACH DELETE n")
            )
        logger.info("Database cleared.")

    def count_nodes(self, label: Optional[str] = None) -> int:
        """Count nodes, optionally filtered by label."""
        if label:
            q = f"MATCH (n:{label}) RETURN count(n) AS cnt"
        else:
            q = "MATCH (n) RETURN count(n) AS cnt"
        result = self.run_query(q)
        return result[0]["cnt"] if result else 0

    def count_relationships(self, rel_type: Optional[str] = None) -> int:
        """Count relationships, optionally filtered by type."""
        if rel_type:
            q = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt"
        else:
            q = "MATCH ()-[r]->() RETURN count(r) AS cnt"
        result = self.run_query(q)
        return result[0]["cnt"] if result else 0
