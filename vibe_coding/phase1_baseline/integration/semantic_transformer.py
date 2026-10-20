#!/usr/bin/env python3
"""
semantic_transformer.py
-----------------------
Semantic Transformation Layer in the Information Integration Pipeline.

Resolves Semantic and Representation Heterogeneity across disparate data sources:
  1. Temperature Scales: Converts Fahrenheit (deg F) and Kelvin (K) to canonical Celsius (deg C)
     for cold-chain integrity evaluation.
  2. Currency Discrepancies: Converts foreign distributor transaction values (USD, Paisa)
     to canonical Indian Rupees (INR).
  3. Heterogeneous DateTime Formats: Normalizes Unix epoch milliseconds, Indian Gazette
     dates (DD/MM/YYYY), ISO-8601 strings, and SQL standard formats into ISO canonical strings.
  4. Boolean & Enum Representation: Normalizes heterogeneous status codes (1/0, "Y"/"N", "ACTIVE").
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class SemanticTransformer:
    """Provides declarative semantic conversion and audit logging."""

    # Approximate fixed exchange rates for demo compliance verification
    USD_TO_INR_RATE = 86.50

    @staticmethod
    def normalize_temperature(temp_val: Any, source_unit: str = "C") -> Dict[str, Any]:
        """
        Converts temperature readings into canonical Celsius (deg C).
        Logs transformation provenance for academic auditability.
        """
        if temp_val is None:
            return {"value_celsius": None, "original": None, "unit": "C", "transformed": False}

        try:
            val = float(temp_val)
        except (ValueError, TypeError):
            return {"value_celsius": None, "original": str(temp_val), "unit": "C", "error": "Unparseable"}

        unit = source_unit.strip().upper() if source_unit else "C"
        celsius = val
        transformed = False

        if unit in ("F", "FAHRENHEIT"):
            celsius = (val - 32.0) * 5.0 / 9.0
            transformed = True
        elif unit in ("K", "KELVIN"):
            celsius = val - 273.15
            transformed = True

        return {
            "value_celsius": round(celsius, 2),
            "original_value": val,
            "original_unit": unit,
            "canonical_unit": "C",
            "transformed": transformed,
            "rule": f"{unit} -> Celsius" if transformed else "Identical"
        }

    @staticmethod
    def normalize_currency(amount: Any, source_currency: str = "INR") -> Dict[str, Any]:
        """
        Converts multi-currency price inputs into canonical Indian Rupees (INR).
        """
        if amount is None:
            return {"amount_inr": 0.0, "original": 0.0, "currency": "INR", "transformed": False}

        try:
            val = float(amount)
        except (ValueError, TypeError):
            return {"amount_inr": 0.0, "original": str(amount), "currency": "INR", "error": "Unparseable"}

        curr = source_currency.strip().upper() if source_currency else "INR"
        inr = val
        transformed = False

        if curr == "USD":
            inr = val * SemanticTransformer.USD_TO_INR_RATE
            transformed = True
        elif curr in ("PAISA", "PAISE"):
            inr = val / 100.0
            transformed = True

        return {
            "amount_inr": round(inr, 2),
            "original_amount": val,
            "original_currency": curr,
            "canonical_currency": "INR",
            "transformed": transformed,
            "rate_applied": SemanticTransformer.USD_TO_INR_RATE if curr == "USD" else 1.0
        }

    @staticmethod
    def parse_heterogeneous_timestamp(raw_ts: Any) -> Dict[str, Any]:
        """
        Parses heterogeneous timestamps:
          - Unix epoch milliseconds: 1746174480000
          - Unix epoch seconds: 1746174480
          - Indian Gazette Date: DD/MM/YYYY or DD-MM-YYYY
          - ISO 8601 string: 2025-05-02T08:28:00Z
          - SQL standard string: 2025-05-02 08:28:00
        Returns ISO-8601 string and parsed datetime.
        """
        if not raw_ts:
            return {"iso_string": None, "datetime": None, "format_detected": "EMPTY", "transformed": False}

        # Check if integer / float epoch timestamp
        if isinstance(raw_ts, (int, float)) or (isinstance(raw_ts, str) and raw_ts.strip().isdigit()):
            num = float(raw_ts)
            # If > 10^11, likely epoch milliseconds
            if num > 1e11:
                dt = datetime.fromtimestamp(num / 1000.0, tz=timezone.utc)
                format_detected = "EPOCH_MILLISECONDS"
            else:
                dt = datetime.fromtimestamp(num, tz=timezone.utc)
                format_detected = "EPOCH_SECONDS"

            return {
                "iso_string": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "datetime": dt,
                "format_detected": format_detected,
                "transformed": True
            }

        s = str(raw_ts).strip()

        # Try ISO 8601
        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y"
        ):
            try:
                dt = datetime.strptime(s, fmt)
                format_name = "INDIAN_GAZETTE" if ("/" in s or "-" in s[:3]) else "ISO_OR_SQL"
                return {
                    "iso_string": dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "datetime": dt,
                    "format_detected": format_name,
                    "transformed": fmt != "%Y-%m-%d %H:%M:%S"
                }
            except ValueError:
                continue

        return {
            "iso_string": s,
            "datetime": None,
            "format_detected": "RAW_PASSTHROUGH",
            "transformed": False
        }


def get_transformer() -> SemanticTransformer:
    return SemanticTransformer()
