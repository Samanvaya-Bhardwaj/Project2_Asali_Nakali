-- DB4: Ministry of Consumer Affairs Report Database
-- Tracks complaints, regulatory blacklists, and forensic lab tests.
-- Integration attribute: complaint_item_ref

PRAGMA foreign_keys = ON;

-- 1. Ministry officers table
CREATE TABLE IF NOT EXISTS ministry_officers (
    officer_id   TEXT PRIMARY KEY,
    full_name    TEXT NOT NULL,
    department   TEXT NOT NULL,
    rank         TEXT,
    email        TEXT UNIQUE,
    phone        TEXT,
    active       INTEGER NOT NULL DEFAULT 1
);

-- 2. Complaints table: reports of suspected fake or substandard items
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id        TEXT PRIMARY KEY,
    complaint_item_ref  TEXT NOT NULL,
    complaint_date      DATETIME NOT NULL DEFAULT (datetime('now')),
    complainant_type    TEXT NOT NULL CHECK(complainant_type IN ('consumer','vendor','manufacturer','ngo','authority','auto_system')),
    complainant_name    TEXT,
    complainant_contact TEXT,
    purchase_location   TEXT,
    complaint_category  TEXT NOT NULL CHECK(complaint_category IN (
                            'counterfeit','substandard','expired','mislabeled',
                            'tampered_packaging','adverse_reaction','price_gouging','other')),
    description         TEXT,
    severity_level      TEXT NOT NULL DEFAULT 'medium'
                        CHECK(severity_level IN ('low','medium','high','critical')),
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK(status IN ('open','under_investigation','lab_testing','resolved','escalated','closed')),
    assigned_officer_id TEXT,
    date_assigned       DATE,
    resolution_date     DATE,
    resolution_notes    TEXT,
    action_taken        TEXT CHECK(action_taken IN (
                            'warning_issued','product_recalled','distributor_suspended',
                            'manufacturer_fined','criminal_referral','case_dismissed','monitoring')),
    auto_generated      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (assigned_officer_id) REFERENCES ministry_officers(officer_id)
);

-- 3. Ministry blacklist: confirmed counterfeit or dangerous items
CREATE TABLE IF NOT EXISTS ministry_blacklist (
    blacklist_id        TEXT PRIMARY KEY,
    item_ref            TEXT NOT NULL UNIQUE,
    complaint_id        TEXT,
    blacklisted_on      DATE NOT NULL,
    blacklisted_by      TEXT NOT NULL,
    reason              TEXT NOT NULL,
    severity            TEXT NOT NULL CHECK(severity IN ('low','medium','high','critical')),
    health_risk         TEXT,
    public_alert_issued INTEGER NOT NULL DEFAULT 0,
    alert_date          DATE,
    active              INTEGER NOT NULL DEFAULT 1,
    removed_on          DATE,
    removal_reason      TEXT,
    FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id)
);

-- 4. Lab reports: forensic analysis of tested items
CREATE TABLE IF NOT EXISTS lab_reports (
    lab_report_id       TEXT PRIMARY KEY,
    complaint_id        TEXT NOT NULL,
    item_ref            TEXT NOT NULL,
    lab_name            TEXT NOT NULL,
    lab_accreditation   TEXT,
    sample_received_on  DATE NOT NULL,
    test_completed_on   DATE,
    parameters_tested   TEXT NOT NULL,
    result              TEXT NOT NULL DEFAULT 'pending'
                        CHECK(result IN ('pass','fail','inconclusive','pending')),
    active_ingredient_match   INTEGER,
    contaminants_found  TEXT,
    findings_summary    TEXT,
    recommendation      TEXT,
    FOREIGN KEY (complaint_id) REFERENCES complaints(complaint_id)
);

-- 5. Public alerts: safety notices issued to consumers
CREATE TABLE IF NOT EXISTS public_alerts (
    alert_id     TEXT PRIMARY KEY,
    item_ref     TEXT NOT NULL,
    issued_on    DATETIME NOT NULL,
    channel      TEXT,
    message      TEXT NOT NULL,
    issued_by    TEXT,
    active       INTEGER NOT NULL DEFAULT 1
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_comp_item_ref  ON complaints(complaint_item_ref);
CREATE INDEX IF NOT EXISTS idx_comp_status    ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_comp_severity  ON complaints(severity_level);
CREATE INDEX IF NOT EXISTS idx_comp_date      ON complaints(complaint_date);
CREATE INDEX IF NOT EXISTS idx_bl_item_ref    ON ministry_blacklist(item_ref);
CREATE INDEX IF NOT EXISTS idx_bl_active      ON ministry_blacklist(active);
CREATE INDEX IF NOT EXISTS idx_lab_item_ref   ON lab_reports(item_ref);
