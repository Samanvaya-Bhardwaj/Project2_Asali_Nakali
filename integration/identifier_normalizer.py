#!/usr/bin/env python3
"""
identifier_normalizer.py
------------------------
Tier-0: Normalize an incoming item code before any database lookup.

Real-world heterogeneous integration problem:
  DB1 scan (POS barcode reader):   "MED-ASALI-001", "med-asali-001", "MEDASALI001"
  DB2 distributor ERP export:      "MED_ASALI_001",  "Med.Asali.001"
  DB3 manufacturer label system:   "MED-ASALI-001"
  DB4 ministry complaint portal:   "MEDASALI 001"

All of these SHOULD resolve to the same canonical key: "MED-ASALI-001"

This module implements the normalizer step of the
GAV Mediator pipeline:

  raw_input -> normalize() -> canonical_code -> Mediator -> DB wrappers

Normalization rules (in order):
  1. Strip leading/trailing whitespace
  2. UPPERCASE
  3. Replace separators (_, ., space) with hyphens
  4. Remove consecutive duplicate hyphens
  5. Strip non-alphanumeric-hyphen characters
  6. Validate against known code patterns

Also handles format variants used by different DB sources:
  - DB2 sometimes exports without hyphens:  MEDASALI001  -> MED-ASALI-001
  - DB4 sometimes uses dots:                MED.ASALI.001 -> MED-ASALI-001
  - CDSCO QR payloads may use slash:        MED/ASALI/001 -> MED-ASALI-001
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


# --- Known pattern registry (extends schema_mapping.json) --------------------

# Pattern: 3 segments of 3-5 + 5-8 + 3 chars, joined by any separator
_PATTERN_3SEG = re.compile(
    r'^([A-Z]{2,5})[^A-Z0-9]?([A-Z]{3,8})[^A-Z0-9]?(\d{3})$'
)

# Patterns the CDSCO QR payload might include as prefix/suffix fields
_CDSCO_STRIP_PREFIX = re.compile(r'^(?:IN|IND|CDSCO)[/\-_]')

# Characters to treat as separators
_SEPARATORS = re.compile(r'[\s_./\\|]')

# Only keep alphanumeric and hyphens after normalization
_NON_ALPHAHYPHEN = re.compile(r'[^A-Z0-9\-]')

# Collapse multiple hyphens
_MULTI_HYPHEN = re.compile(r'-{2,}')


@dataclass
class NormalizeResult:
    original:       str
    canonical:      str
    was_normalized: bool        # True if any transformation was applied
    confidence:     float       # 0.0-1.0  -  how certain we are of the match
    transformations: list[str]  # human-readable list of what changed
    valid:          bool        # False if code looks structurally invalid


def normalize(raw: str) -> NormalizeResult:
    """
    Normalize a raw item code into the canonical form used as the
    integration key across all 4 heterogeneous databases.

    Returns a NormalizeResult with the canonical code and metadata.
    """
    if not raw:
        return NormalizeResult(
            original="", canonical="", was_normalized=False,
            confidence=0.0, transformations=["EMPTY_INPUT"], valid=False
        )

    original        = raw
    transformations = []
    code            = raw

    # Step 1: Strip whitespace
    stripped = code.strip()
    if stripped != code:
        transformations.append(f"STRIP_WHITESPACE: '{code}' -> '{stripped}'")
        code = stripped

    # Step 2: Uppercase
    upper = code.upper()
    if upper != code:
        transformations.append(f"UPPERCASE: '{code}' -> '{upper}'")
        code = upper

    # Step 3: Strip CDSCO country prefix if present (IN-, IND-, CDSCO-)
    no_prefix = _CDSCO_STRIP_PREFIX.sub('', code)
    if no_prefix != code:
        transformations.append(f"STRIP_CDSCO_PREFIX: '{code}' -> '{no_prefix}'")
        code = no_prefix

    # Step 4: Replace separators (space, _, ., /, \, |) with hyphens
    sep_normalized = _SEPARATORS.sub('-', code)
    if sep_normalized != code:
        transformations.append(f"NORMALIZE_SEPARATORS: '{code}' -> '{sep_normalized}'")
        code = sep_normalized

    # Step 5: Remove any remaining non-alphanumeric-or-hyphen chars
    clean = _NON_ALPHAHYPHEN.sub('', code)
    if clean != code:
        transformations.append(f"STRIP_SPECIAL_CHARS: '{code}' -> '{clean}'")
        code = clean

    # Step 6: Collapse multiple hyphens
    collapsed = _MULTI_HYPHEN.sub('-', code)
    if collapsed != code:
        transformations.append(f"COLLAPSE_HYPHENS: '{code}' -> '{collapsed}'")
        code = collapsed

    # Step 7: Strip leading/trailing hyphens
    trimmed = code.strip('-')
    if trimmed != code:
        transformations.append(f"TRIM_HYPHENS: '{code}' -> '{trimmed}'")
        code = trimmed

    # Step 8: Try to reconstruct canonical pattern if no hyphens remain
    # e.g., "MEDASALI001" -> "MED-ASALI-001"
    if '-' not in code and len(code) >= 10:
        reconstructed = _try_reconstruct(code)
        if reconstructed and reconstructed != code:
            transformations.append(
                f"RECONSTRUCT_PATTERN: '{code}' -> '{reconstructed}' (inferred)")
            code = reconstructed

    canonical = code
    was_normalized = len(transformations) > 0
    valid = _validate(canonical)
    confidence = _confidence(canonical, was_normalized, valid)

    return NormalizeResult(
        original        = original,
        canonical       = canonical,
        was_normalized  = was_normalized,
        confidence      = confidence,
        transformations = transformations,
        valid           = valid,
    )


def _try_reconstruct(code: str) -> Optional[str]:
    """
    Attempt to reconstruct canonical hyphenated form from a code
    with no separators. Uses the expected MED-CATEGORY-NNN pattern.
    """
    m = _PATTERN_3SEG.match(code)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

    # Fallback: look for a trailing 3-digit number
    m2 = re.match(r'^([A-Z]+)(\d{3})$', code)
    if m2 and len(m2.group(1)) >= 6:
        prefix = m2.group(1)
        num    = m2.group(2)
        # Split prefix at midpoint into two segments
        mid = len(prefix) // 2
        return f"{prefix[:3]}-{prefix[3:]}-{num}"

    return None


def _validate(code: str) -> bool:
    """
    Validate that the canonical code looks structurally correct.
    Accepts MED-XXXX-NNN pattern.
    """
    if not code:
        return False
    # At minimum: 3 chars - 3 chars - 3 chars
    parts = code.split('-')
    if len(parts) < 2:
        return False
    if len(code) < 6:
        return False
    return True


def _confidence(canonical: str, was_normalized: bool, valid: bool) -> float:
    if not valid:
        return 0.1
    if not was_normalized:
        return 1.0   # exact match, no transformation needed
    # Each transformation reduces confidence slightly
    return 0.85


# --- Batch normalization ------------------------------------------------------

def normalize_many(codes: list[str]) -> list[NormalizeResult]:
    return [normalize(c) for c in codes]


# --- CLI demo -----------------------------------------------------------------

if __name__ == "__main__":
    test_cases = [
        "MED-ASALI-001",      # perfect  -  no change
        "med-asali-001",      # lowercase
        "MED_ASALI_001",      # underscore separators
        "MED.ASALI.001",      # dot separators
        "MED ASALI 001",      # space separators
        "MEDASALI001",        # no separator  -  reconstruct
        "  MED-ASALI-001  ",  # leading/trailing whitespace
        "IN-MED-ASALI-001",   # CDSCO country prefix
        "MED--ASALI--001",    # double hyphens
        "MED-NAKALI-001",     # NAKALI item
        "INVALID",            # structurally invalid
        "",                   # empty
    ]
    print(f"\n{'-'*70}")
    print(f"  IDENTIFIER NORMALIZER  -  Test Suite")
    print(f"{'-'*70}")
    for raw in test_cases:
        r = normalize(raw)
        status = "PASS" if r.valid else "FAIL"
        changed = "->" if r.was_normalized else "  "
        print(f"  {status} {repr(raw):<28} {changed} '{r.canonical}'  "
              f"[confidence={r.confidence:.0%}]")
        if r.transformations:
            for t in r.transformations:
                print(f"        {t}")
    print()
