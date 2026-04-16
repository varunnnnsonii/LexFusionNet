"""
Configuration loader for LexiFusionNet.

Loads config.yaml and provides typed access via dataclasses.
All paths are resolved relative to the project root.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains configs/)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "configs" / "config.yaml").exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        "Could not find project root (no configs/config.yaml found in parent directories)"
    )


PROJECT_ROOT = _find_project_root()


@dataclass
class PathsConfig:
    raw_data: Path
    parsed_data: Path
    chunks_data: Path
    metadata_db: Path
    bm25_index: Path
    citation_graph: Path
    citation_graph_pkl: Path
    audit_report: Path
    eval_results: Path
    models: Path


@dataclass
class ParsingConfig:
    min_body_length: int
    min_file_size: int
    page_marker_pattern: str
    header_scan_lines: int


@dataclass
class ChunkingConfig:
    chunk_size: int
    chunk_overlap: int
    max_chunks_per_case: int
    tokenizer: str


@dataclass
class EmbeddingConfig:
    model_name: str
    dimension: int
    batch_size: int
    device: str
    normalize: bool


@dataclass
class RerankerConfig:
    model_name: str
    top_k_candidates: int
    top_k_final: int


@dataclass
class RetrievalConfig:
    bm25_top_k: int
    dense_top_k: int
    rrf_k: int
    hybrid_top_k: int


@dataclass
class QdrantConfig:
    host: str
    port: int
    collection_name: str
    hnsw_m: int
    hnsw_ef_construct: int


@dataclass
class GraphConfig:
    node2vec_dimensions: int
    node2vec_walk_length: int
    node2vec_num_walks: int
    node2vec_p: float
    node2vec_q: float


@dataclass
class FusionConfig:
    alpha: float
    beta: float
    gamma: float
    delta: float


@dataclass
class AuditConfig:
    sample_size: int


@dataclass
class AppConfig:
    """Top-level application configuration."""

    paths: PathsConfig
    parsing: ParsingConfig
    chunking: ChunkingConfig
    embedding: EmbeddingConfig
    reranker: RerankerConfig
    retrieval: RetrievalConfig
    qdrant: QdrantConfig
    graph: GraphConfig
    fusion: FusionConfig
    audit: AuditConfig


def _resolve_paths(paths_dict: dict) -> dict:
    """Resolve all path values relative to PROJECT_ROOT."""
    return {k: PROJECT_ROOT / v for k, v in paths_dict.items()}


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses default location.

    Returns:
        Fully resolved AppConfig instance.
    """
    if config_path is None:
        config_path = PROJECT_ROOT / "configs" / "config.yaml"
    else:
        config_path = Path(config_path)

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    # Resolve paths relative to project root
    resolved_paths = _resolve_paths(raw["paths"])

    return AppConfig(
        paths=PathsConfig(**resolved_paths),
        parsing=ParsingConfig(**raw["parsing"]),
        chunking=ChunkingConfig(**raw["chunking"]),
        embedding=EmbeddingConfig(**raw["embedding"]),
        reranker=RerankerConfig(**raw["reranker"]),
        retrieval=RetrievalConfig(**raw["retrieval"]),
        qdrant=QdrantConfig(**raw["qdrant"]),
        graph=GraphConfig(**raw["graph"]),
        fusion=FusionConfig(**raw["fusion"]),
        audit=AuditConfig(**raw["audit"]),
    )


# Module-level singleton for convenience
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or create the singleton config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
