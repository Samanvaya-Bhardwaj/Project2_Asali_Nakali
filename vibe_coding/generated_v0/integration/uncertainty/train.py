"""
train.py
--------
Fits the linkage model on a training split of labelled records and benchmarks
every candidate algorithm on the held-out split. This is the evidence behind the
choice of algorithm: nothing in the matcher is asserted, it is measured.

Labelled data comes from the generator's ground truth (data/generated/
ground_truth.json): for every generated record it records the true product, or
that the code is counterfeit, and what kind of noise was injected. Clean
records are also re-corrupted through the channel they were captured on, to give
the comparison more noisy cases than the silos alone contain. A record and its
re-corrupted copies always fall on the same side of the split, so nothing about
a test record is seen in training.

    python -m integration.uncertainty.train            fit, evaluate, save
    python -m integration.uncertainty.train --quick    smaller sample, faster
"""

from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "integration.uncertainty"

from . import paths
from .confusion import ConfusionModel
from .context import LiveContext
from .linkage import DEFAULT_MU, FEATURES, LinkageModel, Matcher
from .noise import corrupt, corrupt_for_channel, phonetic
from .similarity import (damerau_osa, edit_similarity, jaro_winkler, levenshtein,
                         qgram_jaccard, soundex_similarity)
from .standardize import canonical_code, extract_codes


def _split(key: str) -> str:
    h = int(hashlib.md5(key.split("#")[0].encode()).hexdigest(), 16)
    return "train" if h % 100 < 50 else "test"


def product_aliases(ctx: LiveContext) -> Dict[str, str]:
    from .cleanser import Scanner
    aliases, _ = Scanner._product_duplicates(Scanner.__new__(Scanner), ctx)
    return aliases


def build_examples(ctx: LiveContext, truth: Dict[str, Dict], augment: int, rng: random.Random):
    """[(key, record, true_uid_or_None, noise_kind, split)]"""
    out = []
    sources = [("db1", "purchase_events", "event_id", ctx.db1_events, Matcher.record_from_db1),
               ("db2", "distribution_batches", "batch_id", ctx.db2_batches, Matcher.record_from_db2),
               ("db4", "complaints", "complaint_id", ctx.db4_complaints, Matcher.record_from_db4)]
    for db_id, table, pk, rows, adapt in sources:
        for row in rows:
            key = f"{db_id}:{table}:{row[pk]}"
            t = truth.get(key)
            if not t:
                continue
            rec = adapt(row)
            true_uid = ctx.resolve_alias(t.get("true_uid")) if t.get("true_uid") else None
            kind = t.get("noise", "clean")
            if not rec.get("code") and db_id != "db4":
                continue
            split = _split(key)
            out.append((key, rec, true_uid, kind, split))
            if augment and kind == "clean" and rec.get("code"):
                channel = rec.get("channel", "manual")
                if channel == "scan":
                    channel = rng.choice(["manual", "ocr"])
                    rec = dict(rec, channel=channel)
                base = true_uid or canonical_code(rec.get("code"))
                for n in range(augment):
                    noisy, k = corrupt_for_channel(base, channel, rng)
                    out.append((f"{key}#aug{n}", dict(rec, code=noisy), true_uid, k, split))
    return out


# -- Fellegi-Sunter estimation -------------------------------------------------

def _candidates(matcher: Matcher, rec) -> Tuple[str, List[str]]:
    code = canonical_code(rec.get("code"))
    if rec.get("source") == "db4" and not code:
        found = extract_codes(rec.get("description"))
        code = found[0] if found else ""
    uids = matcher.ctx.block(code) if code else []
    resolved = matcher.ctx.resolve_alias(code)
    if resolved in matcher.ctx.products and resolved not in uids:
        uids.insert(0, resolved)
    return code, uids


