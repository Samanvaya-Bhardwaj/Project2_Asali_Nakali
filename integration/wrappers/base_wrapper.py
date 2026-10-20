#!/usr/bin/env python3
"""
base_wrapper.py
---------------
Abstract Base Class for Data Source Wrappers in the GAV Mediator-Wrapper Architecture.

In Information Integration theory (Wiederhold, 1992; Garcia-Molina et al., 1997),
a Wrapper maps a specific heterogeneous data source into the mediated canonical model,
hiding syntactic, protocol, and query differences from the Mediator.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceMetadata:
    """Provenance and system telemetry for a heterogeneous data source."""
    source_id: str
    source_name: str
    source_type: str  # "NoSQL Document Store", "Relational SQL", "REST API", "MDM Catalog"
    paradigm: str     # "Document", "Relational", "Web Service", "Catalog"
    protocol: str     # "JSON File / MongoDB Query", "SQLite / SQL", "HTTP REST / JSON", etc.
    native_key: str   # "scan_code", "batch_serial", "product_uid", "complaint_item_ref"
    status: str = "ONLINE"
    latency_ms: float = 0.0


class BaseWrapper(ABC):
    """Abstract base class for all heterogeneous wrappers."""

    def __init__(self, source_id: str):
        self.source_id = source_id

    @abstractmethod
    def get_metadata(self) -> SourceMetadata:
        """Returns source identity, paradigm, protocol, and connection health."""
        pass

    @abstractmethod
    def query(self, canonical_key: str, native_filter: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes native query against this heterogeneous source using its local dialect.
        Returns a standardized wrapper result dict with local provenance.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Checks connectivity and returns True if healthy."""
        pass
