# Asali / Nakali Medicine Verification System
## Project 2: Intelligent, Trustworthy and Decision-Centric Integration from Heterogeneous Data

"Asali" (Hindi/Urdu/Swahili) = Genuine
"Nakali" (Hindi/Urdu/Swahili) = Counterfeit / Fake

---

## 1. Problem Statement

Counterfeit medicine detection requires combining records that reside in independently designed systems:
- Whether the medicine was legitimately manufactured and registered.
- Whether it was transported through authorized, cold-chain compliant distributors.
- Whether the item was scanned or sold at a licensed pharmacy.
- Whether regulatory complaints, lab failures, or recall notices exist.

Each database was designed in isolation by different stakeholders and uses a different column name for the primary item code:
- DB1 (Retail POS): `scan_code`
- DB2 (Distributor ERP): `batch_serial`
- DB3 (Manufacturer Registry): `product_uid`
- DB4 (Ministry of Consumer Affairs): `complaint_item_ref`

---

## 2. Integration Architecture

The system uses a Global-as-View (GAV) mediator architecture with a two-tier hybrid decision engine:

```
                      Raw User Barcode / QR
                                |
                                v
                +-------------------------------+
                |  Tier-0: Normalizer           |
                |  (casing, separators, prefix) |
                +---------------+---------------+
                                |
                                v
                +-------------------------------+
                |  GAV Mediator Layer           |
                |  (schema_mapping.json)        |
                +---------------+---------------+
                                |
        +-----------+-----------+-----------+-----------+
        |           |                       |           |
        v           v                       v           v
    +-------+   +-------+               +-------+   +-------+
    |  DB1  |   |  DB2  |               |  DB3  |   |  DB4  |
    | Retail|   | Dist  |               |  Mfg  |   | Govt  |
    +-------+   +-------+               +-------+   +-------+
        |           |                       |           |
        +-----------+-----------+-----------+-----------+
                                |
                                v
                +-------------------------------+
                |  Canonical Unified View       |
                |  (GlobalItemHistory)          |
                |  - Provenance tags            |
                |  - Cross-DB contradictions    |
                |  - Supply chain event timeline|
                +---------------+---------------+
                                |
                                v
                +-------------------------------+
                |  Tier-1: Hard Veto Gates      |
                |  - V1: Phantom serial         |
                |  - V2: Ministry blacklist     |
                |  - V3: Temporal paradox       |
                |  - V4: Replay / duplicate scan|
                |  - V5: Custody bypass         |
                +---------------+---------------+
                                |
               +----------------+----------------+
               | Any Fail                        | All Pass
               v                                 v
        [COUNTERFEIT]                     +-------------------------------+
        Score = 0                         |  Tier-2: Soft Compliance Score|
        Auto-Draft MCA Report             |  (Starts 100, docks points for|
                                          |   cold chain, MRP, expiry)    |
                                          +---------------+---------------+
                                                          |
                                                          v
                                                  Score >= 80 : ASALI
                                                  Score 50-79 : SUSPICIOUS
                                                  Score < 50  : NAKALI
```

---

## 3. The 4 Heterogeneous Databases

| Database | Owner | Table | Integration Column |
|----------|-------|-------|-------------------|
| DB1: Purchase Registry | Retail Vendor POS | `purchase_events` | `scan_code` |
| DB2: Distributor Ledger | Logistics Distributor | `distribution_batches` | `batch_serial` |
| DB3: Manufacturer Registry | Pharma Manufacturer | `products` | `product_uid` |
| DB4: Ministry Reports | Regulatory Authority | `complaints` | `complaint_item_ref` |

---

## 4. Verification Engine

### Tier-1: Hard Veto Gates (Deterministic)
If any of these 5 gates trigger, the item is immediately marked NAKALI with a score of 0:
1. `V1_PHANTOM_SERIAL`: Item does not exist in the manufacturer catalog (DB3).
2. `V2_MINISTRY_BLACKLIST`: Item is actively listed on the government blacklist (DB4).
3. `V3_TEMPORAL_PARADOX`: Manufacture date is after dispatch or retail purchase date.
4. `V4_REPLAY_SCAN`: Duplicate scans across impossible locations or re-dispensing of consumed units.
5. `V5_CUSTODY_BYPASS`: Selling vendor was never part of the authorized distribution targets.

### Tier-2: Soft Compliance Signals (Weighted)
When all Tier-1 gates pass, the item starts at 100 points:
- Cold chain breach for temperature-sensitive drug: -25
- Unauthorized distributor route: -20
- Supply chain gap (retail event with no distribution record): -20
- Retail price below 40% of MRP (counterfeit dumping indicator): -15
- Unlicensed distributor: -15
- Active consumer complaints with ministry: -10
- Product expired: -10
- All checks clean bonus: +5

### Verdict Thresholds
- `80 - 100`: ASALI (Genuine)
- `50 - 79` : SUSPICIOUS (Quality or custody issue)
- `0 - 49`  : NAKALI (Counterfeit)

---

## 5. Quick Start

### 1. Initialize Databases and Seed Data
```bash
python3 create_databases.py
python3 data/seed_db3.py
python3 data/seed_db2.py
python3 data/seed_db1.py
python3 data/seed_db4.py
```

### 2. Run the Full Integration Demo
```bash
python3 demo.py
```

### 3. Verify Individual Items via CLI
```bash
# Verify a genuine antibiotic
python3 api/verify_item.py MED-ASALI-001

# Verify an item with a broken cold chain
python3 api/verify_item.py MED-ASALI-009

# Verify a counterfeit item (not registered in DB3)
python3 api/verify_item.py MED-NAKALI-001

# Run full batch verification across all items
python3 api/verify_item.py --all

# Check tamper-evident SHA-256 audit chain
python3 api/verify_item.py --audit

# View system statistics
python3 api/verify_item.py --stats
```

### 4. Interactive Web Dashboard
Open `dashboard/index.html` in any web browser.
To start the live backend server:
```bash
python3 demo.py --serve
```

---

## 6. Directory Structure

```
Project2_Asali_Nakali/
|-- api/
|   `-- verify_item.py          # Main CLI entry point
|-- integration/
|   |-- identifier_normalizer.py# Tier-0 input cleaner
|   |-- schema_mapping.json     # GAV ontology bridge
|   |-- resolver.py             # Cross-DB wrapper queries
|   |-- canonical_model.py      # GlobalItemHistory unified view
|   |-- hard_veto_engine.py     # Tier-1 deterministic veto gates
|   |-- lifecycle_state.py      # Digital twin state tracker
|   |-- trust_engine.py         # Tier-2 soft score engine
|   |-- anomaly_detector.py     # Multi-signal anomaly detector
|   |-- audit_chain.py          # SHA-256 tamper-evident log
|   `-- ministry_reporter.py    # Auto-drafts MCA complaints
|-- databases/                  # SQLite database files
|-- schema/                     # SQL DDL schemas (DB1 - DB4)
|-- data/                       # Database seed scripts
|-- dashboard/                  # Web dashboard (HTML, CSS, JS)
|-- reports/                    # Generated verification reports
|-- create_databases.py         # DB initialization script
|-- demo.py                     # Automated demonstration script
`-- README.md                   # System documentation
```