def fit_fs(matcher: Matcher, examples) -> Tuple[Dict, Dict, Dict[str, float], Dict[str, object]]:
    counts_m = defaultdict(lambda: defaultdict(Counter))
    counts_u = defaultdict(lambda: defaultdict(Counter))
    nulls, totals = Counter(), Counter()
    in_block = n_pos = 0
    for key, rec, true_uid, kind, split in examples:
        src = rec["source"]
        totals[src] += 1
        if true_uid is None:
            nulls[src] += 1
        rec = dict(rec)
        from .standardize import parse_label
        rec["_label"] = parse_label(rec.get("label_text")) if rec.get("label_text") else None
        code, uids = _candidates(matcher, rec)
        if true_uid is not None:
            n_pos += 1
            in_block += true_uid in uids
        for uid in uids:
            dist = 0.0 if uid == matcher.ctx.resolve_alias(code) else matcher.distance(code, uid)
            feats = matcher.features(rec, uid, dist)
            target = counts_m if uid == true_uid else counts_u
            for f, v in feats.items():
                target[src][f][v] += 1
    m, u = {}, {}
    for src in FEATURES:
        m[src], u[src] = {}, {}
        for f in FEATURES[src]:
            values = set(counts_m[src][f]) | set(counts_u[src][f])
            if not values:
                continue
            nm, nu = sum(counts_m[src][f].values()), sum(counts_u[src][f].values())
            k = len(values)
            m[src][f] = {v: (counts_m[src][f][v] + 0.5) / (nm + 0.5 * k) for v in values}
            u[src][f] = {v: (counts_u[src][f][v] + 0.5) / (nu + 0.5 * k) for v in values}
    pi0 = {src: max(0.005, nulls[src] / totals[src]) for src in totals}
    stats = {"pairs_complete": round(in_block / n_pos, 4) if n_pos else None}
    return m, u, pi0, stats


def tune_thresholds(results) -> Dict[str, float]:
    """
    Choose the auto-link and no-match thresholds on the training split: as many
    records decided without a person as possible, while auto-links stay at least
    99.5% correct and no-match calls at least 97% correct.
    """
    best, best_cov = {"link": 0.95, "none": 0.90}, -1
    grid = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995]
    for tl in grid:
        for tn in grid:
            linked = [(b, t) for b, bp, pn, t in results if bp >= tl and b is not None]
            nulled = [(b, t) for b, bp, pn, t in results if bp < tl and pn >= tn]
            if linked and sum(b == t for b, t in linked) / len(linked) < 0.995:
                continue
            if nulled and sum(t is None for _, t in nulled) / len(nulled) < 0.97:
                continue
            cov = len(linked) + len(nulled)
            if cov > best_cov:
                best, best_cov = {"link": tl, "none": tn}, cov
    best["alt"] = 0.6
    return best


# -- string-only baselines --------------------------------------------------------

def baseline_metrics(model: LinkageModel) -> Dict[str, Callable[[str, str], float]]:
    return {
        "Levenshtein": lambda a, b: edit_similarity(levenshtein(a, b), a, b),
        "Damerau-Levenshtein": lambda a, b: edit_similarity(damerau_osa(a, b), a, b),
        "Jaro-Winkler": jaro_winkler,
        "Bigram Jaccard": qgram_jaccard,
        "Soundex": soundex_similarity,
        "Learned OCR distance": model.confusion.similarity,
    }


def rank_all(fn, code: str, uids: List[str]) -> List[Tuple[float, str]]:
    return sorted(((fn(code, u), u) for u in uids), key=lambda t: (-t[0], t[1]))


def _f1(p, r):
    return 2 * p * r / (p + r) if p + r else 0.0


def evaluate_string_method(name, fn, train_ex, test_ex, uids, cache):
    def ranked(code):
        k = (name, code)
        if k not in cache:
            cache[k] = rank_all(fn, code, uids)[:10]
        return cache[k]

    def decisions(examples):
        rows = []
        for key, rec, truth, kind, split in examples:
            code = canonical_code(rec.get("code"))
            if not code:
                continue
            r = ranked(code)
            ties = sum(1 for s, _ in r if s == r[0][0]) if r else 0
            rows.append((r, truth, kind, ties))
        return rows

    tr, te = decisions(train_ex), decisions(test_ex)
    best_t, best_f = 0.5, -1
    for t in [x / 100 for x in range(40, 100, 2)]:
        tp = sum(1 for r, truth, _, _ in tr if r and r[0][0] >= t and r[0][1] == truth)
        fp = sum(1 for r, truth, _, _ in tr if r and r[0][0] >= t and r[0][1] != truth)
        pos = sum(1 for _, truth, _, _ in tr if truth is not None)
        p = tp / (tp + fp) if tp + fp else 0
        rc = tp / pos if pos else 0
        if _f1(p, rc) > best_f:
            best_t, best_f = t, _f1(p, rc)
    return summarise(name, te, best_t)


