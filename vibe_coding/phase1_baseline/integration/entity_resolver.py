#!/usr/bin/env python3
"""
entity_resolver.py
------------------
Multi-Attribute Entity Resolution, Transitive Linkage, and Fuzzy Record Linkage Layer
in Heterogeneous Information Integration & Architecture (IIA).

Implements the Enterprise Identity Resolution & Customer/Product 360 Architecture:
  1. Deterministic Transitive Linkage (Identity Graph):
     Connects disparate data silos via shared bridge keys:
     batch_number <---> product_uid <---> brand_name <---> generic_name <---> packaging_barcode
  2. Probabilistic Record Linkage (Fellegi-Sunter Framework):
     Calculates composite agreement weights using:
     - Levenshtein Edit Distance
     - Jaro-Winkler String Similarity (prefix-boosted edit distance)
     - Soundex Phonetic Encoding (Double Metaphone / phonetic sound buckets)
     - Token-Set / Substring Containment Matching
  3. Master Data Management (MDM) Survivorship:
     Resolves noisy, misspelled, or disjoint queries to canonical Golden Record UIDs.
"""

from __future__ import annotations
import os, re, sqlite3
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASES_DIR = os.path.join(BASE_DIR, "databases")

# Ground Truth Master Catalog of verified benchmark pharmaceutical entities
CANONICAL_PRODUCT_CATALOG: Dict[str, Dict[str, Any]] = {
    "MED-ASALI-001": {
        "product_name": "Novamox 500mg",
        "generic_name": "Amoxycillin",
        "batch_number": "BATCH-A001",
        "manufacturer": "Cipla Ltd",
        "mfg_id": "MFG-001",
        "dist_batches": ["DBATCH-001", "DBATCH-002"]
    },
    "MED-ASALI-002": {
        "product_name": "Pacimol 500mg",
        "generic_name": "Paracetamol",
        "batch_number": "BATCH-A002",
        "manufacturer": "Sun Pharmaceutical Industries Ltd",
        "mfg_id": "MFG-002",
        "dist_batches": ["DBATCH-003"]
    },
    "MED-ASALI-003": {
        "product_name": "Metsmall 850mg",
        "generic_name": "Metformin",
        "batch_number": "BATCH-A003",
        "manufacturer": "Dr. Reddy's Laboratories",
        "mfg_id": "MFG-003",
        "dist_batches": ["DBATCH-004"]
    },
    "MED-ASALI-004": {
        "product_name": "Falcinil 80/480mg",
        "generic_name": "Artemether+Lumefantrine",
        "batch_number": "BATCH-A004",
        "manufacturer": "Sun Pharmaceutical Industries Ltd",
        "mfg_id": "MFG-002",
        "dist_batches": ["DBATCH-005"]
    },
    "MED-ASALI-005": {
        "product_name": "Atorva 40mg",
        "generic_name": "Atorvastatin",
        "batch_number": "BATCH-A005",
        "manufacturer": "Cipla Ltd",
        "mfg_id": "MFG-001",
        "dist_batches": ["DBATCH-006"]
    },
    "MED-ASALI-006": {
        "product_name": "Electral ORS",
        "generic_name": "ORS Formula",
        "batch_number": "BATCH-A006",
        "manufacturer": "Dr. Reddy's Laboratories",
        "mfg_id": "MFG-003",
        "dist_batches": ["DBATCH-007"]
    },
    "MED-ASALI-007": {
        "product_name": "Ciplox 500mg",
        "generic_name": "Ciprofloxacin",
        "batch_number": "BATCH-A007",
        "manufacturer": "Cipla Ltd",
        "mfg_id": "MFG-001",
        "dist_batches": ["DBATCH-008"]
    },
    "MED-ASALI-008": {
        "product_name": "Omez 20mg",
        "generic_name": "Omeprazole",
        "batch_number": "BATCH-A008",
        "manufacturer": "Dr. Reddy's Laboratories",
        "mfg_id": "MFG-003",
        "dist_batches": ["DBATCH-009"]
    },
    "MED-ASALI-009": {
        "product_name": "Basalog 100 IU/ml",
        "generic_name": "Insulin glargine",
        "batch_number": "BATCH-A009",
        "manufacturer": "Biocon Biologics Ltd",
        "mfg_id": "MFG-004",
        "dist_batches": ["DBATCH-010"]
    },
    "MED-ASALI-010": {
        "product_name": "Calcirol 1000 IU",
        "generic_name": "Cholecalciferol",
        "batch_number": "BATCH-A010",
        "manufacturer": "Dr. Reddy's Laboratories",
        "mfg_id": "MFG-003",
        "dist_batches": ["DBATCH-011"]
    },
    "MED-NAKALI-001": {
        "product_name": "Fake Novamox 500mg",
        "generic_name": "Starch powder (Counterfeit)",
        "batch_number": "BATCH-FAKE-01",
        "manufacturer": "Unlicensed Workshop",
        "mfg_id": "UNKNOWN",
        "dist_batches": ["DBATCH-012"]
    },
    "MED-NAKALI-002": {
        "product_name": "Adulterated Pacimol",
        "generic_name": "Sub-potent Paracetamol",
        "batch_number": "BATCH-FAKE-02",
        "manufacturer": "Unlicensed Workshop",
        "mfg_id": "UNKNOWN",
        "dist_batches": ["DBATCH-013"]
    },
    "MED-NAKALI-003": {
        "product_name": "Cloned Metsmall 850mg",
        "generic_name": "Metformin (Counterfeit)",
        "batch_number": "BATCH-FAKE-03",
        "manufacturer": "Unlicensed Workshop",
        "mfg_id": "UNKNOWN",
        "dist_batches": ["DBATCH-014"]
    },
    "MED-NAKALI-004": {
        "product_name": "Substandard Falcinil",
        "generic_name": "Artemether under-dosed",
        "batch_number": "BATCH-FAKE-04",
        "manufacturer": "Unlicensed Workshop",
        "mfg_id": "UNKNOWN",
        "dist_batches": ["DBATCH-015"]
    },
    "MED-NAKALI-005": {
        "product_name": "Counterfeit Atorva",
        "generic_name": "Talcum / Chalk filler",
        "batch_number": "BATCH-FAKE-05",
        "manufacturer": "Unlicensed Workshop",
        "mfg_id": "UNKNOWN",
        "dist_batches": ["DBATCH-016"]
    },
    "MED-RECALL-001": {
        "product_name": "Coughcure Syrup 100ml [RECALLED]",
        "generic_name": "Dextromethorphan Syrup",
        "batch_number": "BATCH-R001",
        "manufacturer": "Sun Pharmaceutical Industries Ltd",
        "mfg_id": "MFG-002",
        "dist_batches": ["DBATCH-017"]
    },
    "MED-RECALL-002": {
        "product_name": "Amoxiclav 250mg Suspension [RECALLED]",
        "generic_name": "Amoxycillin+Clavulanate",
        "batch_number": "BATCH-R002",
        "manufacturer": "Cipla Ltd",
        "mfg_id": "MFG-001",
        "dist_batches": ["DBATCH-018"]
    },
    "MED-RECALL-003": {
        "product_name": "Metrogyl 400mg [RECALLED]",
        "generic_name": "Metronidazole",
        "batch_number": "BATCH-R003",
        "manufacturer": "Dr. Reddy's Laboratories",
        "mfg_id": "MFG-003",
        "dist_batches": ["DBATCH-019"]
    },
    "MED-UNAUTH-001": {
        "product_name": "Valium 5mg",
        "generic_name": "Diazepam",
        "batch_number": "BATCH-U001",
        "manufacturer": "Sun Pharmaceutical Industries Ltd",
        "mfg_id": "MFG-002",
        "dist_batches": ["DBATCH-020"]
    },
    "MED-UNAUTH-002": {
        "product_name": "Corex Cough Syrup",
        "generic_name": "Codeine phosphate",
        "batch_number": "BATCH-U002",
        "manufacturer": "Cipla Ltd",
        "mfg_id": "MFG-001",
        "dist_batches": ["DBATCH-021"]
    }
}

