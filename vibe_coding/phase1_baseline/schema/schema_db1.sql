-- DB1: Purchase and Scan Registry
-- Records scan and purchase events at point of sale.
-- Integration attribute: scan_code

PRAGMA foreign_keys = ON;

-- 1. Vendors table: stores retail vendor details
CREATE TABLE IF NOT EXISTS vendors (
    vendor_id        TEXT PRIMARY KEY,
    vendor_name      TEXT NOT NULL,
    vendor_type      TEXT CHECK(vendor_type IN ('pharmacy','supermarket','clinic','hospital','kiosk')),
    location_county  TEXT NOT NULL,
    location_street  TEXT,
    license_no       TEXT UNIQUE,
    license_expiry   DATE,
    phone            TEXT,
    email            TEXT,
    active           INTEGER NOT NULL DEFAULT 1,
    registered_on    DATE NOT NULL,
    CONSTRAINT chk_vendor_id CHECK (vendor_id LIKE 'VND-%')
);

-- 2. Purchase events table: point of sale scans
CREATE TABLE IF NOT EXISTS purchase_events (
    event_id         TEXT PRIMARY KEY,
    scan_code        TEXT NOT NULL,
    scan_timestamp   DATETIME NOT NULL DEFAULT (datetime('now')),
    vendor_id        TEXT NOT NULL,
    customer_age_group TEXT CHECK(customer_age_group IN ('child','youth','adult','senior')),
    quantity_bought  INTEGER NOT NULL DEFAULT 1,
    price_paid       REAL NOT NULL CHECK(price_paid >= 0),
    currency         TEXT NOT NULL DEFAULT 'INR',
    payment_method   TEXT CHECK(payment_method IN ('cash','upi','card','insurance','mpesa')),
    scan_method      TEXT CHECK(scan_method IN ('barcode','qrcode','manual','nfc')),
    device_id        TEXT,
    anomaly_flag     INTEGER NOT NULL DEFAULT 0,
    anomaly_reason   TEXT,
    notes            TEXT,
    FOREIGN KEY (vendor_id) REFERENCES vendors(vendor_id)
);

-- 3. Scan anomaly log: duplicate or impossible scan patterns
CREATE TABLE IF NOT EXISTS scan_anomaly_log (
    anomaly_id       TEXT PRIMARY KEY,
    scan_code        TEXT NOT NULL,
    detected_on      DATETIME NOT NULL DEFAULT (datetime('now')),
    anomaly_type     TEXT CHECK(anomaly_type IN ('multi_location','expired_scan','rapid_rescan','unregistered_vendor')),
    vendor_ids       TEXT,
    description      TEXT,
    resolved         INTEGER NOT NULL DEFAULT 0
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pe_scan_code   ON purchase_events(scan_code);
CREATE INDEX IF NOT EXISTS idx_pe_vendor_id   ON purchase_events(vendor_id);
CREATE INDEX IF NOT EXISTS idx_pe_timestamp   ON purchase_events(scan_timestamp);
CREATE INDEX IF NOT EXISTS idx_pe_anomaly     ON purchase_events(anomaly_flag);
