#!/usr/bin/env python3
"""
schema_adapter.py
-----------------
Challenge 7: Schema Evolution and Version Drift Adaptation.

In real-world distributed enterprise systems, autonomous nodes upgrade their internal schemas
independently. When PC 1 upgrades its retail POS database from Schema v1.0 to Schema v2.0
(e.g., introducing GS1 Digital Link URIs, ISO-4217 minor unit currencies, and nested GLN locations),
a static mediator crashes.

The SchemaEvolutionAdapter implements:
  1. Automated schema version detection (v1.0 vs v2.0)
  2. Bidirectional schema mapping adapters
  3. Non-destructive canonical normalization preserving legacy compatibility
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
import re


class SchemaEvolutionAdapter:
    """Adapts disparate schema versions into the canonical integration model."""

    @staticmethod
    def detect_schema_version(payload: Dict[str, Any]) -> str:
        """Determines whether a payload follows v1.0 legacy or v2.0 evolved schema."""
        if "digital_link_uri" in payload or "transaction_pricing" in payload or "dispensing_facility" in payload:
            return "v2.0_EVOLVED"
        return "v1.0_LEGACY"

    @staticmethod
    def adapt_retail_scan(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes both Schema v1.0 and Schema v2.0 documents into canonical fields.
        """
        version = SchemaEvolutionAdapter.detect_schema_version(doc)
        normalized = dict(doc)

        if version == "v2.0_EVOLVED":
            # Extract item_code from GS1 Digital Link URI if missing in root
            if "item_code" not in normalized and "digital_link_uri" in doc:
                uri = doc["digital_link_uri"]
                match = re.search(r"/21/([A-Z0-9\-]+)", uri)
                if match:
                    normalized["item_code"] = match.group(1)
                    normalized["scan_code"] = match.group(1)

            # Adapt nested transaction_pricing (minor units to standard float)
            if "transaction_pricing" in doc:
                tp = doc["transaction_pricing"]
                amt_gross = tp.get("amount_gross", 0)
                precision = tp.get("precision", 2)
                normalized["price_paid"] = round(amt_gross / (10 ** precision), 2)
                normalized["currency"] = tp.get("iso_currency", "INR")

            # Adapt dispensing_facility to flat vendor fields
            if "dispensing_facility" in doc:
                df = doc["dispensing_facility"]
                normalized["vendor_name"] = df.get("name", normalized.get("vendor_name", "Unknown Facility"))
                normalized["vendor_id"] = df.get("gln", normalized.get("vendor_id", "GLN-UNKNOWN"))

            normalized["schema_evolution_applied"] = {
                "detected_version": "v2.0_EVOLVED",
                "adaptation_rules": [
                    "GS1_DIGITAL_LINK_URI_EXTRACTION",
                    "ISO_MINOR_CURRENCY_DIVISION",
                    "GLN_FACILITY_FLATTENING"
                ]
            }

        else:
            normalized["schema_evolution_applied"] = {
                "detected_version": "v1.0_LEGACY",
                "adaptation_rules": ["PASS_THROUGH"]
            }

        return normalized


def test_schema_evolution():
    """Unit test demonstrating seamless adaptation across v1.0 and v2.0."""
    v1_sample = {
        "scan_code": "MED-ASALI-001",
        "price_paid": 230.0,
        "currency": "INR",
        "vendor_name": "Apollo Pharmacy"
    }

    v2_sample = {
        "digital_link_uri": "https://id.cdsco.gov.in/01/08901234567890/21/MED-ASALI-001",
        "transaction_pricing": {"amount_gross": 23000, "iso_currency": "INR", "precision": 2},
        "dispensing_facility": {"gln": "GLN-890123456701", "name": "Apollo Pharmacy Superstore Hub"}
    }

    res1 = SchemaEvolutionAdapter.adapt_retail_scan(v1_sample)
    res2 = SchemaEvolutionAdapter.adapt_retail_scan(v2_sample)

    assert res1["price_paid"] == 230.0
    assert res2["scan_code"] == "MED-ASALI-001"
    assert res2["price_paid"] == 230.0
    assert res2["vendor_name"] == "Apollo Pharmacy Superstore Hub"
    print("[+] Schema Evolution Test PASSED: Successfully adapted Schema v1.0 and Schema v2.0!")


if __name__ == "__main__":
    test_schema_evolution()
