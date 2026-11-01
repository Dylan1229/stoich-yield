"""The verifier's own formula parser: regular expressions and a stack, independent of src/'s recursive
descent, so a parser bug on either side shows up as a disagreement.

It reads the same grammar: case-sensitive element symbols with optional positive counts, nested () and []
groups with counts, hydrate parts joined by * or · (a later part may start with a multiplier), and an
optional charge suffix ^+, ^-, ^2+, ^3-. The element symbols are those with a standard atomic weight up to
U (92); the weights themselves are never needed here.
"""

import re
from collections import Counter

SYMBOLS = frozenset(
    [
        "H",
        "He",
        "Li",
        "Be",
        "B",
        "C",
        "N",
        "O",
        "F",
        "Ne",
        "Na",
        "Mg",
        "Al",
        "Si",
        "P",
        "S",
        "Cl",
        "Ar",
        "K",
        "Ca",
        "Sc",
        "Ti",
        "V",
        "Cr",
        "Mn",
        "Fe",
        "Co",
        "Ni",
        "Cu",
        "Zn",
        "Ga",
        "Ge",
        "As",
        "Se",
        "Br",
        "Kr",
        "Rb",
        "Sr",
        "Y",
        "Zr",
        "Nb",
        "Mo",
        "Ru",
        "Rh",
        "Pd",
        "Ag",
        "Cd",
        "In",
        "Sn",
        "Sb",
        "Te",
        "I",
        "Xe",
        "Cs",
        "Ba",
        "La",
        "Ce",
        "Pr",
        "Nd",
        "Sm",
        "Eu",
        "Gd",
        "Tb",
        "Dy",
        "Ho",
        "Er",
        "Tm",
        "Yb",
        "Lu",
        "Hf",
        "Ta",
        "W",
        "Re",
        "Os",
        "Ir",
        "Pt",
        "Au",
        "Hg",
        "Tl",
        "Pb",
        "Bi",
        "Th",
        "Pa",
        "U",
    ]
)
MAX_LENGTH = 100
WHOLE = re.compile(r"(?P<body>[^\^]*)(?:\^(?P<size>[1-9][0-9]*)?(?P<sign>[+-]))?")
PART = re.compile(r"(?P<multiplier>[1-9][0-9]*)?(?P<units>.*)")
TOKEN = re.compile(r"(?P<element>[A-Z][a-z]?)|(?P<open>[(\[])|(?P<close>[)\]])|(?P<count>[1-9][0-9]*)")
PAIRS = {"(": ")", "[": "]"}


def _units(text):
    """(atoms per element, normalized text) of one hydrate part's units, or (None, why it is malformed)."""
    frames = [Counter()]
    opened = []
    pending = None  # the last unit (an element or a closed group), not yet added to its frame
    shown = []
    at = 0
    for match in TOKEN.finditer(text):
        if match.start() != at:
            return None, f"unexpected {text[at]!r}"
        at = match.end()
        kind, token = match.lastgroup, match.group()
        if kind == "count":
            if pending is None:
                return None, f"the count {token} follows no element or group"
            pending = Counter({element: atoms * int(token) for element, atoms in pending.items()})
            if token != "1":
                shown.append(token)
            frames[-1].update(pending)
            pending = None
            continue
        if pending is not None:
            frames[-1].update(pending)
            pending = None
        if kind == "element":
            if token not in SYMBOLS:
                return None, f"unknown element {token!r}"
            pending = Counter({token: 1})
        elif kind == "open":
            frames.append(Counter())
            opened.append(token)
        else:
            if not opened or PAIRS[opened[-1]] != token:
                return None, f"{token!r} closes no matching bracket"
            opened.pop()
            group = frames.pop()
            if not group:
                return None, "empty brackets"
            pending = group
        shown.append(token)
    if at != len(text):
        return None, f"unexpected {text[at]!r}"
    if opened:
        return None, f"{opened[-1]!r} is never closed"
    if pending is not None:
        frames[-1].update(pending)
    if not frames[0]:
        return None, "a part holds no element"
    return frames[0], "".join(shown)


def read_formula(text):
    """(the formula {"counts": {element: atoms}, "charge": int, "normalized": str}, None) or (None, why it is
    malformed)."""
    if not isinstance(text, str) or not text:
        return None, "it is empty"
    if len(text) > MAX_LENGTH:
        return None, f"it is longer than {MAX_LENGTH} characters"
    whole = WHOLE.fullmatch(text)
    if whole is None:
        return None, "its charge is not a final ^, an optional positive integer and + or -"
    counts = Counter()
    pieces = []
    for index, part in enumerate(re.split(r"[*·]", whole.group("body"))):
        found = PART.fullmatch(part)
        multiplier = found.group("multiplier") if found else None
        if index == 0 and multiplier:
            return None, "it starts with a number (a coefficient is not part of a formula)"
        atoms, shown = _units(found.group("units") if found else part)
        if atoms is None:
            return None, shown
        times = int(multiplier or "1")
        counts.update({element: count * times for element, count in atoms.items()})
        pieces.append(("" if times == 1 else str(times)) + shown)
    charge = 0
    suffix = ""
    if whole.group("sign"):
        size = int(whole.group("size") or "1")
        charge = size if whole.group("sign") == "+" else -size
        suffix = "^" + ("" if size == 1 else str(size)) + whole.group("sign")
    normalized = "*".join(pieces) + suffix
    return {"counts": dict(sorted(counts.items())), "charge": charge, "normalized": normalized}, None


def identity(formula):
    """What makes two read formulas the same species: their atoms and charge."""
    return tuple(sorted(formula["counts"].items())), formula["charge"]
