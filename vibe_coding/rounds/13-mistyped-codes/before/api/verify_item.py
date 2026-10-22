#!/usr/bin/env python3
"""
verify_item.py
--------------
Main verification entry point for the Asali/Nakali Detection System.

Usage:
    python verify_item.py MED-ASALI-001
    python verify_item.py MED-NAKALI-001
    python verify_item.py MED-RECALL-001
    python verify_item.py --report MED-NAKALI-001   (also generate HTML report)
    python verify_item.py --all                      (verify all known items)
    python verify_item.py --audit                    (check audit chain integrity)
    python verify_item.py --stats                    (show system statistics)
"""

from __future__ import annotations
import sys, os, json, argparse
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE)
sys.path.insert(0, BASE)
sys.path.insert(0, PROJECT_ROOT)

from integration.resolver              import resolve
from integration.identifier_normalizer import normalize
from integration.hard_veto_engine      import HardVetoEngine
from integration.lifecycle_state       import get_tracker
from integration.canonical_model       import build_global_view
from integration.trust_engine          import TrustEngine
from integration.anomaly_detector      import AnomalyDetector
from integration.audit_chain           import get_chain
from integration.ministry_reporter     import auto_file_complaint, generate_html_report

# --- ANSI colour helpers ------------------------------------------------------
def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"
def dim(s):    return f"\033[2m{s}\033[0m"

# All known item codes in the demo dataset
ALL_ITEM_CODES = [
    "MED-ASALI-001","MED-ASALI-002","MED-ASALI-003","MED-ASALI-004","MED-ASALI-005",
    "MED-ASALI-006","MED-ASALI-007","MED-ASALI-008","MED-ASALI-009","MED-ASALI-010",
    "MED-NAKALI-001","MED-NAKALI-002","MED-NAKALI-003","MED-NAKALI-004","MED-NAKALI-005",
    "MED-RECALL-001","MED-RECALL-002","MED-RECALL-003",
    "MED-UNAUTH-001","MED-UNAUTH-002",
]


def _yes(v) -> int:
    return 1 if str(v).strip().lower() in ("1", "true", "yes") else 0


