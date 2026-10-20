#!/usr/bin/env python3
"""
mediator.py  (Global-as-View Federated Query Mediator & IIA Innovator)
----------------------------------------------------------------------
Academic Innovation Component: Information Integration & Architecture (IIA)

This module implements an explicit Global-as-View (GAV) Mediator that:
  1. Accepts a Global Unified Query over canonical schema:
     Q_global(item_code) -> CanonicalItem(id, product, batch, cold_chain, scans, alerts)
  2. Unfolds the global query into 4 heterogeneous sub-queries across distinct paradigms:
     - DB1 (NoSQL Document Store): Filter predicate over nested JSON collection
     - DB2 (Relational SQL): Multi-table JOIN with Foreign Key constraints
     - DB3 (Central MDM Relational Catalog): Golden Record extraction
     - DB4 (HTTP REST Microservice): Web resource consumption with Bearer auth
  3. Executes sub-queries via Modular Wrappers.
  4. Solves 5 Core Information Integration Challenges:
     - Challenge 1: System & Syntactic Heterogeneity
     - Challenge 2: Structural & Schema Hierarchy Heterogeneity
     - Challenge 3: Semantic & Unit Heterogeneity
     - Challenge 4: Fuzzy Entity Resolution & Record Linkage
     - Challenge 5: Cross-Source Conflict Arbitration
  5. Provides full query execution trace and provenance for auditability.
"""

from __future__ import annotations
import sys
import os
import time
import json
import argparse
from typing import Dict, Any, List, Optional
from dataclasses import asdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from integration.resolver import (
    resolve,
    ItemRecord,
    WRAPPER_DB1,
    WRAPPER_DB2,
    WRAPPER_DB3,
    WRAPPER_DB4
)
from integration.entity_resolver import resolve_entity, EntityResolver
from integration.semantic_transformer import SemanticTransformer
from integration.conflict_resolver import arbitrate_conflicts
from integration.distributed_config import get_topology_config
from integration.schema_adapter import SchemaEvolutionAdapter