def summarise(name, rows, threshold, family="string similarity on the code"):
    pos = [(r, t, k, ties) for r, t, k, ties in rows if t is not None]
    neg = [(r, t, k, ties) for r, t, k, ties in rows if t is None]
    noisy = [x for x in pos if x[2] not in ("clean",)]
    top1 = sum(1 for r, t, _, _ in pos if r and r[0][1] == t)
    top1_noisy = sum(1 for r, t, _, _ in noisy if r and r[0][1] == t)
    r5 = sum(1 for r, t, _, _ in pos if t in [u for _, u in r[:5]])
    mrr = sum(next((1 / (i + 1) for i, (_, u) in enumerate(r) if u == t), 0) for r, t, _, _ in pos)
    tp = sum(1 for r, t, _, _ in pos if r and r[0][0] >= threshold and r[0][1] == t)
    fp_wrong = sum(1 for r, t, _, _ in pos if r and r[0][0] >= threshold and r[0][1] != t)
    fp_fake = sum(1 for r, t, _, _ in neg if r and r[0][0] >= threshold)
    prec = tp / (tp + fp_wrong + fp_fake) if tp + fp_wrong + fp_fake else 0
    rec = tp / len(pos) if pos else 0
    by_kind = defaultdict(lambda: [0, 0])
    for r, t, k, _ in pos:
        by_kind[k][1] += 1
        by_kind[k][0] += bool(r and r[0][1] == t)
    ties = sum(1 for r, t, _, tie in pos if tie > 1)
    return {"name": name, "family": family, "threshold": threshold,
            "n_pos": len(pos), "n_noisy": len(noisy), "n_neg": len(neg),
            "top1": round(top1 / len(pos), 4) if pos else None,
            "top1_noisy": round(top1_noisy / len(noisy), 4) if noisy else None,
            "recall_at_5": round(r5 / len(pos), 4) if pos else None,
            "mrr": round(mrr / len(pos), 4) if pos else None,
            "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(_f1(prec, rec), 4),
            "false_link_rate_fakes": round(fp_fake / len(neg), 4) if neg else None,
            "tied_top1_rate": round(ties / len(pos), 4) if pos else None,
            "by_kind": {k: round(c / n, 4) for k, (c, n) in sorted(by_kind.items())}}


# -- the full model ---------------------------------------------------------------

def run_model(matcher: Matcher, examples, strip_context: bool = False):
    rows = []
    for key, rec, truth, kind, split in examples:
        r = dict(rec)
        if strip_context:
            r = {k: r.get(k) for k in ("source", "table", "key", "code", "channel", "description")}
            r["description"] = None
        res = matcher.match(r, limit=10)
        ranked = [(c.posterior, c.uid) for c in res.candidates]
        rows.append((res, ranked, truth, kind))
    return rows


def summarise_fs(name, rows, family):
    as_ranked = [(ranked, truth, kind, 1) for res, ranked, truth, kind in rows]
    base = summarise(name, as_ranked, threshold=2.0, family=family)   # top-1 / recall@5 / MRR only
    pos = [x for x in rows if x[2] is not None]
    neg = [x for x in rows if x[2] is None]
    linked = [(res, t) for res, _, t, _ in rows if res.decision in ("EXACT", "AUTO_LINK")]
    correct_links = sum(1 for res, t in linked if res.best_uid == t)
    review = [(res, t) for res, _, t, _ in rows if res.decision in ("REVIEW", "VALID_BUT_WRONG")]
    nomatch = [(res, t) for res, _, t, _ in rows if res.decision == "NO_MATCH"]
    fake_linked = sum(1 for res, t in linked if t is None)
    prec = correct_links / len(linked) if linked else 0
    rec = correct_links / len(pos) if pos else 0
    base.update({
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(_f1(prec, rec), 4),
        "false_link_rate_fakes": round(fake_linked / len(neg), 4) if neg else None,
        "review_rate": round(len(review) / len(rows), 4) if rows else None,
        "review_top1_correct": round(sum(1 for res, t in review if res.best_uid == t) / len(review), 4) if review else None,
        "no_match_precision": round(sum(1 for _, t in nomatch if t is None) / len(nomatch), 4) if nomatch else None,
        "fakes_caught": round(sum(1 for res, _, t, _ in rows if t is None and res.decision == "NO_MATCH") / len(neg), 4) if neg else None,
        "threshold": None, "tied_top1_rate": None,
    })
    return base


