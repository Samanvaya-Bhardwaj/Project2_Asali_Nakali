"""
confusion.py
------------
A noisy-channel edit distance for printed codes.

Plain Levenshtein charges the same for reading 'O' as '0' as for reading 'O' as
'X'. For a code read off a pack by a camera that is wrong: the first is the most
common failure of optical reading, the second almost never happens. Charging them
equally is what lets a counterfeit serial two random edits away look as close as a
genuine serial with two smudged glyphs.

This model is a weighted optimal-string-alignment distance:

  substitution   cost(true -> observed), learned from training pairs; a pair
                 that accounts for most substitutions of a character becomes cheap
  transposition  fixed, 0.6 (a finger slip, cheaper than two substitutions)
  separator      0.1 to insert or drop a hyphen
  doubled key    0.5 to insert a copy of the previous character
  other indel    1.0

Before any training data exists it starts from a prior built from glyph-shape
classes, so it is usable on day one and improves once labelled pairs are seen.
"""

from __future__ import annotations
import math
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

SEPARATORS = frozenset("-")

# Shape-based prior: characters that look alike in print, cost to confuse them.
_PRIOR_GROUPS: List[Tuple[str, float]] = [
    ("O0", 0.25), ("D0", 0.35), ("Q0", 0.4), ("OD", 0.4), ("OQ", 0.4),
    ("I1", 0.25), ("L1", 0.35), ("IL", 0.35), ("17", 0.5), ("T7", 0.55),
    ("S5", 0.3), ("B8", 0.3), ("38", 0.5), ("Z2", 0.35), ("G6", 0.4),
    ("56", 0.6), ("68", 0.6), ("08", 0.6), ("A4", 0.6), ("EF", 0.6),
    ("UV", 0.6), ("CG", 0.6), ("MN", 0.7), ("HN", 0.7), ("RB", 0.7), ("EB", 0.7),
]


def prior_sub_costs() -> Dict[str, float]:
    costs: Dict[str, float] = {}
    for pair, cost in _PRIOR_GROUPS:
        a, b = pair[0], pair[1]
        costs[a + b] = cost
        costs[b + a] = cost
    return costs


