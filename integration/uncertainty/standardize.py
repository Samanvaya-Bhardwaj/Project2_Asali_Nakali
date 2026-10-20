"""
standardize.py
--------------
Format-level heterogeneity: the same value written differently by different
systems. None of this needs probability. A lower-case code, a date written
day-first, 'Rs.' instead of 'INR' are all deterministic to fix, and fixing them
first means the probabilistic matcher only has to deal with genuine damage.

The one place real ambiguity enters is a date like 03/10/2025, which is either
3 October or 10 March. parse_datetime reports both readings and lets the caller
pick the one the rest of the record agrees with.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional

# -- identifiers ----------------------------------------------------------------

_SEP = re.compile(r"[\s_./\\|]+")
_NON_CODE = re.compile(r"[^A-Z0-9-]")
_MULTI_HYPHEN = re.compile(r"-{2,}")
_COUNTRY_PREFIX = re.compile(r"^(?:IN|IND|CDSCO)-(?=MED)")
_FAMILY_NUMBER = re.compile(r"^([A-Z0-9]*?[A-Z])(\d{2,4})$")


def canonical_code(raw) -> str:
    """
    Canonical MED-FAMILY-NNN form. Removes case, spacing and separator noise and
    re-inserts the separators a scanner or a hurried typist dropped. It never
    changes a character, so it cannot turn one product into another.
    """
    if raw is None:
        return ""
    s = str(raw).strip().upper()
    link = re.search(r"/21/([^/?#\s]+)", s)          # GS1 Digital Link serial
    if link:
        s = link.group(1)
    s = _SEP.sub("-", s)
    s = _NON_CODE.sub("", s)
    s = _MULTI_HYPHEN.sub("-", s).strip("-")
    s = _COUNTRY_PREFIX.sub("", s)
    if s.startswith("MED") and s.count("-") < 2:
        body = s[3:].replace("-", "")
        m = _FAMILY_NUMBER.match(body)
        if m:
            s = f"MED-{m.group(1)}-{m.group(2)}"
        elif body:
            s = f"MED-{body}"
    return s


def looks_like_code(text: str) -> bool:
    return bool(re.search(r"MED[\s\-_.]?[A-Z0-9]{3,}", (text or "").upper()))


def extract_codes(text: str) -> List[str]:
    """Pull anything shaped like a pack code out of free text."""
    found = re.findall(r"MED[\s\-_.]?[A-Z0-9]{3,8}[\s\-_.]?[A-Z0-9]{2,4}", (text or "").upper())
    return [canonical_code(f) for f in found]


# -- dates ----------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


@dataclass
class ParsedDate:
    raw: str
    value: Optional[datetime]
    fmt: str
    has_time: bool = False
    alternatives: List[datetime] = field(default_factory=list)

    @property
    def ambiguous(self) -> bool:
        return bool(self.alternatives)

    def iso(self, with_time: Optional[bool] = None, value: Optional[datetime] = None) -> str:
        v = value or self.value
        if v is None:
            return ""
        keep_time = self.has_time if with_time is None else with_time
        return v.strftime("%Y-%m-%d %H:%M:%S") if keep_time else v.strftime("%Y-%m-%d")


def _safe(y: int, m: int, d: int, hh: int = 0, mm: int = 0, ss: int = 0) -> Optional[datetime]:
    try:
        return datetime(y, m, d, hh, mm, ss)
    except ValueError:
        return None


def _time_parts(t: Optional[str]):
    if not t:
        return 0, 0, 0, False
    parts = [int(p) for p in t.split(":")]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2], True


def parse_datetime(raw) -> ParsedDate:
    s = ("" if raw is None else str(raw)).strip()
    if not s:
        return ParsedDate(s, None, "empty")
    up = s.upper().replace(",", " ")
    up = re.sub(r"\s+", " ", up)

    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T](\d{1,2}:\d{2}(?::\d{2})?))?(?:\.\d+)?$", up)
    if m:
        hh, mi, ss, has_t = _time_parts(m.group(4))
        v = _safe(int(m.group(1)), int(m.group(2)), int(m.group(3)), hh, mi, ss)
        fmt = "iso" if "-" in up[:8] else "ymd_slash"
        return ParsedDate(s, v, fmt, has_t)

    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})(?: (\d{1,2}:\d{2}(?::\d{2})?))?$", up)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mi, ss, has_t = _time_parts(m.group(4))
        dmy = _safe(y, b, a, hh, mi, ss)
        mdy = _safe(y, a, b, hh, mi, ss)
        if dmy and mdy and a != b:
            return ParsedDate(s, dmy, "dd/mm/yyyy (ambiguous)", has_t, [mdy])
        return ParsedDate(s, dmy or mdy, "dd/mm/yyyy" if dmy else "mm/dd/yyyy", has_t)

    m = re.match(r"^(\d{1,2})[ \-]([A-Z]{3})[A-Z]*[ \-](\d{4})(?: (\d{1,2}:\d{2}(?::\d{2})?))?$", up)
    if m and m.group(2) in _MONTHS:
        hh, mi, ss, has_t = _time_parts(m.group(4))
        return ParsedDate(s, _safe(int(m.group(3)), _MONTHS[m.group(2)], int(m.group(1)), hh, mi, ss),
                          "dd-mon-yyyy", has_t)

    m = re.match(r"^([A-Z]{3})[A-Z]* (\d{1,2}) (\d{4})(?: (\d{1,2}:\d{2}(?::\d{2})?))?$", up)
    if m and m.group(1) in _MONTHS:
        hh, mi, ss, has_t = _time_parts(m.group(4))
        return ParsedDate(s, _safe(int(m.group(3)), _MONTHS[m.group(1)], int(m.group(2)), hh, mi, ss),
                          "mon dd yyyy", has_t)

    return ParsedDate(s, None, "unrecognised")


def is_canonical_datetime(raw, with_time: bool) -> bool:
    s = "" if raw is None else str(raw)
    pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$" if with_time else r"^\d{4}-\d{2}-\d{2}$"
    return bool(re.match(pattern, s))


def to_date(raw) -> Optional[datetime]:
    return parse_datetime(raw).value


# -- currency, vendors, licences --------------------------------------------------

_INR_ALIASES = {"", "INR", "RS", "RS.", "RUPEES", "RUPEE", "INDIAN RUPEE", "₹", "INR."}


def normalize_currency(raw) -> str:
    s = ("" if raw is None else str(raw)).strip().upper()
    if s in _INR_ALIASES:
        return "INR"
    return s


def normalize_vendor_id(raw, known: Iterable[str]) -> Optional[str]:
    """'vnd-12', 'VND12', ' VND 012 ' -> 'VND-012' when that vendor exists."""
    s = ("" if raw is None else str(raw)).strip().upper()
    known = set(known)
    if s in known:
        return s
    m = re.match(r"^V\s*N\s*D\s*[-_ ./]?\s*0*(\d{1,4})$", s)
    if not m:
        return None
    cand = f"VND-{int(m.group(1)):03d}"
    return cand if cand in known else None


def license_key(raw) -> str:
    return re.sub(r"[^A-Z0-9]", "", ("" if raw is None else str(raw)).upper())


_NAME_STOP = {"PHARMACY", "PHARMA", "CHEMIST", "CHEMISTS", "MEDICAL", "MEDICALS", "MEDICOS",
              "STORE", "STORES", "LTD", "PVT", "THE", "AND", "HALL", "DISPENSARY", "HOSPITAL"}


def name_tokens(raw) -> List[str]:
    return [t for t in re.findall(r"[A-Z0-9]+", ("" if raw is None else str(raw)).upper())
            if t not in _NAME_STOP and len(t) > 1]


# -- products -------------------------------------------------------------------

def brand_key(product_name) -> str:
    words = re.findall(r"[A-Z]+", ("" if product_name is None else str(product_name)).upper())
    return words[0] if words else ""


def strength_key(raw) -> str:
    s = ("" if raw is None else str(raw)).upper().replace(" ", "")
    return s.replace("MCG", "MCG").replace("UNITS", "IU")


_STRENGTH = re.compile(r"(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\s*(MG|MCG|IU|ML|G)\b")


def find_strength(text) -> str:
    m = _STRENGTH.search(("" if text is None else str(text)).upper())
    return f"{m.group(1)}{m.group(2)}" if m else ""


@dataclass
class LabelReading:
    """What could be read off a photographed pack label."""
    raw: str
    brand: str = ""
    strength: str = ""
    batch: str = ""
    expiry: str = ""          # YYYY-MM
    mrp: Optional[float] = None
    code: str = ""

    def as_dict(self) -> Dict[str, object]:
        return {"brand": self.brand, "strength": self.strength, "batch": self.batch,
                "expiry": self.expiry, "mrp": self.mrp, "code": self.code}

    @property
    def empty(self) -> bool:
        return not (self.brand or self.strength or self.batch or self.expiry or self.mrp or self.code)


def _month_year(text: str) -> str:
    m = re.search(r"(\d{1,2})\s*[/\-.]\s*(\d{2,4})", text)
    if not m:
        return ""
    month, year = int(m.group(1)), int(m.group(2))
    if year < 100:
        year += 2000
    if not 1 <= month <= 12:
        return ""
    return f"{year:04d}-{month:02d}"


def parse_label(text) -> LabelReading:
    """
    Parse OCR text from a pack label. Tolerant of the damage OCR does: segments
    are found by keyword rather than position, and digits read as letters inside
    numeric fields are mapped back before parsing.
    """
    raw = "" if text is None else str(text)
    reading = LabelReading(raw=raw)
    if not raw.strip():
        return reading
    parts = [p.strip() for p in re.split(r"[|\n]", raw) if p.strip()]
    digitize = str.maketrans({"O": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"})
    for i, part in enumerate(parts):
        up = part.upper()
        if re.match(r"^(B\.?\s*NO|BATCH|LOT)", up):
            reading.batch = re.sub(r"^(B\.?\s*NO\.?|BATCH(\s*NO\.?)?|LOT(\s*NO\.?)?)\s*[:.]?\s*", "", up).replace(" ", "")
        elif up.startswith("EXP"):
            reading.expiry = _month_year(re.sub(r"^EXP\w*\.?\s*", "", up).translate(digitize))
        elif up.startswith("MRP"):
            num = re.sub(r"^MRP\.?\s*(RS\.?|INR|₹)?\s*", "", up).translate(digitize)
            m = re.search(r"\d+(?:\.\d+)?", num)
            if m:
                reading.mrp = float(m.group(0))
        elif up.startswith("MF") or up.startswith("MFG") or up.startswith("MFD"):
            continue
        elif i == 0:
            reading.strength = find_strength(up)
            words = re.findall(r"[A-Z0-9]+", up)
            brand_words = [w for w in words if not re.match(r"^\d", w)]
            reading.brand = brand_words[0] if brand_words else ""
        elif looks_like_code(up) and not reading.code:
            reading.code = canonical_code(up)
    if not reading.code:
        codes = extract_codes(raw)
        reading.code = codes[0] if codes else ""
    return reading


def label_text_for(product: Dict[str, object]) -> str:
    """The text a clean label for this registered product would carry."""
    mfg = to_date(product.get("manufacture_date"))
    exp = to_date(product.get("expiry_date"))
    name = str(product.get("product_name") or "")
    strength = str(product.get("strength") or "")
    head = name if strength.replace(" ", "").upper() in name.replace(" ", "").upper() else f"{name} {strength}"
    mrp = product.get("msrp_kes") or 0
    return " | ".join([
        head.upper(),
        str(product.get("generic_name") or ""),
        f"B.No. {product.get('batch_number') or ''}",
        f"MFD {mfg.strftime('%m/%Y') if mfg else ''}",
        f"EXP {exp.strftime('%m/%Y') if exp else ''}",
        f"MRP Rs.{float(mrp):.2f}",
        str(product.get("product_uid") or ""),
    ])
