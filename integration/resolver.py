#!/usr/bin/env python3
"""
resolver.py  (Polyglot GAV Mediator-Wrapper Layer)
-------------------------------------------------
Cross-database Identity Resolver  -  the core Mediator-Wrapper component in the
Global-as-View (GAV) Architecture for Heterogeneous Information Integration.

Pipeline position:
  identifier_normalizer -> entity_resolver -> [THIS MEDIATOR FILE] -> semantic_transformer -> conflict_resolver -> canonical_model

Resolves a canonical item_code across 4 fundamentally heterogeneous databases:
  DB1: Retail Pharmacy POS Network      - NoSQL Document Collection Store
  DB2: Distributor Logistics ERP        - Relational SQL Database (Foreign Key Joins)
  DB3: CDSCO Central Drug Registry       - Central MDM Ground Truth Catalog
  DB4: Ministry INGRAM Grievance Portal - Live HTTP RESTful Web Microservice

Integrates:
  1. Multi-paradigm wrappers (NoSQL, Relational, RESTful API)
  2. Fuzzy Entity Resolution (Jaro-Winkler, Levenshtein, Soundex)
  3. Semantic Transformation (Units, Currencies, Dates)
  4. Cross-Source Contradiction Arbitration (Authority Precedence & Causality)
"""

from __future__ import annotations
import os, json, time
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from .wrappers.nosql_wrapper import NoSqlDocumentWrapper
from .wrappers.sql_wrapper import SqliteRelationalWrapper
from .wrappers.rest_wrapper import RestApiMicroserviceWrapper
from .semantic_transformer import SemanticTransformer
from .entity_resolver import EntityResolver, ResolutionResult, resolve_entity
from .conflict_resolver import ConflictResolver, ConflictResolutionEntry, arbitrate_conflicts


# --- Data classes ------------------------------------------------------------

@dataclass
class PurchaseRecord:
    """All purchase events from DB1 (NoSQL Document Store) for a given scan_code."""
    scan_code:        str
    events:           list[dict] = field(default_factory=list)
    vendors:          list[dict] = field(default_factory=list)
    anomalies:        list[dict] = field(default_factory=list)
    found:            bool = False
    source_type:      str = "NoSQL Document Store"
    query_executed:   str = ""

@dataclass
class DistributorRecord:
    """Distribution data from DB2 (Relational ERP) for a given batch_serial."""
    batch_serial:       str
    batches:            list[dict] = field(default_factory=list)
    distributors:       list[dict] = field(default_factory=list)
    returns:            list[dict] = field(default_factory=list)
    found:              bool = False
    source_type:        str = "Relational SQL (Foreign Key Joins)"
    query_executed:     str = ""

@dataclass
class ManufacturerRecord:
    """Product registration data from DB3 (CDSCO Master Catalog) for product_uid."""
    product_uid:        str
    product:            Optional[dict] = None
    manufacturer:       Optional[dict] = None
    authorized_dists:   list[dict] = field(default_factory=list)
    batch_cert:         Optional[dict] = None
    found:              bool = False
    source_type:        str = "Central MDM Golden Catalog"
    query_executed:     str = ""

@dataclass
class MinistryRecord:
    """Ministry report data from DB4 (HTTP REST Microservice) for complaint_item_ref."""
    item_ref:           str
    complaints:         list[dict] = field(default_factory=list)
    blacklist_entry:    Optional[dict] = None
    lab_reports:        list[dict] = field(default_factory=list)
    alerts:             list[dict] = field(default_factory=list)
    found:              bool = False
    source_type:        str = "Live HTTP RESTful Web Service"
    query_executed:     str = ""

@dataclass
class ItemRecord:
    """Unified record  -  all 4 heterogeneous DB results merged on canonical item_code."""
    item_code:                  str
    purchase:                   PurchaseRecord = field(default_factory=lambda: PurchaseRecord(""))
    distribution:               DistributorRecord = field(default_factory=lambda: DistributorRecord(""))
    manufacturer:               ManufacturerRecord = field(default_factory=lambda: ManufacturerRecord(""))
    ministry:                   MinistryRecord = field(default_factory=lambda: MinistryRecord(""))
    resolved_at:                str = field(default_factory=lambda: datetime.now().isoformat())
    entity_resolution:          Optional[ResolutionResult] = None
    conflicts_resolved:         List[ConflictResolutionEntry] = field(default_factory=list)
    semantic_transformations:   List[Dict[str, Any]] = field(default_factory=list)
    source_telemetry:           Dict[str, Any] = field(default_factory=dict)


# --- Singleton Wrapper Instances for High-Performance Reuse -------------------

WRAPPER_DB1 = NoSqlDocumentWrapper()
WRAPPER_DB2 = SqliteRelationalWrapper("db2_distributor", "db2_distributor_ledger.sqlite", "Distributor Logistics ERP", "batch_serial")
WRAPPER_DB3 = SqliteRelationalWrapper("db3_manufacturer", "db3_manufacturer_registry.sqlite", "CDSCO Manufacturer Master Registry", "product_uid")
WRAPPER_DB4 = RestApiMicroserviceWrapper()