# -- names ------------------------------------------------------------------------

def name_benchmark(brands: List[str], rng: random.Random, per_kind: int = 120) -> Dict[str, object]:
    kinds = ["keyboard", "transpose", "delete", "insert", "phonetic", "ocr"]
    methods = {
        "Levenshtein": lambda a, b: edit_similarity(levenshtein(a, b), a, b),
        "Damerau-Levenshtein": lambda a, b: edit_similarity(damerau_osa(a, b), a, b),
        "Jaro-Winkler": jaro_winkler,
        "Bigram Jaccard": qgram_jaccard,
        "Soundex": soundex_similarity,
        "Jaro-Winkler + Soundex": lambda a, b: 0.85 * jaro_winkler(a, b) + 0.15 * soundex_similarity(a, b),
    }
    queries = []
    for kind in kinds:
        for _ in range(per_kind):
            b = rng.choice(brands)
            noisy = phonetic(b, rng) if kind == "phonetic" else corrupt(b, kind, rng)
            if noisy.upper() != b:
                queries.append((noisy.upper(), b, kind))
    results = []
    for name, fn in methods.items():
        hits = Counter()
        totals = Counter()
        for q, truth, kind in queries:
            best = max(brands, key=lambda c: (fn(q, c), c))
            totals[kind] += 1
            hits[kind] += best == truth
        results.append({"name": name, "top1": round(sum(hits.values()) / max(1, sum(totals.values())), 4),
                        "by_kind": {k: round(hits[k] / totals[k], 4) for k in kinds if totals[k]}})
    return {"n_queries": len(queries), "n_brands": len(brands), "methods": results}


# -- orchestration ------------------------------------------------------------------