class GavQueryMediator:
    """
    Global-as-View (GAV) Query Mediator for Polyglot Medicine Traceability.
    """

    def __init__(self):
        self.semantic_engine = SemanticTransformer()
        self.entity_engine = EntityResolver()

    def get_source_manifest(self) -> Dict[str, Any]:
        """Returns the federated source registry and paradigm descriptions."""
        return {
            "sources": [
                {
                    "source_id": "db1_retail_pos",
                    "paradigm": "NoSQL Document Store (JSON Documents)",
                    "role": "High-velocity retail pharmacy scan events and POS telemetry",
                    "location": "data/nosql_store/db1_retail_pos.json",
                    "query_language": "JSON Document Filter & Projection (find)",
                    "status": "ONLINE" if WRAPPER_DB1.health_check() else "OFFLINE"
                },
                {
                    "source_id": "db2_distributor_ledger",
                    "paradigm": "Relational SQL (Tabular RDBMS)",
                    "role": "Logistics ERP, warehouse dispatch batches, vehicle transport",
                    "location": "databases/db2_distributor_ledger.sqlite",
                    "query_language": "ANSI SQL (SELECT ... JOIN with FK constraints)",
                    "status": "ONLINE" if WRAPPER_DB2.health_check() else "OFFLINE"
                },
                {
                    "source_id": "db3_manufacturer_registry",
                    "paradigm": "Central MDM Relational Catalog",
                    "role": "CDSCO master catalog, batch release certs, manufacturer licenses",
                    "location": "databases/db3_manufacturer_registry.sqlite",
                    "query_language": "ANSI SQL (SELECT ... JOIN on product_uid)",
                    "status": "ONLINE" if WRAPPER_DB3.health_check() else "OFFLINE"
                },
                {
                    "source_id": "db4_ministry_service",
                    "paradigm": "HTTP RESTful Web Microservice",
                    "role": "Live government complaints, blacklisted vendors, recalls, alerts",
                    "location": "http://127.0.0.1:8001/api/v1 (Microservice)",
                    "query_language": "RESTful HTTP GET /api/v1/dossier with Bearer Auth",
                    "status": "ONLINE" if WRAPPER_DB4.health_check() else "FALLBACK_PROXY"
                }
            ],
            "architecture": "Global-as-View (GAV) Mediator-Wrapper",
            "challenges_addressed": [
                "System & Syntactic Heterogeneity",
                "Structural & Nested Document Heterogeneity",
                "Semantic & Unit Representation Heterogeneity",
                "Fuzzy Entity Resolution & OCR Typo Linkage",
                "Cross-Source Contradiction & Conflict Arbitration"
            ]
        }

    def explain_query_unfolding(self, query_code: str) -> Dict[str, Any]:
        """
        Explains how a Global Query Q(item_code) unfolds into physical sub-queries.
        """
        # Step 0: Entity Resolution mapping
        entity_res = self.entity_engine.resolve_item_code(query_code)
        canonical = entity_res.resolved_canonical

        unfolded_plans = {
            "global_query": f"SELECT * FROM UnifiedMedicineDossier WHERE item_code = '{query_code}'",
            "entity_linkage": {
                "raw_input": query_code,
                "canonical_target": canonical,
                "confidence_score": entity_res.confidence_score,
                "algorithm": entity_res.match_explanation,
                "is_fuzzy_match": entity_res.is_fuzzy_linked
            },
            "subqueries": [
                {
                    "target_source": "DB1 Retail Pharmacy POS",
                    "engine": "NoSQL Document Store",
                    "unfolded_operation": f"db.retail_scans.find({{'item_code': '{canonical}'}})",
                    "projection": "dispensary, pos_terminal, geo_coordinates, transaction, telemetry",
                    "purpose": "Detect duplicate scans, velocity anomalies, and unauthorized vendor sales"
                },
                {
                    "target_source": "DB2 Distributor ERP",
                    "engine": "Relational SQL (SQLite)",
                    "unfolded_operation": f"SELECT b.*, d.company_name, d.is_authorized FROM distribution_batches b JOIN distributors d ON b.distributor_id = d.distributor_id WHERE b.batch_serial = '{canonical}'",
                    "purpose": "Audit supply chain custody, cold-chain temperature excursion, transit route"
                },
                {
                    "target_source": "DB3 CDSCO Master Registry",
                    "engine": "Central MDM Catalog (SQLite)",
                    "unfolded_operation": f"SELECT p.*, m.company_name, m.license_no FROM products p JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id WHERE p.product_uid = '{canonical}'",
                    "purpose": "Verify statutory existence, authorized distributors, batch certificate QC"
                },
                {
                    "target_source": "DB4 Ministry INGRAM Portal",
                    "engine": "HTTP RESTful Microservice",
                    "unfolded_operation": f"GET /api/v1/dossier?item_ref={canonical} [Headers: Authorization: Bearer CDSCO-MCA-2026-KEY]",
                    "purpose": "Fetch active recalls, citizen grievance reports, laboratory chemical tests"
                }
            ]
        }
        return unfolded_plans

    def execute_mediated_query(self, query_code: str) -> Dict[str, Any]:
        """
        Executes the distributed query across all 4 sources, performs semantic
        transformations, resolves conflicts, and measures execution telemetry.
        """
        start_time = time.perf_counter()

        # Step 0: Explain unfolding
        unfolding = self.explain_query_unfolding(query_code)
        canonical = unfolding["entity_linkage"]["canonical_target"]

        # Step 1: Distributed query execution via resolver
        record: ItemRecord = resolve(canonical, raw_input=query_code)
        total_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Structure the mediated response with provenance
        return {
            "query_input": query_code,
            "canonical_id": canonical,
            "total_latency_ms": total_time_ms,
            "query_unfolding": unfolding,
            "entity_resolution": asdict(record.entity_resolution) if record.entity_resolution else None,
            "sources_contacted": {
                "db1_nosql": {
                    "source": "DB1 Retail POS (NoSQL)",
                    "found": record.purchase.found,
                    "records_count": len(record.purchase.events),
                    "native_query": record.purchase.query_executed,
                    "execution_time_ms": record.source_telemetry.get("db1_nosql", {}).get("latency_ms", 0.0)
                },
                "db2_relational": {
                    "source": "DB2 Distributor ERP (Relational SQL)",
                    "found": record.distribution.found,
                    "records_count": len(record.distribution.batches),
                    "native_query": record.distribution.query_executed,
                    "execution_time_ms": record.source_telemetry.get("db2_relational", {}).get("latency_ms", 0.0)
                },
                "db3_mdm": {
                    "source": "DB3 CDSCO Registry (MDM Relational)",
                    "found": record.manufacturer.found,
                    "product_name": record.manufacturer.product.get("product_name") if record.manufacturer.product else None,
                    "native_query": record.manufacturer.query_executed,
                    "execution_time_ms": record.source_telemetry.get("db3_mdm", {}).get("latency_ms", 0.0)
                },
                "db4_rest": {
                    "source": "DB4 Ministry Web Service (HTTP REST)",
                    "found": record.ministry.found,
                    "complaints_count": len(record.ministry.complaints),
                    "alerts_count": len(record.ministry.alerts),
                    "native_query": record.ministry.query_executed,
                    "execution_time_ms": record.source_telemetry.get("db4_rest", {}).get("latency_ms", 0.0)
                }
            },
            "semantic_transformations": record.semantic_transformations,
            "conflicts_detected_and_arbitrated": [
                {
                    "conflict_type": c.conflict_type,
                    "sources_in_conflict": c.sources_involved,
                    "governing_policy": c.governing_policy,
                    "winning_source": c.winning_source,
                    "severity": c.severity,
                    "resolution": c.description
                }
                for c in record.conflicts_resolved
            ]
        }

    def execute_distributed_query(self, query_code: str, simulate_partition: bool = False) -> Dict[str, Any]:
        """
        Executes true distributed HTTP network queries across PC 1 and PC 2 endpoints.
        Demonstrates:
          - Challenge 6: Network Partition Tolerance & Circuit Breaker (CAP Theorem)
          - Challenge 7: Schema Evolution & Version Drift Adaptation
        """
        cfg = get_topology_config()
        pc1_url = cfg["pc1_node"]["url"]
        pc2_url = cfg["pc2_node"]["url"]

        start_time = time.perf_counter()
        unfolding = self.explain_query_unfolding(query_code)
        canonical = unfolding["entity_linkage"]["canonical_target"]

        import urllib.request
        import urllib.error

        # Query PC 1 (Retail & Logistics)
        pc1_db1_data = {}
        pc1_db2_data = {}
        t_pc1_start = time.perf_counter()
        try:
            req1 = urllib.request.Request(f"{pc1_url}/api/v1/pos/scans?scan_code={canonical}")
            with urllib.request.urlopen(req1, timeout=1.5) as r1:
                pc1_db1_data = json.loads(r1.read().decode("ascii"))
        except Exception as e:
            pc1_db1_data = {"error": str(e), "found": False, "documents": []}

        try:
            req2 = urllib.request.Request(f"{pc1_url}/api/v1/distributor/batches?batch_serial={canonical}")
            with urllib.request.urlopen(req2, timeout=1.5) as r2:
                pc1_db2_data = json.loads(r2.read().decode("ascii"))
        except Exception as e:
            pc1_db2_data = {"error": str(e), "found": False, "batches": []}
        t_pc1_ms = round((time.perf_counter() - t_pc1_start) * 1000, 2)

        # Challenge 7: Apply Schema Evolution Adapter on returned retail documents
        evolved_docs = []
        schema_evolution_applied = None
        for doc in pc1_db1_data.get("documents", []):
            adapted = SchemaEvolutionAdapter.adapt_retail_scan(doc)
            evolved_docs.append(adapted)
            if not schema_evolution_applied:
                schema_evolution_applied = adapted.get("schema_evolution_applied")

        # Query PC 2 (Regulatory Authority) with Circuit Breaker
        pc2_db3_data = {}
        pc2_db4_data = {}
        t_pc2_start = time.perf_counter()
        circuit_breaker = {"triggered": False}

        if simulate_partition:
            circuit_breaker = {
                "triggered": True,
                "partitioned_node": "PC 2 (Regulatory Authority)",
                "reason": "SIMULATED_NETWORK_PARTITION (CAP Theorem)",
                "policy": "GRACEFUL_DEGRADATION_LOCAL_CUSTODY",
                "confidence_penalty": "Confidence capped at 50% due to unconfirmed statutory status"
            }
            pc2_db3_data = {"found": False, "status": "PARTITIONED"}
            pc2_db4_data = {"found": False, "status": "PARTITIONED"}
        else:
            try:
                req3 = urllib.request.Request(f"{pc2_url}/api/v1/cdsco/product?product_uid={canonical}")
                with urllib.request.urlopen(req3, timeout=1.5) as r3:
                    pc2_db3_data = json.loads(r3.read().decode("ascii"))
            except Exception as e:
                circuit_breaker = {
                    "triggered": True,
                    "partitioned_node": "PC 2 (Regulatory Authority)",
                    "reason": f"Connection Failure: {e}",
                    "policy": "GRACEFUL_DEGRADATION_LOCAL_CUSTODY",
                    "confidence_penalty": "Confidence capped at 50% due to unconfirmed statutory status"
                }
                pc2_db3_data = {"found": False, "status": "UNREACHABLE"}

            try:
                req4 = urllib.request.Request(f"{pc2_url}/api/v1/dossier?item_ref={canonical}")
                with urllib.request.urlopen(req4, timeout=1.5) as r4:
                    pc2_db4_data = json.loads(r4.read().decode("ascii"))
            except Exception as e:
                pc2_db4_data = {"found": False, "status": "UNREACHABLE"}

        t_pc2_ms = round((time.perf_counter() - t_pc2_start) * 1000, 2)
        total_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "query_input": query_code,
            "canonical_id": canonical,
            "execution_mode": "DISTRIBUTED_HTTP_MULTI_NODE",
            "total_latency_ms": total_time_ms,
            "network_nodes": {
                "pc1_node": {
                    "name": "PC 1: Retail & Logistics Edge Node",
                    "endpoint": pc1_url,
                    "status": "ONLINE" if "error" not in pc1_db1_data else "ERROR",
                    "latency_ms": t_pc1_ms,
                    "db1_pos_found": pc1_db1_data.get("found", False),
                    "db2_ledger_found": pc1_db2_data.get("found", False)
                },
                "pc2_node": {
                    "name": "PC 2: Regulatory Authority Cloud Node",
                    "endpoint": pc2_url,
                    "status": "PARTITIONED / OFFLINE" if circuit_breaker["triggered"] else "ONLINE",
                    "latency_ms": t_pc2_ms,
                    "db3_mdm_found": pc2_db3_data.get("found", False),
                    "db4_ministry_found": pc2_db4_data.get("found", False)
                }
            },
            "circuit_breaker": circuit_breaker,
            "schema_evolution": schema_evolution_applied or {"detected_version": "v1.0_LEGACY", "adaptation_rules": ["PASS_THROUGH"]},
            "query_unfolding": unfolding
        }

    def simulate_all_challenges(self) -> Dict[str, Any]:
        """
        Runs an academic simulation demonstrating all 7 Information Integration Challenges.
        """
        test_scenarios = [
            {
                "challenge": "Challenge 1 & 2: System & Structural Heterogeneity (NoSQL vs Relational vs REST)",
                "item": "MED-ASALI-002",
                "explanation": "Simultaneously queries a native NoSQL Document Store with nested POS payloads, Relational SQL with multi-table FK JOINs, and a live REST Microservice with Bearer auth."
            },
            {
                "challenge": "Challenge 3: Semantic & Unit Representation Heterogeneity",
                "item": "MED-ASALI-009",
                "explanation": "Normalizes temperature scales (Fahrenheit to Celsius), currencies (USD to INR), and multi-format timestamps (epoch ms and gazette DD/MM/YYYY into ISO-8601)."
            },
            {
                "challenge": "Challenge 4: Fuzzy Entity Resolution & OCR Typo Linkage",
                "item": "med-asall-002",
                "explanation": "Resolves noisy barcode with lower-case and OCR transposition ('l' vs 'I') to canonical 'MED-ASALI-002' using Jaro-Winkler string similarity (96.5% match)."
            },
            {
                "challenge": "Challenge 5: Cross-Source Conflict Arbitration (Statutory Precedence & Causality)",
                "item": "MED-RECALL-001",
                "explanation": "Arbitrates conflict where DB3 shows an active product, but DB4 Government Microservice issues an emergency diethylene glycol recall, overriding DB3 via Statutory Precedence."
            },
            {
                "challenge": "Challenge 6: Distributed Network Partition & Asynchronous Fault Tolerance (CAP Theorem)",
                "item": "MED-ASALI-001",
                "explanation": "Simulates network partition on PC 2 (Cloud Authority). The Mediator circuit breaker activates, gracefully falls back to local PC 1 custody records, and applies an optimistic confidence cap."
            },
            {
                "challenge": "Challenge 7: Schema Evolution & Version Drift Adaptation",
                "item": "MED-ASALI-001",
                "explanation": "Demonstrates automatic adaptation when PC 1 upgrades to Schema v2.0 (GS1 Digital Link URI extraction, ISO minor currency division, GLN facility flattening)."
            }
        ]

        results = []
        for s in test_scenarios:
            if "Partition" in s["challenge"]:
                out = self.execute_distributed_query(s["item"], simulate_partition=True)
                results.append({
                    "scenario": s["challenge"],
                    "test_item": s["item"],
                    "academic_explanation": s["explanation"],
                    "execution_summary": {
                        "canonical_id": out["canonical_id"],
                        "latency_ms": out["total_latency_ms"],
                        "circuit_breaker": out["circuit_breaker"]["triggered"],
                        "partitioned_node": out["circuit_breaker"].get("partitioned_node")
                    }
                })
            elif "Schema Evolution" in s["challenge"]:
                v2_sample = {
                    "digital_link_uri": "https://id.cdsco.gov.in/01/08901234567890/21/MED-ASALI-001",
                    "transaction_pricing": {"amount_gross": 23000, "iso_currency": "INR", "precision": 2},
                    "dispensing_facility": {"gln": "GLN-890123456701", "name": "Apollo Pharmacy Superstore Hub"}
                }
                adapted = SchemaEvolutionAdapter.adapt_retail_scan(v2_sample)
                results.append({
                    "scenario": s["challenge"],
                    "test_item": s["item"],
                    "academic_explanation": s["explanation"],
                    "execution_summary": {
                        "canonical_id": adapted["scan_code"],
                        "adapted_price": adapted["price_paid"],
                        "adapted_facility": adapted["vendor_name"],
                        "schema_version": adapted["schema_evolution_applied"]["detected_version"]
                    }
                })
            else:
                out = self.execute_mediated_query(s["item"])
                results.append({
                    "scenario": s["challenge"],
                    "test_item": s["item"],
                    "academic_explanation": s["explanation"],
                    "execution_summary": {
                        "canonical_id": out["canonical_id"],
                        "latency_ms": out["total_latency_ms"],
                        "sources_online": sum(1 for src in out["sources_contacted"].values() if src["found"]),
                        "conflicts": len(out["conflicts_detected_and_arbitrated"]),
                        "transformations": len(out["semantic_transformations"])
                    }
                })
        return {"demonstration": "IIA Academic Challenge Suite (7 Challenges)", "results": results}