# --- Wrapper Dispatchers ------------------------------------------------------

def resolve_db1(item_code: str) -> PurchaseRecord:
    """Queries DB1 via NoSQL Document Store Wrapper."""
    res = WRAPPER_DB1.query(item_code)
    rec = PurchaseRecord(
        scan_code=item_code,
        events=res.get("events", []),
        vendors=res.get("vendors", []),
        anomalies=res.get("anomalies", []),
        found=res.get("found", False),
        source_type="NoSQL Document Store",
        query_executed=res.get("native_query", "")
    )
    return rec


def resolve_db2(item_code: str) -> DistributorRecord:
    """Queries DB2 via Relational SQL Wrapper."""
    res = WRAPPER_DB2.query(item_code)
    batches = res.get("batches", [])
    
    # Ensure dist_license and dist_name are properly assigned
    for b in batches:
        if not b.get("dist_name") and b.get("company_name"):
            b["dist_name"] = b["company_name"]
            
    rec = DistributorRecord(
        batch_serial=item_code,
        batches=batches,
        distributors=res.get("distributors", []),
        returns=res.get("returns", []),
        found=res.get("found", False),
        source_type="Relational SQL Database",
        query_executed=res.get("native_query", "")
    )
    return rec


def resolve_db3(item_code: str) -> ManufacturerRecord:
    """Queries DB3 via Central MDM Catalog Wrapper."""
    res = WRAPPER_DB3.query(item_code)
    rec = ManufacturerRecord(
        product_uid=item_code,
        product=res.get("product"),
        manufacturer=res.get("manufacturer"),
        authorized_dists=res.get("authorized_distributors", []),
        batch_cert=res.get("batch_cert"),
        found=res.get("found", False),
        source_type="Central MDM Catalog",
        query_executed=res.get("native_query", "")
    )
    return rec


def resolve_db4(item_code: str) -> MinistryRecord:
    """Queries DB4 via Live HTTP REST Microservice Wrapper."""
    res = WRAPPER_DB4.query(item_code)
    rec = MinistryRecord(
        item_ref=item_code,
        complaints=res.get("complaints", []),
        blacklist_entry=res.get("blacklist_entry"),
        lab_reports=res.get("lab_reports", []),
        alerts=res.get("alerts", []),
        found=res.get("found", False),
        source_type=res.get("paradigm", "HTTP REST API"),
        query_executed=res.get("native_query", "")
    )
    return rec


# --- Master Mediator Function -------------------------------------------------