class ConfusionModel:
    def __init__(self, sub_costs: Optional[Dict[str, float]] = None,
                 trans_cost: float = 0.6, indel_cost: float = 1.0,
                 sep_cost: float = 0.1, double_cost: float = 0.5,
                 band: int = 3, source: str = "prior",
                 counts: Optional[Dict[str, int]] = None):
        self.sub = dict(sub_costs) if sub_costs is not None else prior_sub_costs()
        self.trans_cost = trans_cost
        self.indel_cost = indel_cost
        self.sep_cost = sep_cost
        self.double_cost = double_cost
        self.band = band
        self.source = source
        self.counts = dict(counts or {})

    # -- cost primitives -------------------------------------------------------

    def sub_cost(self, truth_ch: str, obs_ch: str) -> float:
        if truth_ch == obs_ch:
            return 0.0
        return self.sub.get(truth_ch + obs_ch, 1.0)

    def _ins(self, obs: str, j: int) -> float:
        ch = obs[j]
        if ch in SEPARATORS:
            return self.sep_cost
        if j > 0 and obs[j - 1] == ch:
            return self.double_cost
        return self.indel_cost

    def _del(self, ch: str) -> float:
        return self.sep_cost if ch in SEPARATORS else self.indel_cost

    # -- distance --------------------------------------------------------------

    def distance(self, observed: str, truth: str, cutoff: Optional[float] = None) -> float:
        """
        Weighted OSA distance from what was recorded to what is registered.
        With a cutoff, gives up as soon as the answer must exceed it (returns a
        value above the cutoff). The bound uses the last two rows, because a
        transposition can jump from row i-2 straight to row i.
        """
        o, t = observed, truth
        if o == t:
            return 0.0
        lo, lt = len(o), len(t)
        if abs(lo - lt) > self.band:
            return 99.0
        inf = float("inf")
        band = self.band
        prev2: List[float] = []
        prev = [0.0] * (lo + 1)
        for j in range(1, lo + 1):
            prev[j] = prev[j - 1] + self._ins(o, j - 1) if j <= band else inf
        for i in range(1, lt + 1):
            tc = t[i - 1]
            cur = [inf] * (lo + 1)
            cur[0] = prev[0] + self._del(tc) if i <= band else inf
            jlo, jhi = max(1, i - band), min(lo, i + band)
            for j in range(jlo, jhi + 1):
                oc = o[j - 1]
                best = prev[j - 1] + (0.0 if tc == oc else self.sub.get(tc + oc, 1.0))
                v = prev[j] + self._del(tc)
                if v < best:
                    best = v
                v = cur[j - 1] + self._ins(o, j - 1)
                if v < best:
                    best = v
                if i > 1 and j > 1 and tc != oc and tc == o[j - 2] and t[i - 2] == oc:
                    v = prev2[j - 2] + self.trans_cost
                    if v < best:
                        best = v
                cur[j] = best
            if cutoff is not None and min(cur) > cutoff and min(prev) > cutoff:
                return cutoff + 1.0
            prev2, prev = prev, cur
        return prev[lo]

    def similarity(self, observed: str, truth: str) -> float:
        d = self.distance(observed, truth)
        return max(0.0, 1.0 - d / max(len(observed), len(truth), 1))

    # -- learning --------------------------------------------------------------

    @staticmethod
    def _align(truth: str, observed: str) -> List[Tuple[str, str, str]]:
        """Unit-cost OSA alignment with backtrace: [(op, truth_ch, obs_ch)]."""
        lt, lo = len(truth), len(observed)
        d = [[0] * (lo + 1) for _ in range(lt + 1)]
        for i in range(lt + 1):
            d[i][0] = i
        for j in range(lo + 1):
            d[0][j] = j
        for i in range(1, lt + 1):
            for j in range(1, lo + 1):
                c = 0 if truth[i - 1] == observed[j - 1] else 1
                v = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + c)
                if (i > 1 and j > 1 and truth[i - 1] == observed[j - 2]
                        and truth[i - 2] == observed[j - 1]):
                    v = min(v, d[i - 2][j - 2] + 1)
                d[i][j] = v
        ops = []
        i, j = lt, lo
        while i > 0 or j > 0:
            if (i > 1 and j > 1 and truth[i - 1] == observed[j - 2] and truth[i - 2] == observed[j - 1]
                    and truth[i - 1] != observed[j - 1] and d[i][j] == d[i - 2][j - 2] + 1):
                ops.append(("trans", truth[i - 2:i], observed[j - 2:j]))
                i, j = i - 2, j - 2
            elif i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (truth[i - 1] != observed[j - 1]):
                op = "keep" if truth[i - 1] == observed[j - 1] else "sub"
                ops.append((op, truth[i - 1], observed[j - 1]))
                i, j = i - 1, j - 1
            elif i > 0 and d[i][j] == d[i - 1][j] + 1:
                ops.append(("del", truth[i - 1], ""))
                i -= 1
            else:
                ops.append(("ins", "", observed[j - 1]))
                j -= 1
        return list(reversed(ops))

    @classmethod
    def fit(cls, pairs: Iterable[Tuple[str, str]], min_total: int = 4,
            min_pair: int = 2, alphabet: int = 36) -> "ConfusionModel":
        """
        Learn substitution costs from (observed, truth) pairs.

        For a printed character t, p = P(recorded as o | t was misrecorded). A
        uniformly random slip has p0 = 1/alphabet. The cost is how much more
        likely than chance the confusion is, on a log scale:

            cost(t -> o) = 1 - log(p / p0) / log(1 / p0)        clipped to [0.1, 1]

        A confusion as likely as chance costs 1.0, like any edit. One that
        accounts for most of how t goes wrong approaches 0.1. Using the
        likelihood ratio rather than the raw share matters for characters with
        several genuine confusions: O is read as 0, D and Q, and none of those
        should be priced like a random typo just because the others exist.
        Pairs never seen often enough keep their shape-based prior.
        """
        subs: Dict[str, Counter] = defaultdict(Counter)
        n_pairs = 0
        for observed, truth in pairs:
            if not observed or not truth or observed == truth:
                continue
            n_pairs += 1
            for op, tc, oc in cls._align(truth, observed):
                if op == "sub":
                    subs[tc][oc] += 1
        costs = prior_sub_costs()
        counts: Dict[str, int] = {}
        p0 = 1.0 / alphabet
        for tc, ctr in subs.items():
            total = sum(ctr.values())
            if total < min_total:
                continue
            for oc, n in ctr.items():
                counts[tc + oc] = n
                if n >= min_pair:
                    p = n / total
                    cost = 1.0 - math.log(p / p0) / math.log(1.0 / p0)
                    costs[tc + oc] = round(min(1.0, max(0.1, cost)), 3)
        return cls(sub_costs=costs, source=f"learned from {n_pairs} training pairs", counts=counts)

    def top_confusions(self, n: int = 16, min_seen: int = 2) -> List[Dict[str, object]]:
        """The cheapest substitutions actually observed in training."""
        learned = sorted(((k, v) for k, v in self.sub.items()
                          if v < 1.0 and self.counts.get(k, 0) >= min_seen),
                         key=lambda kv: (kv[1], -self.counts.get(kv[0], 0)))
        return [{"truth": k[0], "observed": k[1], "cost": c, "seen": self.counts.get(k, 0)}
                for k, c in learned[:n]]

    # -- persistence -----------------------------------------------------------

    def to_dict(self) -> Dict[str, object]:
        return {"sub": self.sub, "trans_cost": self.trans_cost, "indel_cost": self.indel_cost,
                "sep_cost": self.sep_cost, "double_cost": self.double_cost, "band": self.band,
                "source": self.source, "counts": self.counts}

    @classmethod
    def from_dict(cls, d: Dict[str, object]) -> "ConfusionModel":
        return cls(sub_costs=d.get("sub"), trans_cost=d.get("trans_cost", 0.6),
                   indel_cost=d.get("indel_cost", 1.0), sep_cost=d.get("sep_cost", 0.1),
                   double_cost=d.get("double_cost", 0.5), band=d.get("band", 3),
                   source=d.get("source", "loaded"), counts=d.get("counts"))


def code_level(distance: float) -> str:
    """Discretise a code distance into the levels the linkage model weighs."""
    if distance <= 0.0:
        return "L0_exact"
    if distance <= 0.6:
        return "L1_confusable"
    if distance <= 1.2:
        return "L2_one_edit"
    if distance <= 2.2:
        return "L3_two_edits"
    return "L4_far"
