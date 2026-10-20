"""
Command line for phase 2, so everything on the dashboard can also be shown from a terminal.

    python -m integration.uncertainty match MED-ASAL1-OO7 --vendor VND-005 --price 95 --date "2025-06-02 11:20"
    python -m integration.uncertainty match MED-ASALI-011 --vendor VND-007 --price 30 --channel scan
    python -m integration.uncertainty match --label "N0VAMOX 500MG | B.No. BATCH-A0O1 | EXP 01/2027 | MRP Rs.115.00" --vendor VND-001
    python -m integration.uncertainty compare MED-ASAL1-OO7
    python -m integration.uncertainty reverse MED-ASALI-001
    python -m integration.uncertainty scan [--show 20]
    python -m integration.uncertainty apply
    python -m integration.uncertainty lineage
    python -m integration.uncertainty undo DQ-...
    python -m integration.uncertainty benchmark
"""

from __future__ import annotations
import argparse
import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "integration.uncertainty"


def _match(a):
    from .cleanser import live_matcher
    m = live_matcher()
    rec = {"source": "db1", "key": "cli", "code": a.code or "", "channel": a.channel, "vendor_id": a.vendor,
           "price_paid": a.price, "quantity": a.qty, "date": a.date, "label_text": a.label}
    r = m.match(rec)
    print(f"\n  {r.decision}  best={r.best_uid}  p={r.best_posterior:.4f}  p(no product)={r.p_none:.4f}")
    print(f"  {r.explanation}\n")
    for n in r.notes:
        print(f"  note: {n}")
    print(f"  {'candidate':<16}{'distance':>9}{'weight':>8}{'posterior':>11}  evidence")
    for c in r.candidates:
        ev = ", ".join(f"{k}={v}({c.weights[k]:+.1f})" for k, v in c.features.items())
        print(f"  {c.uid:<16}{c.code_distance:>9.2f}{c.total_weight:>8.1f}{c.posterior:>11.4f}  {ev}")
    print()


def _compare(a):
    from .linkage import compare_algorithms
    for row in compare_algorithms(a.code):
        top = "  ".join(f"{t['uid']} ({t['score']:.3f})" for t in row["top"])
        print(f"  {row['algorithm']:<22} {top}   ties at top: {row['ties_at_top']}")


def _reverse(a):
    from .cleanser import live_matcher
    r = live_matcher().reverse(a.uid)
    if not r.get("found"):
        print(" ", r.get("message"))
        return
    print(f"\n  {r['uid']}  {r['product']['product_name']}  shipped to {', '.join(r['shipped_to'])}")
    print(f"  {r['counts']}\n")
    for x in r["records"]:
        print(f"  {x['db_id']} {x['table']:<20} {str(x['key']):<22} {str(x['stored_code']):<18} "
              f"p={x['posterior']:.3f}  {x['decision']}{'' if x['points_here'] else ' -> ' + str(x['best_uid'])}")


def _scan(a):
    from .cleanser import scan
    r = scan()
    s = r["summary"]
    print(f"\n  {s['total_open']} open: {s['auto']} automatic, {s['review']} review, {s['retain']} quarantine "
          f"({r['elapsed_ms']} ms)")
    for k, v in s["by_category"].items():
        print(f"    {k:<20} {v}")
    print("  accuracy vs ground truth:", json.dumps(r["accuracy_vs_ground_truth"]))
    for i in r["issues"][:a.show]:
        print(f"  [{i['decision']:<6}] {i['category']:<18} {i['db_id']}.{i['table']}#{i['pk_val']} "
              f"{str(i['current'])[:24]!r} -> {str(i['proposed'])[:24]!r}")


def _apply(a):
    from .cleanser import apply
    r = apply("auto")
    print(json.dumps({k: r[k] for k in ("run_id", "issues_applied", "changes_applied", "passes", "by_category")}, indent=1))
    print("  after:", {k: r["after"][k] for k in ("auto", "review", "retain")})


def _undo(a):
    from .cleanser import undo
    print(json.dumps(undo(a.run_id), indent=1))


def _lineage(a):
    from .cleanser import lineage
    for r in lineage()["runs"]:
        print(f"  {r['run_id']}  {r['started_at']}  {r['mode']:<8} issues={r['issues_applied']:<5} "
              f"changes={r['changes_applied']:<5} {'undone ' + r['undone_at'] if r['undone_at'] else 'applied'}")


def _benchmark(a):
    from . import paths
    from .train import print_table
    with open(paths.benchmark_file(), "r", encoding="utf-8") as f:
        print_table(json.load(f))


def main():
    ap = argparse.ArgumentParser(prog="python -m integration.uncertainty", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("match")
    m.add_argument("code", nargs="?")
    m.add_argument("--vendor")
    m.add_argument("--price")
    m.add_argument("--qty", default="1")
    m.add_argument("--date")
    m.add_argument("--label")
    m.add_argument("--channel", default="manual", choices=["manual", "ocr", "scan"])
    m.set_defaults(fn=_match)
    c = sub.add_parser("compare")
    c.add_argument("code")
    c.set_defaults(fn=_compare)
    r = sub.add_parser("reverse")
    r.add_argument("uid")
    r.set_defaults(fn=_reverse)
    s = sub.add_parser("scan")
    s.add_argument("--show", type=int, default=0)
    s.set_defaults(fn=_scan)
    sub.add_parser("apply").set_defaults(fn=_apply)
    u = sub.add_parser("undo")
    u.add_argument("run_id")
    u.set_defaults(fn=_undo)
    sub.add_parser("lineage").set_defaults(fn=_lineage)
    sub.add_parser("benchmark").set_defaults(fn=_benchmark)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