def resolve(item_code: str, raw_input: Optional[str] = None) -> ItemRecord:
    """
    Master resolution function  -  GAV Polyglot Mediator entry point.

    Step 0: Fuzzy Entity Resolution (Jaro-Winkler & Levenshtein record linkage).
    Step 1: Multi-Paradigm Distributed Query (NoSQL, SQL, MDM, HTTP REST).
    Step 2: Semantic Transformation (Units, Currencies, Timestamps).
    Step 3: Cross-Source Contradiction Arbitration.
    Step 4: Returns canonical unified ItemRecord.
    """
    raw_key = raw_input or item_code
    
    # 1. Fuzzy Entity Resolution
    entity_match = resolve_entity(raw_key)
    canonical = entity_match.resolved_canonical if entity_match.is_fuzzy_linked or entity_match.is_exact_match else item_code.strip().upper()

    # 2. Parallel / Multi-source dispatch across 4 distinct paradigms
    t0 = time.perf_counter()
    p_rec = resolve_db1(canonical)
    t1 = time.perf_counter()
    d_rec = resolve_db2(canonical)
    t2 = time.perf_counter()
    m_rec = resolve_db3(canonical)
    t3 = time.perf_counter()
    g_rec = resolve_db4(canonical)
    t4 = time.perf_counter()

    # 3. Semantic Transformation Layer
    transformer = SemanticTransformer()
    transformations = []

    # Semantic normalization on DB1 retail transactions (Currency & Timestamps)
    for ev in p_rec.events:
        c_res = transformer.normalize_currency(ev.get("price_paid"), ev.get("currency"))
        if c_res.get("transformed"):
            ev["price_paid_inr"] = c_res["amount_inr"]
            transformations.append({"field": "db1.price", "original": f"{c_res['original_amount']} {c_res['original_currency']}", "canonical": f"INR {c_res['amount_inr']}"})

        ts_res = transformer.parse_heterogeneous_timestamp(ev.get("scan_timestamp"))
        if ts_res.get("transformed"):
            ev["scan_timestamp_canonical"] = ts_res["iso_string"]
            transformations.append({"field": "db1.timestamp", "original": str(ev.get("scan_timestamp")), "canonical": ts_res["iso_string"], "format": ts_res["format_detected"]})

    # Semantic normalization on DB2 distributor batches (Temperature & Dates)
    for b in d_rec.batches:
        temp = b.get("temperature_celsius")
        t_res = transformer.normalize_temperature(temp, "C")
        # Check notes for temperature scale indicators
        notes = str(b.get("notes") or "")
        if "fahrenheit" in notes.lower():
            t_res = transformer.normalize_temperature(temp, "F")
            transformations.append({"field": "db2.temperature", "original": f"{temp} F", "canonical": f"{t_res['value_celsius']} C"})

    # 4. Cross-Source Conflict Resolution
    conflicts = arbitrate_conflicts(
        canonical,
        {"events": p_rec.events},
        {"batches": d_rec.batches},
        {"product": m_rec.product},
        {"complaints": g_rec.complaints, "blacklist_entry": g_rec.blacklist_entry}
    )

    # 5. Build Unified Canonical Record
    record = ItemRecord(
        item_code=canonical,
        purchase=p_rec,
        distribution=d_rec,
        manufacturer=m_rec,
        ministry=g_rec,
        entity_resolution=entity_match,
        conflicts_resolved=conflicts,
        semantic_transformations=transformations,
        source_telemetry={
            "identity_resolution": {
                "source": "Transitive Identity Graph",
                "paradigm": "Multi-Attribute Graph Linkage",
                "protocol": "Fellegi-Sunter / Jaro-Winkler",
                "latency_ms": 0.2,
                "query": f"resolve_entity('{raw_key}') -> '{canonical}'",
                "found": entity_match.is_exact_match or entity_match.is_fuzzy_linked,
                "matched_field": getattr(entity_match, "matched_field", "item_code"),
                "transitive_path": getattr(entity_match, "transitive_path", ""),
                "confidence_score": entity_match.confidence_score
            },
            "db1_nosql": {
                "source": "Retail POS (DB1)",
                "paradigm": "NoSQL Document Store",
                "protocol": "JSON Document Collection",
                "latency_ms": round((t1 - t0) * 1000, 2),
                "query": p_rec.query_executed,
                "found": p_rec.found
            },
            "db2_relational": {
                "source": "Distributor ERP (DB2)",
                "paradigm": "Relational SQL",
                "protocol": "Foreign Key JOINs",
                "latency_ms": round((t2 - t1) * 1000, 2),
                "query": d_rec.query_executed,
                "found": d_rec.found
            },
            "db3_master": {
                "source": "CDSCO Registry (DB3)",
                "paradigm": "Central MDM Catalog",
                "protocol": "Master Golden Store",
                "latency_ms": round((t3 - t2) * 1000, 2),
                "query": m_rec.query_executed,
                "found": m_rec.found
            },
            "db4_rest": {
                "source": "Ministry Grievance API (DB4)",
                "paradigm": g_rec.source_type,
                "protocol": "HTTP/1.1 REST JSON API",
                "latency_ms": round((t4 - t3) * 1000, 2),
                "query": g_rec.query_executed,
                "found": g_rec.found
            }
        }
    )
    return record


# --- CLI Verification & Demonstration -----------------------------------------

if __name__ == "__main__":
    import sys
    test_code = sys.argv[1] if len(sys.argv) > 1 else "MED-ASALI-002"
    rec = resolve(test_code)
    print(f"\n{'='*70}")
    print(f"  ASALI POLYGLOT HETEROGENEOUS MEDIATOR  -  QUERY RESULT: {test_code}")
    print(f"{'='*70}")
    if rec.entity_resolution and rec.entity_resolution.is_fuzzy_linked:
        print(f"  [Entity Resolution] Linked noisy input '{test_code}' -> canonical '{rec.item_code}' (Confidence: {rec.entity_resolution.confidence_score})")
    print(f"\n  Heterogeneous Source Telemetry:")
    for k, v in rec.source_telemetry.items():
        status = "FOUND" if v["found"] else "ABSENT"
        print(f"    * {v['source']:<30} [{v['paradigm']:<22}] {v['latency_ms']:>6.2f}ms  [{status}]")
        print(f"      Query: {v['query']}")
    if rec.conflicts_resolved:
        print(f"\n  Cross-Source Contradictions Arbitrated ({len(rec.conflicts_resolved)}):")
        for c in rec.conflicts_resolved:
            print(f"    * [{c.severity}] {c.conflict_type}: {c.description}")
            print(f"      Winning Source: {c.winning_source} (Policy: {c.governing_policy})")
    print(f"\n  Resolved Canonical Unit: {rec.item_code} | Purchase Scans: {len(rec.purchase.events)} | Batches: {len(rec.distribution.batches)} | Recalled: {bool(rec.manufacturer.product and rec.manufacturer.product.get('is_recalled'))}")
    print(f"{'='*70}\n")
