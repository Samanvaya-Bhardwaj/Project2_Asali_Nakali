/**
 * data.js - Asali-Nakali benchmark dossier corpus + signal lexicon.
 * Extracted verbatim from the legacy app.js; the verification payload shape
 * is the same one /api/v1/verify returns, so the UI renders live or embedded data identically.
 */

const BENCHMARK_DATA = {
  "MED-ASALI-001": {
    "item_code": "MED-ASALI-001",
    "verdict": "ASALI",
    "trust_score": 100,
    "confidence_pct": 70,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Novamox 500mg",
      "generic_name": "Amoxycillin",
      "mfg_name": "Cipla Ltd",
      "registration_no": "CDSCO/MFG/001/2020",
      "category": "antibiotic",
      "dosage_form": "capsule",
      "strength": "500mg",
      "batch_number": "BATCH-A001",
      "mfg_date": "2025-01-15",
      "expiry_date": "2027-01-14",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 115.0
    },
    "distribution": {
      "found": true,
      "count": 2,
      "distributors": "Apollo Supply Chain Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2025-02-10",
          "status": "delivered"
        },
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2025-02-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Apollo Pharmacy",
      "last_timestamp": "2025-03-10 09:15:00",
      "avg_price": 230.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Apollo Pharmacy",
          "location": "Mumbai",
          "time": "2025-03-10 09:15:00",
          "price": 230.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 1,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "LAB_TEST_PASSED",
        "value": 5,
        "db_source": "DB4  -  Ministry Lab Reports",
        "description": "MCA Lab PASSED (Central Drug Laboratory Kolkata). Product quality verified by accredited lab.",
        "tier": "SOFT"
      },
      {
        "signal": "ALL_CHECKS_CLEAN",
        "value": 5,
        "db_source": "All 4 DBs",
        "description": "All Tier-2 compliance checks passed. Full supply chain verified. No complaints, no cold chain issues, no price anomalies.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "All checks passed. Medicine appears genuine and safe."
    ]
  },
  "MED-ASALI-002": {
    "item_code": "MED-ASALI-002",
    "verdict": "SUSPICIOUS",
    "trust_score": 65,
    "confidence_pct": 90,
    "lifecycle_state": "SUSPICIOUS",
    "veto_codes": [],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ASALI002",
    "product": {
      "found": true,
      "product_name": "Pacimol 500mg",
      "generic_name": "Paracetamol",
      "mfg_name": "Sun Pharmaceutical Industries Ltd",
      "registration_no": "CDSCO/MFG/002/2020",
      "category": "analgesic",
      "dosage_form": "tablet",
      "strength": "500mg",
      "batch_number": "BATCH-A002",
      "mfg_date": "2025-02-10",
      "expiry_date": "2027-02-09",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 32.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Apollo Supply Chain Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2025-02-12",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 6,
      "vendors": 5,
      "vendor_names": "MedPlus Pharmacy, Apollo Pharmacy, Noble Chemist",
      "last_timestamp": "2025-05-02 08:28:00",
      "avg_price": 32.0,
      "anomaly_count": 5,
      "events": [
        {
          "vendor": "Noble Chemist",
          "location": "Mumbai",
          "time": "2025-05-02 08:28:00",
          "price": 32.0
        },
        {
          "vendor": "Wellness Forever Chemist",
          "location": "New Delhi",
          "time": "2025-05-02 08:21:00",
          "price": 32.0
        },
        {
          "vendor": "AIIMS Hospital Dispensary",
          "location": "New Delhi",
          "time": "2025-05-02 08:14:00",
          "price": 32.0
        },
        {
          "vendor": "MedPlus Pharmacy",
          "location": "Bengaluru",
          "time": "2025-05-02 08:07:00",
          "price": 32.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": false,
      "complaints": 2,
      "open_cases": 2,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "MULTI_LOCATION_ANOMALY",
        "value": -25,
        "db_source": "DB1 - Dispensary Scan Log",
        "description": "5 store scans in 28 mins across 3 cities (Mumbai, New Delhi, Bengaluru). Barcode cloning detected.",
        "tier": "SOFT"
      },
      {
        "signal": "OPEN_COMPLAINTS",
        "value": -10,
        "db_source": "DB4 - Ministry of Consumer Affairs",
        "description": "2 active MCA complaints. Categories: counterfeit barcode cloning.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [
      {
        "severity": "critical",
        "anomaly_type": "MULTI_LOCATION_SCAN",
        "description": "5 store scans in 28 mins across 3 cities (DB1) - Barcode cloning detected"
      }
    ],
    "recommendations": [
      "Barcode cloning detected: 5 store scans across 3 cities in 28 mins (DB1).",
      "2 unresolved complaint(s) with MCA.",
      "Quarantine unit pack and verify physical holographic security seal."
    ]
  },
  "MED-ASALI-003": {
    "item_code": "MED-ASALI-003",
    "verdict": "ASALI",
    "trust_score": 100,
    "confidence_pct": 65,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Metsmall 850mg",
      "generic_name": "Metformin",
      "mfg_name": "Dr. Reddy's Laboratories Ltd",
      "registration_no": "CDSCO/MFG/003/2019",
      "category": "antidiabetic",
      "dosage_form": "tablet",
      "strength": "850mg",
      "batch_number": "BATCH-A003",
      "mfg_date": "2025-03-05",
      "expiry_date": "2027-03-04",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 140.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Apollo Supply Chain Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2025-03-15",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "AIIMS Hospital Dispensary",
      "last_timestamp": "2025-03-22 14:00:00",
      "avg_price": 140.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "AIIMS Hospital Dispensary",
          "location": "New Delhi",
          "time": "2025-03-22 14:00:00",
          "price": 140.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "ALL_CHECKS_CLEAN",
        "value": 5,
        "db_source": "All 4 DBs",
        "description": "All Tier-2 compliance checks passed. Full supply chain verified. No complaints, no cold chain issues, no price anomalies.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "All checks passed. Medicine appears genuine and safe."
    ]
  },
  "MED-ASALI-004": {
    "item_code": "MED-ASALI-004",
    "verdict": "ASALI",
    "trust_score": 90,
    "confidence_pct": 65,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Falcinil 80/480mg",
      "generic_name": "Artemether+Lumefantrine",
      "mfg_name": "Sun Pharmaceutical Industries Ltd",
      "registration_no": "CDSCO/MFG/004/2021",
      "category": "antimalarial",
      "dosage_form": "tablet",
      "strength": "80mg+480mg",
      "batch_number": "BATCH-A004",
      "mfg_date": "2025-01-20",
      "expiry_date": "2026-07-19",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 280.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "MedPlus Distribution Pvt Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "MedPlus Distribution Pvt Ltd",
          "date": "2025-02-05",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Wellness Forever Chemist",
      "last_timestamp": "2025-03-12 11:30:00",
      "avg_price": 840.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Wellness Forever Chemist",
          "location": "New Delhi",
          "time": "2025-03-12 11:30:00",
          "price": 840.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "PRODUCT_EXPIRED",
        "value": -10,
        "db_source": "DB3  -  Manufacturer Registry",
        "description": "Product expired on 2026-07-19. Selling expired medicine is illegal.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      " Product expired on 2026-07-19. Do not consume."
    ]
  },
  "MED-ASALI-005": {
    "item_code": "MED-ASALI-005",
    "verdict": "ASALI",
    "trust_score": 100,
    "confidence_pct": 65,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Atorva 40mg",
      "generic_name": "Atorvastatin",
      "mfg_name": "Cipla Ltd",
      "registration_no": "CDSCO/MFG/005/2020",
      "category": "cardiovascular",
      "dosage_form": "tablet",
      "strength": "40mg",
      "batch_number": "BATCH-A005",
      "mfg_date": "2025-04-01",
      "expiry_date": "2027-03-31",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 180.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Apollo Supply Chain Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2025-04-10",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "MedPlus Pharmacy",
      "last_timestamp": "2025-04-18 16:45:00",
      "avg_price": 180.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "MedPlus Pharmacy",
          "location": "Bengaluru",
          "time": "2025-04-18 16:45:00",
          "price": 180.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "ALL_CHECKS_CLEAN",
        "value": 5,
        "db_source": "All 4 DBs",
        "description": "All Tier-2 compliance checks passed. Full supply chain verified. No complaints, no cold chain issues, no price anomalies.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "All checks passed. Medicine appears genuine and safe."
    ]
  },
  "MED-ASALI-006": {
    "item_code": "MED-ASALI-006",
    "verdict": "ASALI",
    "trust_score": 100,
    "confidence_pct": 65,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Electral ORS",
      "generic_name": "ORS Formula",
      "mfg_name": "Dr. Reddy's Laboratories Ltd",
      "registration_no": "CDSCO/MFG/006/2022",
      "category": "rehydration",
      "dosage_form": "powder",
      "strength": "WHO formula",
      "batch_number": "BATCH-A006",
      "mfg_date": "2025-02-15",
      "expiry_date": "2027-02-14",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 22.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Entero Healthcare Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Entero Healthcare Solutions Ltd",
          "date": "2025-03-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Fortis Healthworld Pharmacy",
      "last_timestamp": "2025-03-15 08:00:00",
      "avg_price": 44.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Fortis Healthworld Pharmacy",
          "location": "Gurugram",
          "time": "2025-03-15 08:00:00",
          "price": 44.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "ALL_CHECKS_CLEAN",
        "value": 5,
        "db_source": "All 4 DBs",
        "description": "All Tier-2 compliance checks passed. Full supply chain verified. No complaints, no cold chain issues, no price anomalies.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "All checks passed. Medicine appears genuine and safe."
    ]
  },
  "MED-ASALI-007": {
    "item_code": "MED-ASALI-007",
    "verdict": "ASALI",
    "trust_score": 100,
    "confidence_pct": 65,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Ciplox 500mg",
      "generic_name": "Ciprofloxacin",
      "mfg_name": "Cipla Ltd",
      "registration_no": "CDSCO/MFG/007/2020",
      "category": "antibiotic",
      "dosage_form": "tablet",
      "strength": "500mg",
      "batch_number": "BATCH-A007",
      "mfg_date": "2025-05-10",
      "expiry_date": "2027-05-09",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 95.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "MedPlus Distribution Pvt Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "MedPlus Distribution Pvt Ltd",
          "date": "2025-05-20",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Noble Chemist",
      "last_timestamp": "2025-05-28 12:15:00",
      "avg_price": 95.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Noble Chemist",
          "location": "Mumbai",
          "time": "2025-05-28 12:15:00",
          "price": 95.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "ALL_CHECKS_CLEAN",
        "value": 5,
        "db_source": "All 4 DBs",
        "description": "All Tier-2 compliance checks passed. Full supply chain verified. No complaints, no cold chain issues, no price anomalies.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "All checks passed. Medicine appears genuine and safe."
    ]
  },
  "MED-ASALI-008": {
    "item_code": "MED-ASALI-008",
    "verdict": "ASALI",
    "trust_score": 100,
    "confidence_pct": 65,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Omez 20mg",
      "generic_name": "Omeprazole",
      "mfg_name": "Dr. Reddy's Laboratories Ltd",
      "registration_no": "CDSCO/MFG/008/2019",
      "category": "antacid",
      "dosage_form": "capsule",
      "strength": "20mg",
      "batch_number": "BATCH-A008",
      "mfg_date": "2025-03-20",
      "expiry_date": "2027-03-19",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 85.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Apollo Supply Chain Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2025-04-05",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Apollo Pharmacy",
      "last_timestamp": "2025-04-12 09:00:00",
      "avg_price": 170.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Apollo Pharmacy",
          "location": "Mumbai",
          "time": "2025-04-12 09:00:00",
          "price": 170.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "ALL_CHECKS_CLEAN",
        "value": 5,
        "db_source": "All 4 DBs",
        "description": "All Tier-2 compliance checks passed. Full supply chain verified. No complaints, no cold chain issues, no price anomalies.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "All checks passed. Medicine appears genuine and safe."
    ]
  },
  "MED-ASALI-009": {
    "item_code": "MED-ASALI-009",
    "verdict": "SUSPICIOUS",
    "trust_score": 65,
    "confidence_pct": 65,
    "lifecycle_state": "SUSPICIOUS",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Basalog 100 IU/ml",
      "generic_name": "Insulin glargine",
      "mfg_name": "Biocon Biologics Ltd",
      "registration_no": "CDSCO/MFG/009/2021",
      "category": "antidiabetic",
      "dosage_form": "injection",
      "strength": "100 IU/ml",
      "batch_number": "BATCH-A009",
      "mfg_date": "2025-06-01",
      "expiry_date": "2026-06-01",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 1,
      "msrp": 850.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Apollo Supply Chain Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2025-06-05",
          "status": "delivered",
          "notes": "Thermal excursion > 8C logged in transit"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "AIIMS Hospital Dispensary",
      "last_timestamp": "2025-06-15 10:00:00",
      "avg_price": 850.0,
      "anomaly_count": 1,
      "events": [
        {
          "vendor": "AIIMS Hospital Dispensary",
          "location": "New Delhi",
          "time": "2025-06-15 10:00:00",
          "price": 850.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "COLD_CHAIN_BROKEN",
        "value": -25,
        "db_source": "DB2 - Distributor Ledger",
        "description": "Thermal excursion > 8C logged during transit (DB2). Biological potency degraded.",
        "tier": "SOFT"
      },
      {
        "signal": "PRODUCT_EXPIRED",
        "value": -10,
        "db_source": "DB3 - CDSCO Registry",
        "description": "Product shelf-life expiry date recorded.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [
      {
        "severity": "high",
        "anomaly_type": "COLD_CHAIN_VIOLATION",
        "description": "Thermal excursion > 8C logged during transit (DB2)"
      }
    ],
    "recommendations": [
      "Thermal excursion > 8C logged during transit (DB2). Product potency may be compromised.",
      "Biological cold chain broken. Do not dispense without temperature log review."
    ]
  },
  "MED-ASALI-010": {
    "item_code": "MED-ASALI-010",
    "verdict": "ASALI",
    "trust_score": 100,
    "confidence_pct": 65,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Calcirol 1000 IU",
      "generic_name": "Cholecalciferol",
      "mfg_name": "Dr. Reddy's Laboratories Ltd",
      "registration_no": "CDSCO/MFG/010/2022",
      "category": "supplement",
      "dosage_form": "tablet",
      "strength": "1000IU",
      "batch_number": "BATCH-A010",
      "mfg_date": "2025-04-15",
      "expiry_date": "2027-04-14",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 340.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Entero Healthcare Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Entero Healthcare Solutions Ltd",
          "date": "2025-04-20",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Fortis Healthworld Pharmacy",
      "last_timestamp": "2025-04-28 11:30:00",
      "avg_price": 340.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Fortis Healthworld Pharmacy",
          "location": "Gurugram",
          "time": "2025-04-28 11:30:00",
          "price": 340.0
        }
      ]
    },
    "ministry": {
      "found": false,
      "blacklisted": false,
      "complaints": 0,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "ALL_CHECKS_CLEAN",
        "value": 5,
        "db_source": "All 4 DBs",
        "description": "All Tier-2 compliance checks passed. Full supply chain verified. No complaints, no cold chain issues, no price anomalies.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "All checks passed. Medicine appears genuine and safe."
    ]
  },
  "MED-NAKALI-001": {
    "item_code": "MED-NAKALI-001",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 55,
    "lifecycle_state": "UNKNOWN",
    "veto_codes": [
      "V1_PHANTOM_SERIAL",
      "V2_MINISTRY_BLACKLIST"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALI001",
    "product": {
      "found": false,
      "product_name": "UNKNOWN (Not in Manufacturer DB)",
      "generic_name": " - ",
      "mfg_name": " - ",
      "registration_no": " - ",
      "category": " - ",
      "dosage_form": " - ",
      "strength": " - ",
      "batch_number": " - ",
      "mfg_date": " - ",
      "expiry_date": " - ",
      "is_recalled": 0,
      "recall_reason": "",
      "gmp_certified": 0,
      "requires_cold_chain": 0,
      "msrp": 0.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "QuickMed Traders",
      "authorized": false,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 1,
      "batches": [
        {
          "distributor": "QuickMed Traders",
          "date": "2025-01-10",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Janata Medicos (Unlicensed Kiosk)",
      "last_timestamp": "2025-03-10 09:30:00",
      "avg_price": 45.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Janata Medicos (Unlicensed Kiosk)",
          "location": "Mumbai",
          "time": "2025-03-10 09:30:00",
          "price": 45.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": true,
      "complaints": 2,
      "open_cases": 2,
      "labs": 1,
      "lab_result": "N/A",
      "alerts": 1,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V1_PHANTOM_SERIAL",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item code 'MED-NAKALI-001' has NO record in the Manufacturer Product Registry (DB3 / CDSCO-registered products). A genuine medicine unit must be registered by a licensed CDSCO-approved manufacturer. This is an absolute NAKALI indicator.",
        "tier": "HARD_VETO"
      },
      {
        "signal": "V2_MINISTRY_BLACKLIST",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item is on the MCA/CDSCO BLACKLIST. Gazette order: N/A. Blacklisted on: 2025-03-20. Reason: Confirmed counterfeit - active ingredient absent. Not manufactured by Cipla.. Risk: Acute health risk - severe infection treatment failure..",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [
      {
        "severity": "critical",
        "anomaly_type": "PHANTOM_UNREGISTERED_SERIAL",
        "description": "Zero record in CDSCO database (File Not Found)"
      },
      {
        "severity": "high",
        "anomaly_type": "UNLICENSED_VENDOR_SALE",
        "description": "Item sold at unlicensed vendor"
      }
    ],
    "recommendations": [
      "Zero record in CDSCO database (File Not Found).",
      "Do NOT purchase. No CDSCO manufacturer registration found.",
      "Item is on MCA/CDSCO BLACKLIST. Report to authorities."
    ]
  },
  "MED-NAKALI-002": {
    "item_code": "MED-NAKALI-002",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 50,
    "lifecycle_state": "UNKNOWN",
    "veto_codes": [
      "V1_PHANTOM_SERIAL",
      "V2_MINISTRY_BLACKLIST"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALI002",
    "product": {
      "found": false,
      "product_name": "UNKNOWN (Not in Manufacturer DB)",
      "generic_name": " - ",
      "mfg_name": " - ",
      "registration_no": " - ",
      "category": " - ",
      "dosage_form": " - ",
      "strength": " - ",
      "batch_number": " - ",
      "mfg_date": " - ",
      "expiry_date": " - ",
      "is_recalled": 0,
      "recall_reason": "",
      "gmp_certified": 0,
      "requires_cold_chain": 0,
      "msrp": 0.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "QuickMed Traders",
      "authorized": false,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "QuickMed Traders",
          "date": "2025-02-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Janata Medicos (Unlicensed Kiosk)",
      "last_timestamp": "2025-03-11 14:30:00",
      "avg_price": 15.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Janata Medicos (Unlicensed Kiosk)",
          "location": "Mumbai",
          "time": "2025-03-11 14:30:00",
          "price": 15.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": true,
      "complaints": 1,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V1_PHANTOM_SERIAL",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item code 'MED-NAKALI-002' has NO record in the Manufacturer Product Registry (DB3 / CDSCO-registered products). A genuine medicine unit must be registered by a licensed CDSCO-approved manufacturer. This is an absolute NAKALI indicator.",
        "tier": "HARD_VETO"
      },
      {
        "signal": "V2_MINISTRY_BLACKLIST",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item is on the MCA/CDSCO BLACKLIST. Gazette order: N/A. Blacklisted on: 2025-04-15. Reason: Substandard - API under 30%. Chalk fillers and heavy metal binders.. Risk: Risk of toxicity and organ damage..",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [
      {
        "severity": "high",
        "anomaly_type": "UNLICENSED_VENDOR_SALE",
        "description": "Item sold at unlicensed vendor"
      }
    ],
    "recommendations": [
      "Do NOT purchase. No CDSCO manufacturer registration found.",
      "Item is on MCA/CDSCO BLACKLIST. Report to authorities."
    ]
  },
  "MED-NAKALI-003": {
    "item_code": "MED-NAKALI-003",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 50,
    "lifecycle_state": "UNKNOWN",
    "veto_codes": [
      "V1_PHANTOM_SERIAL",
      "V2_MINISTRY_BLACKLIST"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALI003",
    "product": {
      "found": false,
      "product_name": "UNKNOWN (Not in Manufacturer DB)",
      "generic_name": " - ",
      "mfg_name": " - ",
      "registration_no": " - ",
      "category": " - ",
      "dosage_form": " - ",
      "strength": " - ",
      "batch_number": " - ",
      "mfg_date": " - ",
      "expiry_date": " - ",
      "is_recalled": 0,
      "recall_reason": "",
      "gmp_certified": 0,
      "requires_cold_chain": 0,
      "msrp": 0.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "QuickMed Traders",
      "authorized": false,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "QuickMed Traders",
          "date": "2025-03-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "QuickRelief Kiosk",
      "last_timestamp": "2025-03-12 10:00:00",
      "avg_price": 90.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "QuickRelief Kiosk",
          "location": "New Delhi",
          "time": "2025-03-12 10:00:00",
          "price": 90.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": true,
      "complaints": 1,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V1_PHANTOM_SERIAL",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item code 'MED-NAKALI-003' has NO record in the Manufacturer Product Registry (DB3 / CDSCO-registered products). A genuine medicine unit must be registered by a licensed CDSCO-approved manufacturer. This is an absolute NAKALI indicator.",
        "tier": "HARD_VETO"
      },
      {
        "signal": "V2_MINISTRY_BLACKLIST",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item is on the MCA/CDSCO BLACKLIST. Gazette order: N/A. Blacklisted on: 2025-04-01. Reason: Counterfeit antimalarial with forged licensing credentials.. Risk: Fatal malaria complication risk..",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [
      {
        "severity": "high",
        "anomaly_type": "UNLICENSED_VENDOR_SALE",
        "description": "Item sold at unlicensed vendor"
      }
    ],
    "recommendations": [
      "Do NOT purchase. No CDSCO manufacturer registration found.",
      "Item is on MCA/CDSCO BLACKLIST. Report to authorities."
    ]
  },
  "MED-NAKALI-004": {
    "item_code": "MED-NAKALI-004",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 50,
    "lifecycle_state": "UNKNOWN",
    "veto_codes": [
      "V1_PHANTOM_SERIAL"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALI004",
    "product": {
      "found": false,
      "product_name": "UNKNOWN (Not in Manufacturer DB)",
      "generic_name": " - ",
      "mfg_name": " - ",
      "registration_no": " - ",
      "category": " - ",
      "dosage_form": " - ",
      "strength": " - ",
      "batch_number": " - ",
      "mfg_date": " - ",
      "expiry_date": " - ",
      "is_recalled": 0,
      "recall_reason": "",
      "gmp_certified": 0,
      "requires_cold_chain": 0,
      "msrp": 0.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "QuickMed Traders",
      "authorized": false,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "QuickMed Traders",
          "date": "2025-04-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "QuickRelief Kiosk",
      "last_timestamp": "2025-03-15 15:45:00",
      "avg_price": 40.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "QuickRelief Kiosk",
          "location": "New Delhi",
          "time": "2025-03-15 15:45:00",
          "price": 40.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": false,
      "complaints": 1,
      "open_cases": 1,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V1_PHANTOM_SERIAL",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item code 'MED-NAKALI-004' has NO record in the Manufacturer Product Registry (DB3 / CDSCO-registered products). A genuine medicine unit must be registered by a licensed CDSCO-approved manufacturer. This is an absolute NAKALI indicator.",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [
      {
        "severity": "high",
        "anomaly_type": "UNLICENSED_VENDOR_SALE",
        "description": "Item sold at unlicensed vendor"
      }
    ],
    "recommendations": [
      "Do NOT purchase. No CDSCO manufacturer registration found."
    ]
  },
  "MED-NAKALI-005": {
    "item_code": "MED-NAKALI-005",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 50,
    "lifecycle_state": "UNKNOWN",
    "veto_codes": [
      "V1_PHANTOM_SERIAL"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALI005",
    "product": {
      "found": false,
      "product_name": "UNKNOWN (Not in Manufacturer DB)",
      "generic_name": " - ",
      "mfg_name": " - ",
      "registration_no": " - ",
      "category": " - ",
      "dosage_form": " - ",
      "strength": " - ",
      "batch_number": " - ",
      "mfg_date": " - ",
      "expiry_date": " - ",
      "is_recalled": 0,
      "recall_reason": "",
      "gmp_certified": 0,
      "requires_cold_chain": 0,
      "msrp": 0.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "QuickMed Traders",
      "authorized": false,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "QuickMed Traders",
          "date": "2025-05-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Suburban Chemist Stall",
      "last_timestamp": "2025-03-18 11:00:00",
      "avg_price": 250.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Suburban Chemist Stall",
          "location": "Thane",
          "time": "2025-03-18 11:00:00",
          "price": 250.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": false,
      "complaints": 2,
      "open_cases": 2,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V1_PHANTOM_SERIAL",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item code 'MED-NAKALI-005' has NO record in the Manufacturer Product Registry (DB3 / CDSCO-registered products). A genuine medicine unit must be registered by a licensed CDSCO-approved manufacturer. This is an absolute NAKALI indicator.",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [
      {
        "severity": "high",
        "anomaly_type": "UNLICENSED_VENDOR_SALE",
        "description": "Item sold at unlicensed vendor"
      }
    ],
    "recommendations": [
      "Do NOT purchase. No CDSCO manufacturer registration found."
    ]
  },
  "MED-RECALL-001": {
    "item_code": "MED-RECALL-001",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 90,
    "lifecycle_state": "RECALLED",
    "veto_codes": [
      "V2_MINISTRY_BLACKLIST"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALL001",
    "product": {
      "found": true,
      "product_name": "Coughcure Syrup 100ml [RECALLED]",
      "generic_name": "Dextromethorphan Syrup",
      "mfg_name": "Sun Pharmaceutical Industries Ltd",
      "registration_no": "CDSCO/MFG/011/2018",
      "category": "cough",
      "dosage_form": "syrup",
      "strength": "10mg/5ml",
      "batch_number": "BATCH-R001",
      "mfg_date": "2024-08-01",
      "expiry_date": "2026-07-31",
      "is_recalled": 1,
      "recall_reason": "Diethylene glycol contamination above permissible limit",
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 65.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Apollo Supply Chain Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 1,
      "batches": [
        {
          "distributor": "Apollo Supply Chain Solutions Ltd",
          "date": "2024-09-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Apollo Pharmacy",
      "last_timestamp": "2025-05-20 09:00:00",
      "avg_price": 65.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Apollo Pharmacy",
          "location": "Mumbai",
          "time": "2025-05-20 09:00:00",
          "price": 65.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": true,
      "complaints": 2,
      "open_cases": 1,
      "labs": 1,
      "lab_result": "N/A",
      "alerts": 1,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V2_MINISTRY_BLACKLIST",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item is on the MCA/CDSCO BLACKLIST. Gazette order: N/A. Blacklisted on: 2025-05-25. Reason: Recalled - diethylene glycol solvent contamination.. Risk: Acute kidney injury hazard..",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [
      {
        "severity": "critical",
        "anomaly_type": "TOXIC_CONTAMINATION_RECALL",
        "description": "Diethylene glycol poison recall (DB3 + DB4)"
      }
    ],
    "recommendations": [
      "Diethylene glycol poison recall (DB3 + DB4).",
      "Item is on MCA/CDSCO BLACKLIST. Report to authorities."
    ]
  },
  "MED-RECALL-002": {
    "item_code": "MED-RECALL-002",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 85,
    "lifecycle_state": "RECALLED",
    "veto_codes": [
      "V2_MINISTRY_BLACKLIST"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALL002",
    "product": {
      "found": true,
      "product_name": "Amoxiclav 250mg Suspension [RECALLED]",
      "generic_name": "Amoxycillin+Clavulanate",
      "mfg_name": "Cipla Ltd",
      "registration_no": "CDSCO/MFG/012/2017",
      "category": "antibiotic",
      "dosage_form": "syrup",
      "strength": "250mg/5ml",
      "batch_number": "BATCH-R002",
      "mfg_date": "2024-06-01",
      "expiry_date": "2026-05-31",
      "is_recalled": 1,
      "recall_reason": "Microbial contamination detected in reconstituted oral suspension",
      "gmp_certified": 1,
      "requires_cold_chain": 1,
      "msrp": 55.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "MedPlus Distribution Pvt Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "MedPlus Distribution Pvt Ltd",
          "date": "2024-07-10",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Noble Chemist",
      "last_timestamp": "2025-03-25 14:00:00",
      "avg_price": 55.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Noble Chemist",
          "location": "Mumbai",
          "time": "2025-03-25 14:00:00",
          "price": 55.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": true,
      "complaints": 1,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V2_MINISTRY_BLACKLIST",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item is on the MCA/CDSCO BLACKLIST. Gazette order: N/A. Blacklisted on: 2025-03-15. Reason: Recalled - microbial contamination in pediatric formulation.. Risk: Risk of bacterial septicemia..",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "Item is on MCA/CDSCO BLACKLIST. Report to authorities."
    ]
  },
  "MED-RECALL-003": {
    "item_code": "MED-RECALL-003",
    "verdict": "NAKALI",
    "trust_score": 0,
    "confidence_pct": 85,
    "lifecycle_state": "RECALLED",
    "veto_codes": [
      "V2_MINISTRY_BLACKLIST"
    ],
    "auto_report": true,
    "complaint_id": "MCA-2026-AUTO-ALL003",
    "product": {
      "found": true,
      "product_name": "Metrogyl 400mg [RECALLED]",
      "generic_name": "Metronidazole",
      "mfg_name": "Dr. Reddy's Laboratories Ltd",
      "registration_no": "CDSCO/MFG/013/2019",
      "category": "antiprotozoal",
      "dosage_form": "tablet",
      "strength": "400mg",
      "batch_number": "BATCH-R003",
      "mfg_date": "2024-09-01",
      "expiry_date": "2026-08-31",
      "is_recalled": 1,
      "recall_reason": "Sub-potent active ingredient dissolution failure",
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 45.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "Entero Healthcare Solutions Ltd",
      "authorized": true,
      "cold_chain_ok": true,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "Entero Healthcare Solutions Ltd",
          "date": "2024-10-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Fortis Healthworld Pharmacy",
      "last_timestamp": "2025-06-10 10:30:00",
      "avg_price": 90.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Fortis Healthworld Pharmacy",
          "location": "Gurugram",
          "time": "2025-06-10 10:30:00",
          "price": 90.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": true,
      "complaints": 1,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "V2_MINISTRY_BLACKLIST",
        "value": -100,
        "db_source": "Tier-1 Hard Veto Gate",
        "description": "Item is on the MCA/CDSCO BLACKLIST. Gazette order: N/A. Blacklisted on: 2025-07-20. Reason: Recalled - sub-potent dissolution failure.. Risk: Therapeutic failure..",
        "tier": "HARD_VETO"
      }
    ],
    "anomalies": [],
    "recommendations": [
      "Item is on MCA/CDSCO BLACKLIST. Report to authorities."
    ]
  },
  "MED-UNAUTH-001": {
    "item_code": "MED-UNAUTH-001",
    "verdict": "SUSPICIOUS",
    "trust_score": 55,
    "confidence_pct": 85,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Valium 5mg",
      "generic_name": "Diazepam",
      "mfg_name": "Sun Pharmaceutical Industries Ltd",
      "registration_no": "CDSCO/MFG/014/2020",
      "category": "sedative",
      "dosage_form": "tablet",
      "strength": "5mg",
      "batch_number": "BATCH-U001",
      "mfg_date": "2025-02-01",
      "expiry_date": "2027-01-31",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 48.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "QuickMed Traders",
      "authorized": false,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "QuickMed Traders",
          "date": "2025-03-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "Janata Medicos (Unlicensed Kiosk)",
      "last_timestamp": "2025-04-05 21:00:00",
      "avg_price": 48.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "Janata Medicos (Unlicensed Kiosk)",
          "location": "Mumbai",
          "time": "2025-04-05 21:00:00",
          "price": 48.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": false,
      "complaints": 1,
      "open_cases": 0,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "OPEN_COMPLAINTS",
        "value": -10,
        "db_source": "DB4  -  Ministry of Consumer Affairs",
        "description": "1 active MCA complaint(s). Categories: counterfeit.",
        "tier": "SOFT"
      },
      {
        "signal": "DISTRIBUTOR_UNAUTHORIZED",
        "value": -20,
        "db_source": "DB2  x  DB3",
        "description": "Distributed by UNAUTHORIZED entity: QuickMed Traders. Not on CDSCO-approved list for this manufacturer.",
        "tier": "SOFT"
      },
      {
        "signal": "DISTRIBUTOR_UNLICENSED",
        "value": -15,
        "db_source": "DB2  -  Distributor Ledger",
        "description": "Distributor license expired/revoked. Reason: Unlicensed wholesale broker blacklisted for illegal diversion.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [
      {
        "severity": "high",
        "anomaly_type": "UNLICENSED_VENDOR_SALE",
        "description": "Unlicensed vendor selling Schedule H1 OTC (DB1)"
      }
    ],
    "recommendations": [
      "Unlicensed vendor selling Schedule H1 OTC (DB1).",
      "Unauthorized distributor. Procurement chain is compromised."
    ]
  },
  "MED-UNAUTH-002": {
    "item_code": "MED-UNAUTH-002",
    "verdict": "SUSPICIOUS",
    "trust_score": 55,
    "confidence_pct": 85,
    "lifecycle_state": "DISPENSED",
    "veto_codes": [],
    "auto_report": false,
    "complaint_id": null,
    "product": {
      "found": true,
      "product_name": "Corex Cough Syrup",
      "generic_name": "Codeine phosphate",
      "mfg_name": "Cipla Ltd",
      "registration_no": "CDSCO/MFG/015/2018",
      "category": "analgesic",
      "dosage_form": "syrup",
      "strength": "10mg/5ml",
      "batch_number": "BATCH-U002",
      "mfg_date": "2025-03-01",
      "expiry_date": "2027-02-28",
      "is_recalled": 0,
      "recall_reason": null,
      "gmp_certified": 1,
      "requires_cold_chain": 0,
      "msrp": 52.0
    },
    "distribution": {
      "found": true,
      "count": 1,
      "distributors": "QuickMed Traders",
      "authorized": false,
      "cold_chain_ok": false,
      "status": "delivered",
      "returns": 0,
      "batches": [
        {
          "distributor": "QuickMed Traders",
          "date": "2025-04-01",
          "status": "delivered"
        }
      ]
    },
    "purchase": {
      "found": true,
      "count": 1,
      "vendors": 1,
      "vendor_names": "QuickRelief Kiosk",
      "last_timestamp": "2025-04-10 22:30:00",
      "avg_price": 104.0,
      "anomaly_count": 0,
      "events": [
        {
          "vendor": "QuickRelief Kiosk",
          "location": "New Delhi",
          "time": "2025-04-10 22:30:00",
          "price": 104.0
        }
      ]
    },
    "ministry": {
      "found": true,
      "blacklisted": false,
      "complaints": 1,
      "open_cases": 1,
      "labs": 0,
      "lab_result": "N/A",
      "alerts": 0,
      "reasons": []
    },
    "evidence": [
      {
        "signal": "OPEN_COMPLAINTS",
        "value": -10,
        "db_source": "DB4  -  Ministry of Consumer Affairs",
        "description": "1 active MCA complaint(s). Categories: counterfeit.",
        "tier": "SOFT"
      },
      {
        "signal": "DISTRIBUTOR_UNAUTHORIZED",
        "value": -20,
        "db_source": "DB2  x  DB3",
        "description": "Distributed by UNAUTHORIZED entity: QuickMed Traders. Not on CDSCO-approved list for this manufacturer.",
        "tier": "SOFT"
      },
      {
        "signal": "DISTRIBUTOR_UNLICENSED",
        "value": -15,
        "db_source": "DB2  -  Distributor Ledger",
        "description": "Distributor license expired/revoked. Reason: Unlicensed wholesale broker blacklisted for illegal diversion.",
        "tier": "SOFT"
      }
    ],
    "anomalies": [
      {
        "severity": "high",
        "anomaly_type": "UNLICENSED_VENDOR_SALE",
        "description": "Item sold at unlicensed vendor"
      }
    ],
    "recommendations": [
      " 1 unresolved complaint(s) with MCA.",
      "Unauthorized distributor. Procurement chain is compromised."
    ]
  }
};

// Alias mappings for demo and scenario shortcuts
if (BENCHMARK_DATA["MED-ASALI-002"]) {
  BENCHMARK_DATA["MED-SUSP-001"] = BENCHMARK_DATA["MED-ASALI-002"];
}
if (BENCHMARK_DATA["MED-ASALI-009"]) {
  BENCHMARK_DATA["MED-SUSP-002"] = BENCHMARK_DATA["MED-ASALI-009"];
}

// Human-friendly signal name mapping (No raw uppercase enum constants)
const SIGNAL_MAP = {
  "LAB_TEST_PASSED": "Laboratory safety test",
  "ALL_CHECKS_CLEAN": "Supply chain verification",
  "INSPECTION_RECORD_CLEAN": "Facility audit record",
  "HIGH_REPURCHASE_RATE": "Dispensary sales verification",
  "TEMPERATURE_EXCURSION": "Cold-chain temperature excursion",
  "COLD_CHAIN_BROKEN": "Cold-chain thermal excursion",
  "COLD_CHAIN_VIOLATION": "Cold-chain temperature breach",
  "DISTRIBUTION_ANOMALY": "Logistics custody mismatch",
  "DISTRIBUTOR_UNAUTHORIZED": "Unauthorized distributor",
  "DISTRIBUTOR_UNLICENSED": "Unlicensed distribution entity",
  "SUSPICIOUS_PRICE_DISCOUNT": "Dispensary price anomaly",
  "MULTI_LOCATION_ANOMALY": "Multi-location rapid scan velocity",
  "MULTI_LOCATION_SCAN": "Barcode cloning across retail stores",
  "OPEN_COMPLAINTS": "Consumer ministry complaints",
  "PRODUCT_EXPIRED": "Product shelf-life expired",
  "UNLICENSED_VENDOR_SALE": "Unlicensed vendor OTC sale",
  "V1_ABSENT_FROM_MANUFACTURER_DB": "Barcode absent from manufacturer registry",
  "V1_PHANTOM_SERIAL": "Phantom serial unregistered in DB3",
  "V2_BATCH_RECALLED": "Batch recalled by CDSCO / manufacturer",
  "V2_MINISTRY_BLACKLIST": "Product batch blacklisted by ministry",
  "V3_EXPIRED_PRODUCT": "Product past shelf-life expiry date",
  "V4_COMPLAINT_BLACKLISTED": "Manufacturer blacklisted by ministry",
  "V5_DUPLICATE_DISPENSE": "Duplicate serial barcode dispensed elsewhere",
  "V6_ANOMALOUS_SCAN_VELOCITY": "Velocity anomaly across retail kiosks",
  "TAMPER_EVIDENT_SEAL_FAILED": "Package tamper seal compromise",
  "SERIAL_NUMBER_UNREGISTERED": "Unregistered packaging serial"
};
