"""
noise.py
--------
A typed noise channel. Each kind of corruption corresponds to a real way a code
gets damaged between the pack and the database:

  ocr        a camera or scanner reads a glyph as a similar-looking one (O/0, B/8)
  keyboard   a finger lands on the neighbouring key
  transpose  two adjacent characters typed in the wrong order
  delete     a character skipped
  insert     a key pressed twice, or a stray neighbour
  format     case, spacing and separators changed but nothing else
  truncate   the last character lost (label torn, field too short)
  mixed      two of the above at once

Every function takes and returns a plain string and draws from the Random
instance it is given, so a seeded generator reproduces the same dataset.
"""

from __future__ import annotations
import random
from typing import Dict, List, Tuple

# Glyph pairs an optical reader genuinely confuses, with relative frequency.
# Truth character -> [(observed character, weight)].
OCR_CONFUSIONS: Dict[str, List[Tuple[str, int]]] = {
    "0": [("O", 6), ("D", 2), ("Q", 1), ("8", 1)],
    "O": [("0", 6), ("D", 2), ("Q", 1)],
    "D": [("0", 3), ("O", 3)],
    "1": [("I", 4), ("L", 2), ("7", 2)],
    "I": [("1", 5), ("L", 2)],
    "L": [("1", 3), ("I", 3)],
    "5": [("S", 5), ("6", 2)],
    "S": [("5", 5), ("8", 1)],
    "8": [("B", 4), ("3", 2), ("6", 1), ("0", 1)],
    "B": [("8", 5), ("R", 1)],
    "2": [("Z", 5)],
    "Z": [("2", 5)],
    "6": [("G", 4), ("5", 1), ("8", 1)],
    "G": [("6", 4), ("C", 2)],
    "7": [("1", 3), ("T", 2)],
    "T": [("7", 2)],
    "3": [("8", 3)],
    "A": [("4", 2)],
    "4": [("A", 2)],
    "E": [("F", 2), ("B", 1)],
    "F": [("E", 2)],
    "U": [("V", 2)],
    "V": [("U", 2)],
    "M": [("N", 2)],
    "N": [("M", 2), ("H", 1)],
    "C": [("G", 2)],
    "R": [("B", 1)],
    "H": [("N", 1)],
}

_ROWS = ["1234567890", "QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM"]


def _keyboard_neighbours() -> Dict[str, str]:
    pos = {}
    for r, row in enumerate(_ROWS):
        for c, ch in enumerate(row):
            pos[ch] = (r, c)
    out = {}
    for ch, (r, c) in pos.items():
        near = []
        for other, (r2, c2) in pos.items():
            if other != ch and abs(r - r2) <= 1 and abs(c - c2) <= 1:
                near.append(other)
        out[ch] = "".join(sorted(near))
    return out


KEYBOARD_NEIGHBOURS = _keyboard_neighbours()

NOISE_KINDS = ["ocr", "keyboard", "transpose", "delete", "insert", "format", "truncate", "mixed"]

# How each capture channel tends to fail. Weights are relative.
CHANNEL_PROFILES: Dict[str, Dict[str, int]] = {
    "ocr":     {"ocr": 70, "mixed": 12, "format": 8, "delete": 5, "truncate": 5},
    "manual":  {"keyboard": 28, "transpose": 20, "delete": 15, "insert": 10, "format": 15, "mixed": 12},
    "erp":     {"format": 35, "keyboard": 18, "transpose": 15, "delete": 10, "ocr": 15, "mixed": 7},
    "citizen": {"format": 35, "keyboard": 15, "delete": 15, "transpose": 10, "insert": 5, "mixed": 20},
    "scan":    {"truncate": 60, "delete": 40},
}


def _editable_positions(s: str) -> List[int]:
    return [i for i, ch in enumerate(s) if ch.isalnum()]


def ocr(s: str, rng: random.Random, edits: int = 0) -> str:
    chars = list(s)
    eligible = [i for i in _editable_positions(s) if chars[i] in OCR_CONFUSIONS]
    if not eligible:
        return keyboard(s, rng)
    n = edits or rng.choice([1, 1, 1, 2, 2])
    for i in rng.sample(eligible, min(n, len(eligible))):
        options = OCR_CONFUSIONS[chars[i]]
        total = sum(w for _, w in options)
        pick = rng.uniform(0, total)
        for ch, w in options:
            pick -= w
            if pick <= 0:
                chars[i] = ch
                break
    out = "".join(chars)
    # A camera often loses or invents a separator as well.
    if "-" in out and rng.random() < 0.15:
        out = out.replace("-", rng.choice(["", " ", "."]), 1)
    return out