def _num(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _dossier(record, result, anomaly_report) -> dict:
    """
    Everything the Check-a-medicine page draws, built from the live records:
    the product, its shipments, its sales, the ministry's file on it, and the
    evidence behind the score. A product registered a minute ago therefore
    shows its own details, not a stored example.
    """
    p = record.manufacturer.product or {}
    mfr = record.manufacturer.manufacturer or {}
    product = {
        "found": record.manufacturer.found,
        "product_uid": p.get("product_uid") or record.item_code,
        "manufacturer_id": p.get("manufacturer_id"),
        "product_name": p.get("product_name") or "Unregistered product",
        "generic_name": p.get("generic_name") or "Unidentified formulation",
        "mfg_name": p.get("mfg_name") or mfr.get("company_name") or "Unregistered manufacturer",
        "registration_no": p.get("registration_no") or "None",
        "category": p.get("category") or "Unknown",
        "dosage_form": p.get("dosage_form") or "Unknown",
        "strength": p.get("strength") or "",
        "batch_number": p.get("batch_number") or "Unrecorded batch",
        "mfg_date": p.get("manufacture_date") or "—",
        "expiry_date": p.get("expiry_date") or "—",
        "is_recalled": _yes(p.get("is_recalled")),
        "recall_reason": p.get("recall_reason"),
        "gmp_certified": _yes(p.get("gmp_certified", mfr.get("gmp_certified"))),
        "requires_cold_chain": _yes(p.get("requires_cold_chain")),
        "msrp": _num(p.get("msrp_kes")),
    }

    batches = record.distribution.batches or []
    names = sorted({str(b.get("dist_name") or b.get("distributor_id")) for b in batches})
    distribution = {
        "found": record.distribution.found,
        "count": len(batches),
        "distributors": ", ".join(names) or "No licensed distributor on record",
        "authorized": bool(batches) and all(_yes(b.get("is_authorized")) for b in batches),
        "cold_chain_ok": bool(batches) and all(_yes(b.get("cold_chain_maintained")) for b in batches),
        "status": batches[0].get("status") if batches else "untracked",
        "returns": len(record.distribution.returns or []),
        "batches": [{"distributor": b.get("dist_name") or b.get("distributor_id"), "date": b.get("dispatch_date"),
                     "status": b.get("status"), "notes": b.get("discrepancy_details") or ""} for b in batches],
    }

    events = record.purchase.events or []
    prices = [_num(e.get("price_paid")) for e in events if e.get("price_paid") not in (None, "")]
    purchase = {
        "found": record.purchase.found,
        "count": len(events),
        "vendors": len({e.get("vendor_id") for e in events}),
        "vendor_names": ", ".join(sorted({str(e.get("vendor_name") or e.get("vendor_id")) for e in events}))
                        or "No dispensary on record",
        "last_timestamp": max((str(e.get("scan_timestamp")) for e in events), default=None),
        "avg_price": round(sum(prices) / len(prices), 2) if prices else 0.0,
        "anomaly_count": sum(_yes(e.get("anomaly_flag")) for e in events),
        "events": [{"vendor": e.get("vendor_name") or e.get("vendor_id"), "location": e.get("location_county"),
                    "time": e.get("scan_timestamp"), "price": _num(e.get("price_paid"))} for e in events],
    }

    m = record.ministry
    labs = m.lab_reports or []
    ministry = {
        "found": m.found,
        "blacklisted": m.blacklist_entry is not None,
        "complaints": len(m.complaints or []),
        "open_cases": sum(1 for c in (m.complaints or []) if str(c.get("status")) not in ("resolved", "closed")),
        "labs": len(labs),
        "lab_result": labs[0].get("result") if labs else "N/A",
        "alerts": len(m.alerts or []),
        "reasons": [m.blacklist_entry.get("reason")] if m.blacklist_entry and m.blacklist_entry.get("reason") else [],
    }

    return {
        "product": product,
        "distribution": distribution,
        "purchase": purchase,
        "ministry": ministry,
        "evidence": [{"signal": e.signal, "value": e.value, "db_source": e.db_source,
                      "description": e.description, "tier": e.tier} for e in result.evidence],
        "anomalies": [{"severity": f.severity, "anomaly_type": f.anomaly_type, "description": f.description}
                      for f in anomaly_report.flags],
        "recommendations": list(result.recommendations or []),
    }


def verify(item_code: str, generate_report: bool = False, silent: bool = False) -> dict:
    """
    Full GAV Pipeline (v2  -  Two-Tier Architecture):
      Tier-0: Identifier Normalization
      Step 1: Cross-DB Resolution (4 DB wrappers)
      Step 2: Canonical Unified View (GlobalItemHistory)
      Step 3: Anomaly Detection
      Tier-1: Hard Veto Engine (deterministic gates)
      Tier-2: Soft Trust Scoring (probabilistic)
      Step 4: Lifecycle State Machine update
      Step 5: Audit Chain logging
      Step 6: Auto-Ministry Report if NAKALI
    """
    # Tier-0: normalize
    norm  = normalize(item_code)
    canon = norm.canonical if norm.valid else item_code.strip().upper()
    was_normalized = norm.was_normalized

    if not silent:
        print(f"\n{'-'*65}")
        print(f"  {cyan('Verifying:')} {bold(canon)}"
              + (f" {dim(f'(normalized from: {repr(item_code)})')}" if was_normalized else ""))
        print(f"{'-'*65}")
        print(f"  {dim('Step 1/6')} Resolving across 4 DBs (GAV wrapper layer) ...")

    # Step 1: Cross-DB resolution
    record = resolve(canon)

    if not silent:
        coverage = sum([record.purchase.found, record.distribution.found,
                        record.manufacturer.found, record.ministry.found])
        print(f"          DB1(scan_code)={record.purchase.found}  "
              f"DB2(batch_serial)={record.distribution.found}  "
              f"DB3(product_uid)={record.manufacturer.found}  "
              f"DB4(complaint_item_ref)={record.ministry.found}  "
              f"[{coverage}/4 DBs]")
        print(f"  {dim('Step 2/6')} Building canonical unified view ...")

    # Step 2: Lifecycle + canonical view
    tracker  = get_tracker()
    lc_state = tracker.infer_and_sync(record)
    gv       = build_global_view(record, lifecycle_state=lc_state,
                                 normalized_from=item_code if was_normalized else None)

    if not silent and gv.contradictions:
        print(f"          {yellow(f' {len(gv.contradictions)} data contradiction(s) detected across DBs')}")
        for c in gv.contradictions:
            print(f"          -> [{c.contradiction_type}] {c.description[:70]}...")
        print(f"  {dim('Step 3/6')} Running anomaly detection ...")
    elif not silent:
        print(f"  {dim('Step 3/6')} Running anomaly detection ...")

    # Step 3: Anomaly detection
    detector      = AnomalyDetector()
    anomaly_report = detector.detect(record)

    if not silent and not anomaly_report.clean:
        print(f"          {yellow(f' {len(anomaly_report.flags)} anomaly flag(s) detected')}")
        print(f"  {dim('Step 4/6')} Running Tier-1 Hard Veto Gates ...")
    elif not silent:
        print(f"  {dim('Step 4/6')} Running Tier-1 Hard Veto Gates ...")

    # Tier-1: Hard veto
    veto_engine = HardVetoEngine()
    veto_result = veto_engine.evaluate(record, lifecycle_state=lc_state)

    if not silent:
        if veto_result.vetoed:
            print(f"          {red('VETOED by: ' + ', '.join(veto_result.veto_codes))}")
        else:
            print(f"          {green('All 5 hard veto gates passed')}")
        print(f"  {dim('Step 5/6')} Calculating Tier-2 soft trust score ...")

    # Tier-2: Soft trust score
    engine = TrustEngine()
    result = engine.calculate(record, veto_result=veto_result, global_view=gv)

    if not silent:
        print(f"  {dim('Step 6/6')} Logging to audit chain ...")

    # Step 5: Audit chain
    chain    = get_chain()
    entry_id = chain.log(
        item_code   = canon,
        verdict     = result.verdict,
        trust_score = result.trust_score,
        db_sources  = ["DB1","DB2","DB3","DB4"],
        querier_id  = "verify_item.py",
    )

    # Step 6: Auto-report if needed
    complaint_id = None
    if result.auto_report:
        if not silent:
            print(f"          {yellow('Auto-drafting MCA complaint dossier ...')}")
        complaint = auto_file_complaint(
            item_code    = canon,
            verdict      = result.verdict,
            trust_score  = result.trust_score,
            evidence_log = result.evidence,
            anomaly_flags= anomaly_report.flags,
        )
        complaint_id = complaint.complaint_id
        if not silent:
            status_txt = "Filed new complaint" if complaint.filed else "Complaint already exists"
            print(f"          {status_txt}: {complaint_id}")
    else:
        if not silent:
            print(f"          No Ministry report needed.")

    # -- Print result -----------------------------------------------------------
    if not silent:
        _print_result(result, anomaly_report, record, entry_id, complaint_id,
                      veto_result=veto_result, global_view=gv)

    # HTML report
    report_path = None
    if generate_report:
        report_path = generate_html_report(
            item_code      = canon,
            verdict        = result.verdict,
            trust_score    = result.trust_score,
            confidence_pct = result.evidence_completeness,
            evidence_log   = result.evidence,
            anomaly_report = anomaly_report,
            item_record    = record,
            complaint_id   = complaint_id,
        )
        if not silent:
            print(f"\n  HTML Report saved: {report_path}")

    return {
        "item_code":          canon,
        "verdict":            result.verdict,
        "trust_score":        result.trust_score,
        "evidence_completeness": result.evidence_completeness,
        "confidence_pct":     result.evidence_completeness,
        "lifecycle_state":    lc_state,
        "veto_codes":         veto_result.veto_codes if veto_result.vetoed else [],
        "contradictions":     len(gv.contradictions),
        "audit_entry":        entry_id,
        "complaint_id":       complaint_id,
        "report_path":        report_path,
        "anomaly_count":      len(anomaly_report.flags),
        "evidence_count":     len(result.evidence),
        "db_coverage":        result.db_coverage,
        "dossier":            _dossier(record, result, anomaly_report),
    }


def _print_result(result, anomaly_report, record, entry_id, complaint_id,
                  veto_result=None, global_view=None):
    """Print the verification result to the terminal."""
    verdicts    = {"ASALI": green, "SUSPICIOUS": yellow, "NAKALI": red}
    colorize    = verdicts.get(result.verdict, lambda x: x)
    status_desc = {"ASALI": "Genuine", "SUSPICIOUS": "Suspicious", "NAKALI": "Counterfeit"}.get(result.verdict, result.verdict)
    bar_filled  = int(result.trust_score / 5)
    bar_empty   = 20 - bar_filled
    bar         = "#" * bar_filled + "-" * bar_empty

    prod  = record.manufacturer.product or {}
    pname = prod.get("product_name", "Unknown product")

    print(f"\n  +{'='*61}+")
    print(f"  |  VERDICT     :  {bold(colorize(result.verdict))} ({status_desc})")
    print(f"  |  PRODUCT     :  {bold(pname)}")
    print(f"  +{'='*61}+")
    print(f"  |  Trust Score :  {colorize(str(result.trust_score))}/100  [{bar}]")
    print(f"  |  Confidence  :  {result.confidence_pct}%")
    print(f"  |  Audit Entry :  {dim(entry_id)}")
    if complaint_id:
        print(f"  |  Ministry Ref:  {yellow(complaint_id)}")
    print(f"  +{'='*61}+")
    print(f"  |  EVIDENCE LOG")
    for ev in result.evidence:
        color = green if ev.value >= 0 else red
        print(f"  |    {color(f'{ev.value:+d}'):<8} {ev.signal}")
    if anomaly_report.flags:
        print(f"  +{'='*61}+")
        print(f"  |  ANOMALIES DETECTED")
        for fl in anomaly_report.flags:
            sev_colors = {"critical": red,"high": red,"medium": yellow,"low": dim}
            sev_fn = sev_colors.get(fl.severity, dim)
            print(f"  |    {sev_fn(fl.severity.upper()+'  '):<18} {fl.anomaly_type}")
    print(f"  +{'='*61}+")
    print(f"  |  RECOMMENDATIONS")
    for rec in result.recommendations:
        print(f"  |    {rec}")
    print(f"  +{'='*61}+\n")


def show_stats():
    """Show system-wide statistics."""
    chain   = get_chain()
    stats   = chain.stats()
    verify  = chain.verify_chain()

    print(f"\n{'='*65}")
    print(f"  {bold('ASALI/NAKALI SYSTEM STATISTICS')}")
    print(f"{'='*65}")
    print(f"  Total Verifications : {stats['total_queries']}")
    print(f"  ASALI  (Genuine)    : {green(str(stats['asali']))}")
    print(f"  SUSPICIOUS          : {yellow(str(stats['suspicious']))}")
    print(f"  NAKALI  (Fake)      : {red(str(stats['nakali']))}")
    print(f"\n  Audit Chain Integrity: {'INTACT' if verify['intact'] else red('COMPROMISED')}")
    print(f"  Entries Checked     : {verify['entries_checked']}")
    print(f"  Last Hash           : {dim(verify.get('last_hash',' - ')[:16]+'...')}")
    print(f"{'='*65}\n")


def check_audit():
    """Verify the audit chain integrity."""
    chain  = get_chain()
    result = chain.verify_chain()
    print(f"\n{'='*65}")
    print(f"  AUDIT CHAIN VERIFICATION")
    print(f"{'='*65}")
    print(f"  Status   : {'INTACT' if result['intact'] else red('TAMPERED')}")
    print(f"  Entries  : {result['entries_checked']}")
    if result.get("broken_at"):
        print(f"  Issues   : {red(str(result['broken_at']))}")
    print(f"{'='*65}\n")


# --- CLI entry point ----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Asali/Nakali Medicine Verification System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python verify_item.py MED-ASALI-001               # Verify a genuine item
  python verify_item.py MED-NAKALI-001               # Verify a fake item
  python verify_item.py --report MED-NAKALI-003      # Generate HTML report
  python verify_item.py --all                        # Verify all items
  python verify_item.py --audit                      # Check audit chain
  python verify_item.py --stats                      # System stats
        """)

    parser.add_argument("item_code", nargs="?",          help="Item code to verify (e.g., MED-ASALI-001)")
    parser.add_argument("--report",  action="store_true", help="Also generate HTML report")
    parser.add_argument("--all",     action="store_true", help="Verify all known item codes")
    parser.add_argument("--audit",   action="store_true", help="Verify audit chain integrity")
    parser.add_argument("--stats",   action="store_true", help="Show system statistics")
    parser.add_argument("--json",    action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    if args.audit:
        check_audit(); return
    if args.stats:
        show_stats(); return
    if args.all:
        print(f"\n  Verifying {len(ALL_ITEM_CODES)} items ...\n")
        results = []
        for code in ALL_ITEM_CODES:
            r = verify(code, generate_report=args.report, silent=True)
            v = r["verdict"]
            colorize = {"ASALI": green, "SUSPICIOUS": yellow, "NAKALI": red}.get(v, lambda x: x)
            tag      = {"ASALI": "PASS", "SUSPICIOUS": "WARN", "NAKALI": "FAIL"}.get(v, "?")
            print(f"  [{tag:4}] {code:<18} {colorize(v):<12} Score: {r['trust_score']:>3}/100  "
                  f"Confidence: {r['confidence_pct']}%")
            results.append(r)
        print()
        show_stats()
        if args.json:
            print(json.dumps(results, indent=2))
        return

    if not args.item_code:
        parser.print_help()
        return

    result = verify(args.item_code, generate_report=args.report)
    if args.json:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
