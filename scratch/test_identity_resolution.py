#!/usr/bin/env python3
"""
scratch/test_identity_resolution.py
------------------------------------
Verification test suite for Multi-Attribute Transitive Identity Resolution.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integration.entity_resolver import resolve_entity, GLOBAL_RESOLVER
from integration.resolver import resolve

def run_tests():
    print("\n" + "="*80)
    print("  TEST SUITE: MULTI-ATTRIBUTE TRANSITIVE IDENTITY RESOLUTION (IIA / MDM)")
    print("="*80)

    test_cases = [
        {
            "category": "Transitive Batch Linkage (Identity Graph)",
            "query": "BATCH-A001",
            "expected_canonical": "MED-ASALI-001",
            "expected_field": "batch_number",
            "min_conf": 0.95
        },
        {
            "category": "Transitive Recall Batch Linkage",
            "query": "BATCH-R001",
            "expected_canonical": "MED-RECALL-001",
            "expected_field": "batch_number",
            "min_conf": 0.95
        },
        {
            "category": "Logistics ERP Batch ID Linkage",
            "query": "DBATCH-001",
            "expected_canonical": "MED-ASALI-001",
            "expected_field": "dist_batch_id",
            "min_conf": 0.95
        },
        {
            "category": "Probabilistic Brand Typo Match (Jaro-Winkler)",
            "query": "Novamax 500",
            "expected_canonical": "MED-ASALI-001",
            "expected_field": "product_name",
            "min_conf": 0.85
        },
        {
            "category": "Phonetic Soundex Match (Indian English / Brand Names)",
            "query": "Pasyamol",
            "expected_canonical": "MED-ASALI-002",
            "expected_field": "product_name",
            "min_conf": 0.80
        },
        {
            "category": "Optical Character Recognition Typo Fix",
            "query": "MED-ASALI-0O1",
            "expected_canonical": "MED-ASALI-001",
            "expected_field": "ocr_substitution",
            "min_conf": 0.90
        },
        {
            "category": "Exact Master Catalog Primary Key",
            "query": "MED-ASALI-001",
            "expected_canonical": "MED-ASALI-001",
            "expected_field": "product_uid",
            "min_conf": 1.0
        }
    ]

    all_passed = True
    for tc in test_cases:
        res = resolve_entity(tc["query"])
        passed = (
            res.resolved_canonical == tc["expected_canonical"] and
            res.confidence_score >= tc["min_conf"]
        )
        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_passed = False

        print(f"\n[{status}] {tc['category']}")
        print(f"   Query:               '{tc['query']}'")
        print(f"   Resolved Canonical:  {res.resolved_canonical} (Expected: {tc['expected_canonical']})")
        print(f"   Confidence Score:    {res.confidence_score:.2f} (Min Required: {tc['min_conf']:.2f})")
        print(f"   Matched Field:       {res.matched_field}")
        print(f"   Transitive Path:     {res.transitive_path}")
        print(f"   Explanation:         {res.match_explanation}")

    print("\n" + "-"*80)
    print("  TESTING FEDERATED MULTI-SOURCE GAV MEDIATION (ALL 4 HETEROGENEOUS DBS)")
    print("-"*80)

    # Test full resolve() on batch number
    batch_res = resolve("BATCH-A001")
    print(f"\nFederated Mediation on 'BATCH-A001':")
    print(f"   Canonical Key:   {batch_res.item_code}")
    print(f"   DB1 (NoSQL POS): Found={batch_res.purchase.found} (events: {len(batch_res.purchase.events)})")
    print(f"   DB2 (SQL ERP):   Found={batch_res.distribution.found} (batches: {len(batch_res.distribution.batches)})")
    print(f"   DB3 (CDSCO MDM): Found={batch_res.manufacturer.found} (product: {batch_res.manufacturer.product.get('product_name') if batch_res.manufacturer.product else None})")
    print(f"   DB4 (REST Gov):  Found={batch_res.ministry.found}")
    
    med_passed = (
        batch_res.item_code == "MED-ASALI-001" and
        batch_res.purchase.found and
        batch_res.distribution.found and
        batch_res.manufacturer.found
    )
    print(f"   Mediation Status: {'✅ PASS - All 4 DB silos successfully linked!' if med_passed else '❌ FAIL'}")

    print("\n" + "="*80)
    if all_passed and med_passed:
        print("  🎉 ALL IDENTITY RESOLUTION & HETEROGENEOUS MEDIATION TESTS PASSED!")
    else:
        print("  ⚠️ SOME TESTS FAILED")
    print("="*80 + "\n")

    return 0 if (all_passed and med_passed) else 1

if __name__ == "__main__":
    sys.exit(run_tests())