def keyboard(s: str, rng: random.Random) -> str:
    pos = _editable_positions(s)
    if not pos:
        return s
    i = rng.choice(pos)
    near = KEYBOARD_NEIGHBOURS.get(s[i].upper(), "")
    if not near:
        return s
    return s[:i] + rng.choice(near) + s[i + 1:]


def transpose(s: str, rng: random.Random) -> str:
    pairs = [i for i in range(len(s) - 1)
             if s[i].isalnum() and s[i + 1].isalnum() and s[i] != s[i + 1]]
    if not pairs:
        return keyboard(s, rng)
    i = rng.choice(pairs)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def delete(s: str, rng: random.Random) -> str:
    pos = _editable_positions(s)
    if len(pos) < 4:
        return s
    i = rng.choice(pos)
    return s[:i] + s[i + 1:]


def insert(s: str, rng: random.Random) -> str:
    pos = _editable_positions(s)
    if not pos:
        return s
    i = rng.choice(pos)
    if rng.random() < 0.6:
        extra = s[i]                                  # key pressed twice
    else:
        extra = rng.choice(KEYBOARD_NEIGHBOURS.get(s[i].upper(), s[i]) or s[i])
    return s[:i] + extra + s[i:]


def fmt(s: str, rng: random.Random) -> str:
    out = s
    roll = rng.random()
    if roll < 0.35:
        out = out.lower()
    elif roll < 0.55:
        out = out.title()
    sep = rng.choice(["", " ", "_", ".", "/", "--"])
    if rng.random() < 0.7:
        out = out.replace("-", sep)
    if rng.random() < 0.25:
        out = " " + out + "  "
    return out if out != s else s.lower()


def truncate(s: str, rng: random.Random) -> str:
    return s[:-1] if len(s) > 4 else s


_OPS = {
    "ocr": ocr, "keyboard": keyboard, "transpose": transpose, "delete": delete,
    "insert": insert, "format": fmt, "truncate": truncate,
}


def corrupt(s: str, kind: str, rng: random.Random) -> str:
    """Apply one named kind of noise. 'mixed' chains two different kinds."""
    if kind == "mixed":
        first, second = rng.sample(["ocr", "keyboard", "transpose", "delete", "insert"], 2)
        return _OPS[second](_OPS[first](s, rng), rng)
    return _OPS[kind](s, rng)


def pick_kind(channel: str, rng: random.Random) -> str:
    profile = CHANNEL_PROFILES.get(channel, CHANNEL_PROFILES["manual"])
    total = sum(profile.values())
    roll = rng.uniform(0, total)
    for kind, w in profile.items():
        roll -= w
        if roll <= 0:
            return kind
    return next(iter(profile))


def corrupt_for_channel(s: str, channel: str, rng: random.Random) -> Tuple[str, str]:
    """Corrupt s the way the given capture channel would. Returns (noisy, kind)."""
    for _ in range(6):
        kind = pick_kind(channel, rng)
        noisy = corrupt(s, kind, rng)
        if noisy != s:
            return noisy, kind
    return s.lower(), "format"


# Spelling slips people make when they write a brand name from memory.
PHONETIC_SWAPS = [("PH", "F"), ("X", "KS"), ("C", "K"), ("Y", "I"), ("EE", "I"),
                  ("OO", "U"), ("W", "V"), ("Z", "S"), ("QU", "KW"), ("TH", "T")]


def phonetic(s: str, rng: random.Random) -> str:
    up = s.upper()
    options = [(a, b) for a, b in PHONETIC_SWAPS if a in up]
    if not options:
        # Double or single a consonant instead.
        pos = [i for i, ch in enumerate(up) if ch.isalpha() and ch not in "AEIOU"]
        if not pos:
            return keyboard(s, rng)
        i = rng.choice(pos)
        return up[:i] + up[i] + up[i:]
    a, b = rng.choice(options)
    return up.replace(a, b, 1)
