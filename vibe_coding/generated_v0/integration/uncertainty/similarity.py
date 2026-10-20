"""
similarity.py
-------------
The candidate string metrics, implemented directly so that the benchmark compares
like with like and nothing depends on a third-party package.

  levenshtein      insert / delete / substitute, every edit costs 1
  damerau_osa      Levenshtein plus adjacent transposition (optimal string alignment)
  jaro_winkler     agreement within a sliding window, boosted by a common prefix
  qgram_jaccard    overlap of padded character q-grams
  soundex          phonetic code; meaningful for names, not for serial numbers

Each distance has a matching similarity in [0, 1] so a single threshold can be
tuned per metric.
"""

from __future__ import annotations
import re
from typing import Set


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def damerau_osa(a: str, b: str) -> int:
    """Optimal string alignment distance: Levenshtein plus adjacent swaps."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if not la:
        return lb
    if not lb:
        return la
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            v = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                v = min(v, d[i - 2][j - 2] + 1)
            d[i][j] = v
    return d[la][lb]


def edit_similarity(distance: float, a: str, b: str) -> float:
    longest = max(len(a), len(b), 1)
    return max(0.0, 1.0 - distance / longest)


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    window = max(la, lb) // 2 - 1
    window = max(window, 0)
    a_hit = [False] * la
    b_hit = [False] * lb
    matches = 0
    for i, ca in enumerate(a):
        lo, hi = max(0, i - window), min(i + window + 1, lb)
        for j in range(lo, hi):
            if not b_hit[j] and b[j] == ca:
                a_hit[i] = b_hit[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    k = transpositions = 0
    for i in range(la):
        if a_hit[i]:
            while not b_hit[k]:
                k += 1
            if a[i] != b[k]:
                transpositions += 1
            k += 1
    transpositions //= 2
    return (matches / la + matches / lb + (matches - transpositions) / matches) / 3.0


def jaro_winkler(a: str, b: str, prefix_weight: float = 0.1) -> float:
    j = jaro(a, b)
    prefix = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefix += 1
    return j + prefix * prefix_weight * (1.0 - j)


def qgrams(s: str, q: int = 2) -> Set[str]:
    padded = "#" * (q - 1) + s + "#" * (q - 1)
    return {padded[i:i + q] for i in range(len(padded) - q + 1)}


def qgram_jaccard(a: str, b: str, q: int = 2) -> float:
    ga, gb = qgrams(a, q), qgrams(b, q)
    if not ga and not gb:
        return 1.0
    return len(ga & gb) / len(ga | gb)


_SOUNDEX = {
    **dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"),
    **dict.fromkeys("DT", "3"), "L": "4", **dict.fromkeys("MN", "5"), "R": "6",
}


def soundex(s: str) -> str:
    letters = re.sub(r"[^A-Z]", "", (s or "").upper())
    if not letters:
        return "0000"
    out = [letters[0]]
    prev = _SOUNDEX.get(letters[0], "")
    for ch in letters[1:]:
        code = _SOUNDEX.get(ch, "")
        if code and code != prev:
            out.append(code)
        if ch not in "HW":
            prev = code
        if len(out) == 4:
            break
    return "".join(out).ljust(4, "0")


def soundex_similarity(a: str, b: str) -> float:
    """1.0 when the codes agree, partial credit for a shared prefix of the code."""
    sa, sb = soundex(a), soundex(b)
    same = 0
    for ca, cb in zip(sa, sb):
        if ca != cb:
            break
        same += 1
    return same / 4.0
