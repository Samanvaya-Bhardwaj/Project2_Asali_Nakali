"""
paths.py
--------
One place that knows where the live silos and the generated artefacts are.

Every path can be redirected with an environment variable so the test suite can
run against a throwaway copy of the data instead of the demo databases:

  ASALI_DB_DIR          directory holding the *.sqlite silos
  ASALI_NOSQL_FILE      the DB1 JSON document collection
  ASALI_GENERATED_DIR   ground truth, trained model, benchmark results
"""

from __future__ import annotations
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_FILENAMES = {
    "db1": "db1_purchase_registry.sqlite",
    "db2": "db2_distributor_ledger.sqlite",
    "db3": "db3_manufacturer_registry.sqlite",
    "db4": "db4_ministry_reports.sqlite",
    "dq":  "data_quality.sqlite",
}


def db_dir() -> str:
    return os.environ.get("ASALI_DB_DIR") or os.path.join(BASE_DIR, "databases")


def db_path(db_id: str) -> str:
    return os.path.join(db_dir(), DB_FILENAMES[db_id])


def nosql_file() -> str:
    return os.environ.get("ASALI_NOSQL_FILE") or os.path.join(
        BASE_DIR, "data", "nosql_store", "db1_retail_pos.json")


def generated_dir() -> str:
    return os.environ.get("ASALI_GENERATED_DIR") or os.path.join(BASE_DIR, "data", "generated")


def ground_truth_file() -> str:
    return os.path.join(generated_dir(), "ground_truth.json")


def model_file() -> str:
    return os.path.join(generated_dir(), "linkage_model.json")


def benchmark_file() -> str:
    return os.path.join(generated_dir(), "benchmark_results.json")


def stamp(*db_ids: str) -> tuple:
    """Modification times of the given silos. A change means a cache is stale."""
    out = []
    for d in db_ids:
        p = db_path(d)
        try:
            out.append(os.stat(p).st_mtime_ns)
        except OSError:
            out.append(0)
    return tuple(out)