def print_cli_summary(data: Dict[str, Any]):
    """Pretty prints mediator query execution in pure ASCII."""
    print("=" * 72)
    print("  ASALI-NAKALI GLOBAL-AS-VIEW (GAV) QUERY MEDIATOR")
    print("=" * 72)
    print(f"  Input Query Code     : {data.get('query_input')}")
    print(f"  Canonical Resolved   : {data.get('canonical_id')}")
    print(f"  Total Execution Time : {data.get('total_latency_ms')} ms")
    print("-" * 72)

    ent = data.get("entity_resolution")
    if ent and ent.get("is_fuzzy_linked"):
        print(f"  [ENTITY RESOLUTION] Fuzzy Linked: {ent.get('match_explanation')}")
        print(f"    Confidence: {round(ent.get('confidence_score', 0) * 100, 1)}% | Target: {ent.get('resolved_canonical')}")
        print("-" * 72)

    print("  FEDERATED SUB-QUERY EXECUTION:")
    for key, src in data.get("sources_contacted", {}).items():
        status = "FOUND" if src.get("found") else "NOT FOUND"
        print(f"  * {src.get('source')} -> [{status}] ({src.get('execution_time_ms', 0)} ms)")
        print(f"    Native Query: {src.get('native_query')}")

    trans = data.get("semantic_transformations", [])
    if trans:
        print("-" * 72)
        print(f"  SEMANTIC TRANSFORMATIONS APPLIED ({len(trans)}):")
        for t in trans:
            print(f"  * Field [{t.get('field')}]: '{t.get('original')}' -> '{t.get('canonical')}'")

    conflicts = data.get("conflicts_detected_and_arbitrated", [])
    if conflicts:
        print("-" * 72)
        print(f"  CROSS-SOURCE CONFLICT ARBITRATIONS ({len(conflicts)}):")
        for c in conflicts:
            print(f"  * Policy: {c.get('governing_policy')} [{c.get('severity')}]")
            print(f"    Resolution: {c.get('resolution')}")
            print(f"    Sources   : {', '.join(c.get('sources_in_conflict', []))}")

    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="GAV Query Mediator for Polyglot Medicine Traceability")
    parser.add_argument("--item", "-i", default="MED-ASALI-002", help="Item code or corrupted barcode to resolve")
    parser.add_argument("--explain", "-e", action="store_true", help="Display query unfolding and execution plan")
    parser.add_argument("--simulate-challenges", "-s", action="store_true", help="Run the full 7-challenge IIA demonstration suite")
    parser.add_argument("--manifest", "-m", action="store_true", help="Print federated source manifest and health")
    parser.add_argument("--nodes", action="store_true", help="Print multi-PC / Docker network topology configuration")
    parser.add_argument("--distributed", "-d", action="store_true", help="Execute live distributed network query across PC 1 and PC 2 nodes")
    parser.add_argument("--simulate-partition", "-p", action="store_true", help="Simulate network partition on PC 2 (CAP Theorem Challenge)")
    parser.add_argument("--json", action="store_true", help="Output results as structured JSON")

    args = parser.parse_args()
    mediator = GavQueryMediator()

    if args.nodes:
        cfg = get_topology_config()
        if args.json:
            print(json.dumps(cfg, indent=2))
        else:
            print("DISTRIBUTED MULTI-PC / DOCKER TOPOLOGY:")
            print(f"  * {cfg['pc1_node']['name']} -> {cfg['pc1_node']['url']}")
            print(f"  * {cfg['pc2_node']['name']} -> {cfg['pc2_node']['url']}")
            print(f"  * {cfg['mediator_node']['name']} -> {cfg['mediator_node']['url']}")
        return

    if args.manifest:
        man = mediator.get_source_manifest()
        if args.json:
            print(json.dumps(man, indent=2))
        else:
            print("FEDERATED SOURCES MANIFEST:")
            for s in man["sources"]:
                print(f"  [{s['status']}] {s['source_id']} ({s['paradigm']}) -> {s['location']}")
        return

    if args.simulate_challenges:
        res = mediator.simulate_all_challenges()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("IIA ACADEMIC CHALLENGES DEMONSTRATION (7 CHALLENGES):")
            for r in res["results"]:
                print(f"\n[+] {r['scenario']}")
                print(f"    Item: {r['test_item']} -> Summary: {r['execution_summary']}")
                print(f"    Explanation: {r['academic_explanation']}")
        return

    if args.distributed or args.simulate_partition:
        res = mediator.execute_distributed_query(args.item, simulate_partition=args.simulate_partition)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("=" * 72)
            print("  DISTRIBUTED MULTI-PC MEDIATOR EXECUTION")
            print("=" * 72)
            print(f"  Item: {res['canonical_id']} | Latency: {res['total_latency_ms']} ms")
            print(f"  * PC 1 Node: {res['network_nodes']['pc1_node']['status']} ({res['network_nodes']['pc1_node']['latency_ms']} ms)")
            print(f"  * PC 2 Node: {res['network_nodes']['pc2_node']['status']} ({res['network_nodes']['pc2_node']['latency_ms']} ms)")
            cb = res.get("circuit_breaker", {})
            if cb.get("triggered"):
                print(f"  [!] CIRCUIT BREAKER TRIGGERED: {cb.get('reason')}")
                print(f"      Policy: {cb.get('policy')}")
                print(f"      Penalty: {cb.get('confidence_penalty')}")
            se = res.get("schema_evolution", {})
            print(f"  * Schema Evolution: {se.get('detected_version')} ({', '.join(se.get('adaptation_rules', []))})")
            print("=" * 72)
        return

    result = mediator.execute_mediated_query(args.item)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_cli_summary(result)


if __name__ == "__main__":
    main()

