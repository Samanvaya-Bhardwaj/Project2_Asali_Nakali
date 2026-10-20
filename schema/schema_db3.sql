-- DB3: Manufacturer Product Registry
-- Authoritative catalog of genuine products registered by licensed manufacturers.
-- Integration attribute: product_uid

PRAGMA foreign_keys = ON;

-- 1. Manufacturers table
CREATE TABLE IF NOT EXISTS manufacturers (
    manufacturer_id      TEXT PRIMARY KEY,
    company_name         TEXT NOT NULL,
    country              TEXT NOT NULL DEFAULT 'India',
    physical_address     TEXT,
    license_no           TEXT UNIQUE NOT NULL,
    license_expiry       DATE NOT NULL,
    gmp_certified        INTEGER NOT NULL DEFAULT 1,
    gmp_cert_number      TEXT,
    gmp_cert_expiry      DATE,
    iso_certified        INTEGER NOT NULL DEFAULT 0,
    iso_cert_number      TEXT,
    nairobi_stock_exchange_listed INTEGER DEFAULT 0,
    founded_year         INTEGER,
    ceo_name             TEXT,
    contact_email        TEXT,
    website              TEXT,
    CONSTRAINT chk_mfg_id CHECK (manufacturer_id LIKE 'MFG-%')
);

-- 2. Products table: catalog of registered SKU items
CREATE TABLE IF NOT EXISTS products (
    product_uid          TEXT PRIMARY KEY,
    product_name         TEXT NOT NULL,
    generic_name         TEXT,
    manufacturer_id      TEXT NOT NULL,
    category             TEXT NOT NULL,
    dosage_form          TEXT NOT NULL,
    strength             TEXT NOT NULL,
    pack_size            TEXT,
    manufacture_date     DATE NOT NULL,
    expiry_date          DATE NOT NULL,
    batch_number         TEXT NOT NULL,
    registration_no      TEXT UNIQUE NOT NULL,
    atc_code             TEXT,
    barcode_type         TEXT CHECK(barcode_type IN ('EAN-13','QR','DataMatrix','Code128','GS1-128')),
    storage_temp_min     REAL,
    storage_temp_max     REAL,
    requires_cold_chain  INTEGER NOT NULL DEFAULT 0,
    controlled_substance INTEGER NOT NULL DEFAULT 0,
    is_recalled          INTEGER NOT NULL DEFAULT 0,
    recall_date          DATE,
    recall_reason        TEXT,
    recall_authority     TEXT,
    unit_cost_kes        REAL,
    msrp_kes             REAL,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(manufacturer_id),
    CONSTRAINT chk_dates CHECK (manufacture_date < expiry_date)
);

-- 3. Authorized distributors whitelist
CREATE TABLE IF NOT EXISTS authorized_distributors (
    auth_id          TEXT PRIMARY KEY,
    manufacturer_id  TEXT NOT NULL,
    distributor_ref  TEXT NOT NULL,
    authorized_since DATE NOT NULL,
    authorized_until DATE,
    territory        TEXT,
    product_categories TEXT,
    active           INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(manufacturer_id)
);

-- 4. Batch release certificates: QC verification
CREATE TABLE IF NOT EXISTS batch_release_certs (
    cert_id          TEXT PRIMARY KEY,
    product_uid      TEXT NOT NULL,
    batch_number     TEXT NOT NULL,
    qc_passed        INTEGER NOT NULL,
    release_date     DATE NOT NULL,
    qc_officer       TEXT,
    test_parameters  TEXT,
    certificate_hash TEXT UNIQUE,
    FOREIGN KEY (product_uid) REFERENCES products(product_uid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_prod_uid        ON products(product_uid);
CREATE INDEX IF NOT EXISTS idx_prod_mfg        ON products(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_prod_category   ON products(category);
CREATE INDEX IF NOT EXISTS idx_prod_expiry     ON products(expiry_date);
CREATE INDEX IF NOT EXISTS idx_prod_recalled   ON products(is_recalled);
CREATE INDEX IF NOT EXISTS idx_prod_reg        ON products(registration_no);
