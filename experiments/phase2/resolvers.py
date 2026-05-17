"""
Citation Resolution Engine
===========================
Builds the self_citations → file_id reverse lookup index and resolves
cited_cases to create MENTIONS_CASE edges.

Implements the architecture doc PART 3 — CITATION RESOLUTION STRATEGY.
"""

import logging
from collections import defaultdict
from typing import Optional

from .normalizer import normalize_citation, extract_citation_year

logger = logging.getLogger(__name__)


class CitationResolver:
    """
    Builds and queries a reverse lookup index mapping normalized citation
    codes to file_ids.

    Usage:
        resolver = CitationResolver()
        resolver.build_index(records)
        file_id = resolver.resolve("2006 10 SCC 261")
    """

    def __init__(self):
        # citation_code → list[file_id]  (may have collisions)
        self._code_to_file_ids: dict[str, list[str]] = defaultdict(list)
        # citation_code → file_id  (resolved, unique mapping)
        self._resolved: dict[str, str] = {}
        # file_id → list[citation_code]
        self._file_id_to_codes: dict[str, list[str]] = defaultdict(list)
        # Collision log
        self._collisions: list[dict] = []
        # Stats
        self._total_self_cites = 0
        self._total_collisions = 0

    def build_index(self, records: list[dict], verbose: bool = True):
        """
        Build the reverse lookup index from all records.

        For each record, map each self_citations entry → file_id.
        Handle collisions per architecture doc §3.2.
        """
        if verbose:
            print("  Building citation reverse lookup index...")

        for rec in records:
            file_id = rec.get("file_id", "")
            year_str = rec.get("year", "")
            try:
                year = int(year_str)
            except (ValueError, TypeError):
                year = None

            for raw_cite in rec.get("self_citations", []):
                code = normalize_citation(raw_cite)
                if not code:
                    continue
                self._total_self_cites += 1
                self._code_to_file_ids[code].append(file_id)
                self._file_id_to_codes[file_id].append(code)

        # Resolve collisions
        for code, file_ids in self._code_to_file_ids.items():
            unique_ids = list(set(file_ids))
            if len(unique_ids) == 1:
                self._resolved[code] = unique_ids[0]
            else:
                # Collision: prefer the one whose year matches the citation year
                cite_year = extract_citation_year(code)
                self._total_collisions += 1

                best = None
                for fid in unique_ids:
                    # Find the record year for this file_id
                    rec_year = self._get_record_year(fid, records)
                    if rec_year and cite_year and rec_year == cite_year:
                        best = fid
                        break

                if best is None:
                    best = unique_ids[0]  # Fallback: take first

                self._resolved[code] = best
                self._collisions.append({
                    "code": code,
                    "file_ids": unique_ids,
                    "resolved_to": best,
                    "cite_year": cite_year,
                })

        if verbose:
            print(f"    Total self-citation entries:  {self._total_self_cites}")
            print(f"    Unique citation codes:        {len(self._resolved)}")
            print(f"    Collisions (multi-mapping):   {self._total_collisions}")
            print(f"    File IDs with self-cites:     {len(self._file_id_to_codes)}")

    @staticmethod
    def _get_record_year(file_id: str, records: list[dict]) -> Optional[int]:
        """Get the year for a file_id from records. Linear scan is OK since we only
        call this on collision cases (~rare)."""
        for rec in records:
            if rec.get("file_id") == file_id:
                try:
                    return int(rec.get("year", ""))
                except (ValueError, TypeError):
                    return None
        return None

    def resolve(self, citation_code: str) -> Optional[str]:
        """Look up a citation code → file_id. Returns None if unresolved."""
        normalized = normalize_citation(citation_code)
        return self._resolved.get(normalized)

    def get_file_citations(self, file_id: str) -> list[str]:
        """Get all citation codes for a file_id."""
        return self._file_id_to_codes.get(file_id, [])

    @property
    def index_size(self) -> int:
        return len(self._resolved)

    @property
    def collisions(self) -> list[dict]:
        return self._collisions

    def compute_resolution_stats(self, records: list[dict]) -> dict:
        """
        Compute how many cited_cases entries can be resolved to file_ids.

        Returns stats dict.
        """
        total_body_cites = 0
        resolved_count = 0
        unresolved_count = 0

        for rec in records:
            for raw_cite in rec.get("cited_cases", []):
                code = normalize_citation(raw_cite)
                total_body_cites += 1
                if self.resolve(code):
                    resolved_count += 1
                else:
                    unresolved_count += 1

        resolution_rate = (
            resolved_count / total_body_cites * 100
            if total_body_cites > 0
            else 0.0
        )

        return {
            "total_body_citations": total_body_cites,
            "resolved": resolved_count,
            "unresolved": unresolved_count,
            "resolution_rate_pct": round(resolution_rate, 2),
            "index_size": self.index_size,
            "collisions": self._total_collisions,
        }