def run(quick: bool = False, seed: int = 7) -> Dict[str, object]:
    t0 = time.perf_counter()
    rng = random.Random(seed)
    try:
        with open(paths.ground_truth_file(), "r", encoding="utf-8") as f:
            truth = json.load(f)["records"]
    except (OSError, ValueError, KeyError):
        raise SystemExit("No ground truth found. Run data/generate_uncertain_data.py first.")

    base_ctx = LiveContext()
    aliases = product_aliases(base_ctx)
    ctx = LiveContext(aliases)
    examples = build_examples(ctx, truth, augment=1 if quick else 2, rng=rng)
    train_ex = [e for e in examples if e[4] == "train"]
    test_ex = [e for e in examples if e[4] == "test"]
    print(f"  examples: {len(examples)} (train {len(train_ex)}, test {len(test_ex)})")

    # 1. noisy-channel substitution costs from training pairs only
    pairs = [(canonical_code(rec.get("code")), t) for _, rec, t, k, _ in train_ex
             if t is not None and k not in ("clean", "format")]
    confusion = ConfusionModel.fit(pairs)
    print(f"  confusion model: {confusion.source}")

    # 2. Fellegi-Sunter m/u, prior of 'no registered product'
    seed_model = LinkageModel(confusion=confusion)
    seed_matcher = Matcher(ctx, seed_model)
    ctx.complete_custody(seed_matcher)
    m, u, pi0, block_stats = fit_fs(seed_matcher, train_ex)
    model = LinkageModel(confusion, m, u, pi0)

    # 3. thresholds tuned on training decisions
    tm = Matcher(ctx, model)
    train_rows = run_model(tm, train_ex)
    model.thresholds = tune_thresholds([(res.candidates[0].uid if res.candidates else None,
                                         res.candidates[0].posterior if res.candidates else 0.0,
                                         res.p_none, t) for res, _, t, _ in train_rows])
    print(f"  thresholds: {model.thresholds}")

    # 4. evaluation on the held-out split
    final = Matcher(ctx, model)
    test_rows = run_model(final, test_ex)
    code_only = Matcher(ctx, model)
    code_rows = run_model(code_only, test_ex, strip_context=True)

    uids = sorted(ctx.products)
    sample_train = train_ex if not quick else train_ex[:400]
    cache: Dict = {}
    methods = []
    for name, fn in baseline_metrics(model).items():
        t1 = time.perf_counter()
        methods.append(evaluate_string_method(name, fn, sample_train[:600], test_ex, uids, cache))
        print(f"  {name:<22} top-1 {methods[-1]['top1']}  ({time.perf_counter() - t1:.1f}s)")
    methods.append(summarise_fs("Fellegi-Sunter, code only", code_rows,
                                "probabilistic linkage, learned code distance, no context"))
    methods.append(summarise_fs("Fellegi-Sunter + context (chosen)", test_rows,
                                "probabilistic linkage, learned code distance + custody, price, dates, label"))

    block_sizes = []
    in_block = n_pos = 0
    for _, rec, t, _, _ in test_ex:
        code, cands = _candidates(final, dict(rec))
        block_sizes.append(len(cands))
        if t is not None:
            n_pos += 1
            in_block += t in cands
    weights = {src: {f: {v: round(math.log2(m[src][f][v] / u[src][f][v]), 2) for v in m[src][f]}
                     for f in m[src]} for src in m}
    positives = sum(1 for e in test_ex if e[2] is not None)
    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "dataset": {"catalogue_size": len(uids), "train": len(train_ex), "test": len(test_ex),
                    "test_positives": positives, "test_counterfeits": len(test_ex) - positives,
                    "test_by_kind": dict(Counter(k for _, _, t, k, _ in test_ex if t is not None)),
                    "test_by_source": dict(Counter(rec["source"] for _, rec, _, _, _ in test_ex))},
        "blocking": {"method": "inverted index on confusion-folded character bigrams",
                     "pairs_completeness": round(in_block / n_pos, 4) if n_pos else None,
                     "mean_block_size": round(sum(block_sizes) / len(block_sizes), 1) if block_sizes else 0,
                     "reduction_ratio": round(1 - (sum(block_sizes) / len(block_sizes)) / len(uids), 4) if block_sizes else 0,
                     "train_pairs_completeness": block_stats.get("pairs_complete")},
        "methods": methods,
        "thresholds": model.thresholds,
        "pi0": {k: round(v, 4) for k, v in pi0.items()},
        "confusions": confusion.top_confusions(18),
        "weights": weights,
        "names": name_benchmark(sorted(ctx.brands), random.Random(seed + 1)),
    }
    model.meta = {"trained_at": result["generated_at"], "train_examples": len(train_ex),
                  "source": "fitted by integration/uncertainty/train.py"}
    model.save()
    os.makedirs(os.path.dirname(paths.benchmark_file()), exist_ok=True)
    with open(paths.benchmark_file(), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(f"  saved model -> {paths.model_file()}")
    print(f"  saved benchmark -> {paths.benchmark_file()}  ({result['elapsed_s']} s)")
    return result


def print_table(result: Dict[str, object]) -> None:
    print()
    print(f"  {'method':<36}{'top-1':>7}{'noisy':>7}{'R@5':>7}{'prec':>7}{'recall':>7}{'F1':>7}{'fake→real':>10}")
    for m in result["methods"]:
        fl = m.get("false_link_rate_fakes")
        print(f"  {m['name']:<36}{m['top1'] or 0:>7.3f}{m['top1_noisy'] or 0:>7.3f}{m['recall_at_5'] or 0:>7.3f}"
              f"{m['precision']:>7.3f}{m['recall']:>7.3f}{m['f1']:>7.3f}{(fl if fl is not None else 0):>10.3f}")


def main():
    ap = argparse.ArgumentParser(description="Fit and benchmark the linkage model")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    print_table(run(quick=args.quick))


if __name__ == "__main__":
    main()
