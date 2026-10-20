-- DB2: Distributor and Supplier Ledger
-- Tracks shipments from manufacturers to retail vendors.
-- Integration attribute: batch_serial

PRAGMA foreign_keys = ON;

-- 1. Distributors table: companies licensed to transport medicines
CREATE TABLE IF NOT EXISTS distributors (
    distributor_id    TEXT PRIMARY KEY,
    company_name      TEXT NOT NULL,
    license_no        TEXT UNIQUE NOT NULL,
    license_expiry    DATE NOT NULL,
    registration_date DATE NOT NULL,
    region            TEXT NOT NULL,
    hq_address        TEXT,
    contact_person    TEXT,
    contact_phone     TEXT,
    contact_email     TEXT,
    cold_chain_capable INTEGER NOT NULL DEFAULT 0,
    is_authorized     INTEGER NOT NULL DEFAULT 1,
    revocation_reason TEXT,
    CONSTRAINT chk_dist_id CHECK (distributor_id LIKE 'DIST-%')
);

-- 2. Distribution batches: per-item shipment records
CREATE TABLE IF NOT EXISTS distribution_batches (
    batch_id              TEXT PRIMARY KEY,
    batch_serial          TEXT NOT NULL,
    distributor_id        TEXT NOT NULL,
    manufacturer_ref      TEXT NOT NULL,
    source_warehouse      TEXT,
    destination_vendor_id TEXT NOT NULL,
    quantity_shipped      INTEGER NOT NULL CHECK(quantity_shipped > 0),
    quantity_received     INTEGER,
    dispatch_date         DATE NOT NULL,
    expected_arrival_date DATE,
    actual_arrival_date   DATE,
    cold_chain_maintained INTEGER CHECK(cold_chain_maintained IN (0,1)),
    temperature_log_url   TEXT,
    transport_mode        TEXT CHECK(transport_mode IN ('road','air','rail','courier')),
    vehicle_reg           TEXT,
    status                TEXT NOT NULL DEFAULT 'dispatched'
                          CHECK(status IN ('dispatched','in_transit','delivered','returned','lost','damaged')),
    discrepancy_noted     INTEGER NOT NULL DEFAULT 0,
    discrepancy_details   TEXT,
    FOREIGN KEY (distributor_id) REFERENCES distributors(distributor_id)
);

-- 3. Distributor to vendor authorization contracts
CREATE TABLE IF NOT EXISTS distributor_vendor_contracts (
    contract_id    TEXT PRIMARY KEY,
    distributor_id TEXT NOT NULL,
    vendor_id      TEXT NOT NULL,
    contract_start DATE NOT NULL,
    contract_end   DATE,
    product_scope  TEXT,
    active         INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (distributor_id) REFERENCES distributors(distributor_id)
);

-- 4. Returns log: items returned to distributor
CREATE TABLE IF NOT EXISTS return_log (
    return_id       TEXT PRIMARY KEY,
    batch_serial    TEXT NOT NULL,
    returned_by     TEXT NOT NULL,
    return_date     DATE NOT NULL,
    return_reason   TEXT CHECK(return_reason IN ('expired','damaged','excess','suspected_fake','quality_issue')),
    quantity        INTEGER NOT NULL,
    accepted        INTEGER,
    notes           TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_db_batch_serial   ON distribution_batches(batch_serial);
CREATE INDEX IF NOT EXISTS idx_db_distributor    ON distribution_batches(distributor_id);
CREATE INDEX IF NOT EXISTS idx_db_vendor         ON distribution_batches(destination_vendor_id);
CREATE INDEX IF NOT EXISTS idx_db_status         ON distribution_batches(status);