CANONICAL_KNOWN_ITEMS = list(CANONICAL_PRODUCT_CATALOG.keys())


@dataclass
class ResolutionResult:
    """Detailed entity resolution and record linkage telemetry."""
    query_raw: str
    resolved_canonical: str
    confidence_score: float  # 0.0 to 1.0
    is_exact_match: bool
    is_fuzzy_linked: bool
    algorithm_metrics: Dict[str, Any]
    match_explanation: str
    matched_field: str = "item_code"       # "product_uid", "batch_number", "product_name", "generic_name", "ocr_substitution"
    transitive_path: str = ""              # Graph traversal path: e.g. "BATCH-A001 -> MED-ASALI-001 (Novamox 500mg)"
    entity_metadata: Dict[str, Any] = field(default_factory=dict)


class EntityResolver:
    """Multi-Attribute Transitive Identity Resolution and Fuzzy Record Linkage Engine."""

    def __init__(self, catalog: Optional[Dict[str, Dict[str, Any]]] = None):
        self.catalog = dict(catalog or CANONICAL_PRODUCT_CATALOG)
        self.known_keys = list(self.catalog.keys())
        self._load_dynamic_db_records()
        self._build_indexes()

    def _load_dynamic_db_records(self):
        """Dynamically ingests products and batches from SQLite DB3 and DB2 if present."""
        db3_path = os.path.join(DATABASES_DIR, "db3_manufacturer_registry.sqlite")
        if os.path.exists(db3_path):
            try:
                conn = sqlite3.connect(db3_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("""
                    SELECT p.product_uid, p.product_name, p.generic_name, p.batch_number,
                           p.manufacturer_id, m.company_name as mfg_name
                    FROM products p
                    LEFT JOIN manufacturers m ON p.manufacturer_id = m.manufacturer_id
                """)
                for r in cur.fetchall():
                    uid = r["product_uid"]
                    if uid not in self.catalog:
                        self.catalog[uid] = {
                            "product_name": r["product_name"],
                            "generic_name": r["generic_name"],
                            "batch_number": r["batch_number"],
                            "manufacturer": r["mfg_name"] or "",
                            "mfg_id": r["manufacturer_id"] or "",
                            "dist_batches": []
                        }
                    else:
                        # Enrich existing
                        if r["batch_number"]:
                            self.catalog[uid]["batch_number"] = r["batch_number"]
                        if r["product_name"]:
                            self.catalog[uid]["product_name"] = r["product_name"]
                        if r["generic_name"]:
                            self.catalog[uid]["generic_name"] = r["generic_name"]
                conn.close()
            except Exception:
                pass

        # Ingest distributor batches from DB2
        db2_path = os.path.join(DATABASES_DIR, "db2_distributor_ledger.sqlite")
        if os.path.exists(db2_path):
            try:
                conn = sqlite3.connect(db2_path)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT batch_id, batch_serial FROM distribution_batches")
                for r in cur.fetchall():
                    b_id = r["batch_id"]
                    b_serial = r["batch_serial"]
                    if b_serial in self.catalog:
                        if b_id not in self.catalog[b_serial].get("dist_batches", []):
                            self.catalog[b_serial].setdefault("dist_batches", []).append(b_id)
                conn.close()
            except Exception:
                pass

        self.known_keys = list(self.catalog.keys())

    def _build_indexes(self):
        """Constructs inverted indexes for fast transitive graph traversal."""
        self.batch_to_uid: Dict[str, str] = {}
        self.dist_batch_to_uid: Dict[str, str] = {}
        self.name_to_uid: List[Tuple[str, str, str]] = []  # (text, uid, field_type)

        for uid, meta in self.catalog.items():
            # Batch number index
            b_num = (meta.get("batch_number") or "").strip().upper()
            if b_num:
                self.batch_to_uid[b_num] = uid

            # Distributor batch serial index
            for d_b in meta.get("dist_batches", []):
                if d_b:
                    self.dist_batch_to_uid[d_b.strip().upper()] = uid

            # Product trade names and generic active ingredient names
            p_name = meta.get("product_name") or ""
            if p_name:
                self.name_to_uid.append((p_name.strip(), uid, "product_name"))
            g_name = meta.get("generic_name") or ""
            if g_name:
                self.name_to_uid.append((g_name.strip(), uid, "generic_name"))

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Computes minimum edit distance between two strings."""
        if len(s1) < len(s2):
            return EntityResolver.levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    @staticmethod
    def looks_like_identifier(s: str) -> bool:
        """
        True when the input has the shape of a serial or batch code rather than a
        product name: a separator plus at least one digit, e.g. MED-ASALI-001 or
        BATCH-A001. Names such as 'Novamox' or 'Novamax 500mg' return False and
        still go through name matching.
        """
        t = (s or "").upper().strip()
        if not ("-" in t or "_" in t) or any(c.isspace() for c in t):
            return False
        return any(c.isdigit() for c in t) or len([p for p in t.replace("_", "-").split("-") if p]) >= 3

    CONFUSABLE_GLYPHS = str.maketrans({
        "O": "0", "Q": "0", "D": "0",
        "I": "1", "L": "1", "|": "1",
        "S": "5", "B": "8", "Z": "2", "G": "6",
    })

    @staticmethod
    def fold_confusables(s: str) -> str:
        """
        Collapses glyphs a scanner or OCR pass genuinely mixes up onto a single
        representative, so 'MED-ASAL1-OO1' and 'MED-ASALI-001' become the same
        string. Used to tell a misread apart from a different serial.
        """
        return (s or "").upper().replace(" ", "").translate(EntityResolver.CONFUSABLE_GLYPHS)

    @staticmethod
    def jaro_winkler_similarity(s1: str, s2: str, prefix_weight: float = 0.1) -> float:
        """Computes Jaro-Winkler string similarity (1.0 = identical, 0.0 = completely dissimilar)."""
        s1, s2 = s1.upper(), s2.upper()
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        len1, len2 = len(s1), len(s2)
        match_bound = max(len1, len2) // 2 - 1
        if match_bound < 0:
            match_bound = 0

        s1_matches = [False] * len1
        s2_matches = [False] * len2
        matches = 0

        for i in range(len1):
            start = max(0, i - match_bound)
            end = min(i + match_bound + 1, len2)
            for j in range(start, end):
                if s2_matches[j]:
                    continue
                if s1[i] == s2[j]:
                    s1_matches[i] = True
                    s2_matches[j] = True
                    matches += 1
                    break

        if matches == 0:
            return 0.0

        # Transpositions
        k = 0
        transpositions = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        transpositions //= 2

        # Jaro metric
        jaro = (
            (matches / len1) +
            (matches / len2) +
            ((matches - transpositions) / matches)
        ) / 3.0

        # Winkler prefix bonus (up to 4 common initial chars)
        prefix_len = 0
        for c1, c2 in zip(s1[:4], s2[:4]):
            if c1 == c2:
                prefix_len += 1
            else:
                break

        jw = jaro + (prefix_len * prefix_weight * (1.0 - jaro))
        return round(min(jw, 1.0), 4)

    @staticmethod
    def soundex(name: str) -> str:
        """Computes Soundex phonetic encoding for organization/brand names."""
        name = name.upper()
        name = re.sub(r'[^A-Z]', '', name)
        if not name:
            return "0000"

        first_char = name[0]
        mapping = {
            'B': '1', 'F': '1', 'P': '1', 'V': '1',
            'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
            'D': '3', 'T': '3',
            'L': '4',
            'M': '5', 'N': '5',
            'R': '6'
        }

        digits = [first_char]
        prev_code = mapping.get(first_char, '0')

        for char in name[1:]:
            code = mapping.get(char, '0')
            if code != '0':
                if code != prev_code:
                    digits.append(code)
                    prev_code = code
            else:
                prev_code = '0'
            if len(digits) == 4:
                break

        return "".join(digits).ljust(4, '0')

    def resolve_item_code(self, raw_input: str, min_threshold: float = 0.72) -> ResolutionResult:
        """
        Multi-attribute transitive identity resolution engine.
        Handles:
          1. Exact Canonical Product UID match
          2. Transitive Batch Number Linkage (e.g. 'BATCH-A001' -> 'MED-ASALI-001')
          3. Transitive Logistics Batch ID Linkage (e.g. 'DBATCH-001' -> 'MED-ASALI-001')
          4. OCR Delimiter & Alphanumeric Typo Substitutions ('O'->'0', 'l'->'1')
          5. Batch Number Fuzzy / OCR Typo matching
          6. Probabilistic Brand / Generic Name Matching (Jaro-Winkler + Soundex)
          7. Fuzzy Canonical Alphanumeric Sequence Matching
        """
        cleaned = (raw_input or "").strip().upper()
        if not cleaned:
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical="",
                confidence_score=0.0,
                is_exact_match=False,
                is_fuzzy_linked=False,
                algorithm_metrics={},
                match_explanation="Empty query input."
            )

        # ---------------------------------------------------------------------
        # 1. Exact Canonical Product UID Match
        # ---------------------------------------------------------------------
        if cleaned in self.catalog:
            meta = self.catalog[cleaned]
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=cleaned,
                confidence_score=1.0,
                is_exact_match=True,
                is_fuzzy_linked=False,
                algorithm_metrics={"levenshtein": 0, "jaro_winkler": 1.0, "soundex": self.soundex(cleaned)},
                match_explanation=f"Exact canonical key match in Master Registry ({meta.get('product_name')}).",
                matched_field="product_uid",
                transitive_path=cleaned,
                entity_metadata=meta
            )

        # ---------------------------------------------------------------------
        # 2. Deterministic Transitive Batch Number Linkage (Identity Graph)
        # ---------------------------------------------------------------------
        if cleaned in self.batch_to_uid:
            target_uid = self.batch_to_uid[cleaned]
            meta = self.catalog.get(target_uid, {})
            p_name = meta.get("product_name", "Pharmaceutical Product")
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=target_uid,
                confidence_score=1.0,
                is_exact_match=False,
                is_fuzzy_linked=True,
                algorithm_metrics={"levenshtein": 0, "jaro_winkler": 1.0, "graph_hop": 1},
                match_explanation=f"Transitive Identity Linkage: Batch ID '{cleaned}' mapped to canonical '{target_uid}' ({p_name}) via Identity Graph.",
                matched_field="batch_number",
                transitive_path=f"Batch '{cleaned}' ➔ {target_uid} ({p_name})",
                entity_metadata=meta
            )

        # ---------------------------------------------------------------------
        # 3. Transitive Logistics Batch Serial (DB2 ERP) Linkage
        # ---------------------------------------------------------------------
        if cleaned in self.dist_batch_to_uid:
            target_uid = self.dist_batch_to_uid[cleaned]
            meta = self.catalog.get(target_uid, {})
            p_name = meta.get("product_name", "Pharmaceutical Product")
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=target_uid,
                confidence_score=1.0,
                is_exact_match=False,
                is_fuzzy_linked=True,
                algorithm_metrics={"levenshtein": 0, "jaro_winkler": 1.0, "graph_hop": 1},
                match_explanation=f"Transitive Identity Linkage: Logistics ERP Batch ID '{cleaned}' mapped to canonical '{target_uid}' ({p_name}).",
                matched_field="dist_batch_id",
                transitive_path=f"Logistics Batch '{cleaned}' ➔ {target_uid} ({p_name})",
                entity_metadata=meta
            )

        # ---------------------------------------------------------------------
        # 4. OCR Typo Heuristic Substitution ('l'/'I' -> '1', 'O' -> '0', ' ' -> '-')
        # ---------------------------------------------------------------------
        subbed = cleaned.replace(" ", "-").replace("_", "-")
        parts = subbed.split("-")
        if len(parts) >= 3 and len(parts[-1]) == 3:
            sfx = parts[-1].replace("O", "0").replace("L", "1").replace("I", "1")
            subbed = f"{parts[0]}-{parts[1]}-{sfx}"

        if subbed in self.catalog:
            jw = self.jaro_winkler_similarity(cleaned, subbed)
            lev = self.levenshtein_distance(cleaned, subbed)
            meta = self.catalog[subbed]
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=subbed,
                confidence_score=round(jw, 2),
                is_exact_match=False,
                is_fuzzy_linked=True,
                algorithm_metrics={"levenshtein": lev, "jaro_winkler": jw, "heuristic": "OCR_Sub_Fix"},
                match_explanation=f"OCR optical scan typo resolved with Jaro-Winkler score {jw}.",
                matched_field="ocr_substitution",
                transitive_path=f"Raw '{raw_input}' ➔ OCR Corrected '{subbed}'",
                entity_metadata=meta
            )

        # Check if subbed matches a batch number
        if subbed in self.batch_to_uid:
            target_uid = self.batch_to_uid[subbed]
            meta = self.catalog[target_uid]
            jw = self.jaro_winkler_similarity(cleaned, subbed)
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=target_uid,
                confidence_score=round(jw, 2),
                is_exact_match=False,
                is_fuzzy_linked=True,
                algorithm_metrics={"levenshtein": self.levenshtein_distance(cleaned, subbed), "jaro_winkler": jw},
                match_explanation=f"OCR delimiter fix linked Batch '{subbed}' to canonical '{target_uid}'.",
                matched_field="batch_number",
                transitive_path=f"Raw '{raw_input}' ➔ Batch '{subbed}' ➔ {target_uid}",
                entity_metadata=meta
            )

        # ---------------------------------------------------------------------
        # 5. Fuzzy Batch Number Matching (handling typos in batch ID: 'BATCH_A001', 'BATCH-AO01')
        # ---------------------------------------------------------------------
        best_batch_score = 0.0
        best_batch_key = None
        best_batch_lev = 999
        for b_cand, uid in self.batch_to_uid.items():
            jw = self.jaro_winkler_similarity(cleaned, b_cand)
            lev = self.levenshtein_distance(cleaned, b_cand)
            if jw > best_batch_score:
                best_batch_score = jw
                best_batch_key = b_cand
                best_batch_lev = lev

        if best_batch_score >= 0.85 and best_batch_key:
            target_uid = self.batch_to_uid[best_batch_key]
            meta = self.catalog[target_uid]
            p_name = meta.get("product_name", "Pharmaceutical Product")
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=target_uid,
                confidence_score=round(best_batch_score, 2),
                is_exact_match=False,
                is_fuzzy_linked=True,
                algorithm_metrics={"levenshtein": best_batch_lev, "jaro_winkler": best_batch_score, "matched_batch": best_batch_key},
                match_explanation=f"Fuzzy Batch Linkage: Typo in Batch ID matched '{best_batch_key}' (score: {best_batch_score}) ➔ canonical '{target_uid}' ({p_name}).",
                matched_field="batch_number",
                transitive_path=f"Batch '{raw_input}' ➔ '{best_batch_key}' ➔ {target_uid} ({p_name})",
                entity_metadata=meta
            )

        # ---------------------------------------------------------------------
        # 6. Probabilistic Multi-Attribute Matching (Brand Name & Generic Name)
        # ---------------------------------------------------------------------
        # Evaluates Jaro-Winkler, Levenshtein, and Soundex phonetic encoding across trade & generic names
        best_name_score = 0.0
        best_name_entry: Optional[Tuple[str, str, str]] = None  # (name, uid, field_type)
        best_name_lev = 999
        soundex_raw = self.soundex(cleaned.split()[0] if cleaned.split() else cleaned)

        # Only worth doing when the query reads like a name someone typed. Scoring
        # a serial against brand names is a category error, and it was the path by
        # which 'MED-TOTALLY-FAKE-9999' matched a real product and inherited its
        # clean verdict. A serial is matched by the identifier rules below instead.
        for text, uid, f_type in ([] if self.looks_like_identifier(cleaned) else self.name_to_uid):
            # Whole string similarity
            jw_full = self.jaro_winkler_similarity(cleaned, text)

            # Prefix / Brand Token similarity (e.g. "Novamax" vs "Novamox 500mg")
            first_token_text = text.split()[0] if text.split() else text
            first_token_query = cleaned.split()[0] if cleaned.split() else cleaned
            jw_prefix = self.jaro_winkler_similarity(first_token_query, first_token_text)

            # Phonetic match bonus
            soundex_target = self.soundex(first_token_text)
            phonetic_match = (soundex_raw == soundex_target and soundex_raw != "0000")
            phonetic_bonus = 0.05 if phonetic_match else 0.0

            # Substring containment bonus
            containment = (cleaned.lower() in text.lower() or text.lower() in cleaned.lower())
            containment_bonus = 0.08 if containment else 0.0

            composite_score = max(jw_full, jw_prefix) + phonetic_bonus + containment_bonus
            composite_score = min(composite_score, 0.99)

            if composite_score > best_name_score:
                best_name_score = composite_score
                best_name_entry = (text, uid, f_type)
                best_name_lev = self.levenshtein_distance(cleaned, text)

        if best_name_score >= min_threshold and best_name_entry:
            matched_text, target_uid, field_type = best_name_entry
            meta = self.catalog[target_uid]
            field_label = "Brand Trade Name" if field_type == "product_name" else "Generic Active Formula"
            soundex_matched = self.soundex(matched_text.split()[0])
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=target_uid,
                confidence_score=round(best_name_score, 2),
                is_exact_match=False,
                is_fuzzy_linked=True,
                algorithm_metrics={
                    "levenshtein": best_name_lev,
                    "jaro_winkler": round(best_name_score, 3),
                    "soundex_query": soundex_raw,
                    "soundex_target": soundex_matched,
                    "matched_text": matched_text,
                    "field_type": field_type
                },
                match_explanation=f"Probabilistic Record Linkage: Input matched {field_label} '{matched_text}' (score: {best_name_score:.1%}, Soundex: {soundex_matched}) ➔ '{target_uid}'.",
                matched_field=field_type,
                transitive_path=f"'{raw_input}' ➔ {field_label} '{matched_text}' ➔ {target_uid}",
                entity_metadata=meta
            )

        # ---------------------------------------------------------------------
        # 7. Confusion-Aware Matching across Canonical Keys
        # ---------------------------------------------------------------------
        # Serials here are highly structured (MED-XXXXX-NNN), so almost any two
        # of them look similar to Jaro-Winkler. Measured on the real catalogue, a
        # genuine OCR misread scores 0.888 while the invented 'MED-FAKE-0001'
        # scores 0.897 — a similarity threshold cannot separate them, and set low
        # enough to admit the misread it certifies fakes as genuine.
        #
        # What actually distinguishes them is the *kind* of difference. A scanner
        # confuses specific glyph pairs (O/0, I/L/1, S/5, B/8, Z/2). Folding both
        # sides onto one shape turns a genuine misread into an exact match and
        # leaves a fake several edits away.
        #
        # Anything that does not fold to an exact match is left unlinked, which
        # sends it to the phantom-serial veto. Refusing to guess is the only safe
        # default for an anti-counterfeit check: a wrong guess resolves a fake
        # onto a real product and reports that product's clean verdict.
        best_candidate = cleaned
        best_key_score = 0.0
        best_key_lev = 999
        folded_input = self.fold_confusables(cleaned)
        folded_hit = None

        for candidate in self.known_keys:
            jw = self.jaro_winkler_similarity(cleaned, candidate)
            lev = self.levenshtein_distance(cleaned, candidate)
            if jw > best_key_score:
                best_key_score = jw
                best_candidate = candidate
                best_key_lev = lev
            if folded_hit is None and self.fold_confusables(candidate) == folded_input:
                folded_hit = candidate

        if folded_hit is not None:
            best_candidate = folded_hit
            best_key_score = max(best_key_score, self.jaro_winkler_similarity(cleaned, folded_hit))
            best_key_lev = self.levenshtein_distance(cleaned, folded_hit)

        if folded_hit is not None:
            meta = self.catalog.get(best_candidate, {})
            return ResolutionResult(
                query_raw=raw_input,
                resolved_canonical=best_candidate,
                confidence_score=round(best_key_score, 2),
                is_exact_match=False,
                is_fuzzy_linked=True,
                algorithm_metrics={"levenshtein": best_key_lev, "jaro_winkler": best_key_score},
                match_explanation=f"Character-confusion match: input is identical to '{best_candidate}' once scanner-confusable glyphs (O/0, I/L/1, S/5, B/8, Z/2) are folded. Jaro-Winkler on the raw text was {best_key_score:.1%}.",
                matched_field="product_uid",
                transitive_path=f"'{raw_input}' ➔ '{best_candidate}'",
                entity_metadata=meta
            )

        # ---------------------------------------------------------------------
        # 8. Unlinked Raw Key
        # ---------------------------------------------------------------------
        return ResolutionResult(
            query_raw=raw_input,
            resolved_canonical=cleaned,
            confidence_score=round(best_key_score, 2),
            is_exact_match=False,
            is_fuzzy_linked=False,
            algorithm_metrics={"levenshtein": best_key_lev, "jaro_winkler": best_key_score},
            match_explanation="No matching entity above confidence threshold; treating as unlinked raw key.",
            matched_field="unlinked_raw",
            transitive_path="",
            entity_metadata={}
        )


GLOBAL_RESOLVER = EntityResolver()

def resolve_entity(item_code: str) -> ResolutionResult:
    return GLOBAL_RESOLVER.resolve_item_code(item_code)
