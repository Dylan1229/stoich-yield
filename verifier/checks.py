"""Shared verdict helpers: a result, named checks, and a reaction's input read the way every tool takes it.
Pure functions of their arguments and the files on disk."""

import hashlib
import json
import math
import re
from fractions import Fraction
from pathlib import Path

from .formula import identity, read_formula

MAX_SPECIES = 6
MIN_GRAMS = 1e-6
MAX_GRAMS = 1e6
WORKSHEETS = "worksheets"
READABLE = 60
SAME = "have the same atoms and charge"


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def plain(value):
    """A value as JSON a verdict can hold: non-finite floats as text."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    return value


def check(identifier, ok, expected=None, actual=None, message=""):
    """One named check: ok is True (holds), False (fails) or None (not checked: a check it needs failed)."""
    return {
        "id": identifier,
        "ok": ok,
        "expected": plain(expected),
        "actual": plain(actual),
        "message": "" if ok is True else message,
    }


def verdict(checks, success):
    """valid when every check holds; score the share that hold; the message the first failure and how many more."""
    held = sum(entry["ok"] is True for entry in checks)
    score = held / len(checks)
    failed = [entry for entry in checks if entry["ok"] is False]
    if not failed and held == len(checks):
        return result(True, success, score=1.0, checks=checks)
    first = failed[0] if failed else next(entry for entry in checks if entry["ok"] is not True)
    more = f" (+{len(failed) - 1} more failing)" if len(failed) > 1 else ""
    return result(False, f"{first['id']}: {first['message']}{more}", score=score, checks=checks)


def side_problem(reactants, products):
    """(the read reactants and products, None) or (None, what is wrong): 1 to 6 formulas a side, each well
    formed, no species twice on a side or on both sides."""
    for side, texts in (("reactants", reactants), ("products", products)):
        if not 1 <= len(texts) <= MAX_SPECIES:
            return None, f"{side} must list 1 to {MAX_SPECIES} formulas, not {len(texts)}"
    read = {}
    for side, texts in (("reactants", reactants), ("products", products)):
        read[side] = []
        for text in texts:
            formula, problem = read_formula(text)
            if problem:
                return None, f"malformed formula {text!r}: {problem}"
            read[side].append(formula)
    for side, texts in (("reactants", reactants), ("products", products)):
        keys = [identity(formula) for formula in read[side]]
        for later, key in enumerate(keys):
            if key in keys[:later]:
                first = texts[keys.index(key)]
                return None, f"duplicate species among the {side}: {first!r} and {texts[later]!r} {SAME}"
    left = [identity(formula) for formula in read["reactants"]]
    for index, formula in enumerate(read["products"]):
        if identity(formula) in left:
            reactant = reactants[left.index(identity(formula))]
            return None, f"a species on both sides: reactant {reactant!r} and product {products[index]!r} {SAME}"
    return (read["reactants"], read["products"]), None


def grams_exact(grams):
    """A float mass as the exact decimal it is written as (its shortest repr), or None when it is not finite."""
    return Fraction(repr(grams)) if math.isfinite(grams) else None


def reaction_problem(value):
    """(the read reactants and products, None) or (None, what is wrong) for any value with reactants,
    products, given and target: the task input as every tool and the answer key take it."""
    sides, problem = side_problem(value.reactants, value.products)
    if problem:
        return None, problem
    if not value.given:
        return None, "given must hold the mass of at least one reactant"
    named = []
    for entry in value.given:
        if entry.formula not in value.reactants:
            return None, f"given formula {entry.formula!r} is not one of the reactants (spell it as there)"
        if entry.formula in named:
            return None, f"duplicate given: {entry.formula!r} is given twice"
        named.append(entry.formula)
        if not math.isfinite(entry.grams) or entry.grams <= 0:
            return None, f"the mass of {entry.formula!r} must be a positive number of grams, not {entry.grams!r}"
        if not MIN_GRAMS <= entry.grams <= MAX_GRAMS:
            return None, f"the mass of {entry.formula!r} must be from 0.000001 to 1000000 g, not {entry.grams!r}"
    if value.target not in value.products:
        return None, f"target {value.target!r} is not one of the products (spell it as there)"
    return sides, None


def coefficients_problem(side, formulas, coefficients):
    if len(coefficients) != len(formulas):
        return f"{side} need one coefficient per formula: {len(formulas)} formulas, {len(coefficients)} given"
    if any(coefficient < 1 for coefficient in coefficients):
        return f"{side} coefficients must be positive integers, not {coefficients}"
    return None


def tally(formulas, coefficients):
    """A side's atoms per element and total charge under ``coefficients`` (read formulas)."""
    atoms = {}
    charge = 0
    for formula, coefficient in zip(formulas, coefficients, strict=True):
        for element, count in formula["counts"].items():
            atoms[element] = atoms.get(element, 0) + count * coefficient
        charge += formula["charge"] * coefficient
    return atoms, charge


def imbalance(left, right, reactant_coefficients, product_coefficients):
    """(the elements not conserved, as {element: [left, right]}, the charges [left, right])."""
    atoms_left, charge_left = tally(left, reactant_coefficients)
    atoms_right, charge_right = tally(right, product_coefficients)
    off = {
        element: [atoms_left.get(element, 0), atoms_right.get(element, 0)]
        for element in sorted(set(atoms_left) | set(atoms_right))
        if atoms_left.get(element, 0) != atoms_right.get(element, 0)
    }
    return off, [charge_left, charge_right]


def _piece(formula):
    return re.sub(r"[^A-Za-z0-9]+", "_", formula.replace("+", "p").replace("-", "m")).strip("_") or "x"


def worksheet_path(value):
    """Where save_worksheet saves a task's worksheet: worksheets/<target>-from-<reactants>-<digest>.json, the
    digest the sha256 of the task input as compact, key-sorted JSON."""
    readable = f"{_piece(value.target)}-from-{'-'.join(_piece(name) for name in value.reactants)}"[:READABLE]
    task = {
        "reactants": list(value.reactants),
        "products": list(value.products),
        "given": [[entry.formula, entry.grams] for entry in value.given],
        "target": value.target,
    }
    digest = hashlib.sha256(json.dumps(task, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:10]
    return f"{WORKSHEETS}/{readable.rstrip('-_')}-{digest}.json"


MAX_FILE_BYTES = 64 * 1024  # far above any worksheet (about 1 KB)


def saved_worksheet(workspace, path, expected):
    """(the worksheet's JSON object, None) or (None, why it is not the one save_worksheet saved): ``path``
    must be ``expected`` (relative, under worksheets/), inside the workspace, a JSON object."""
    if path != expected:
        if not path or path.startswith("/") or ".." in path.split("/"):
            return None, f"path {path!r} is not a relative path inside the workspace"
        return None, f"path {path!r} is not {expected}, where save_worksheet saves this task's worksheet"
    file = Path(workspace, path)
    if not file.resolve().is_relative_to(Path(workspace).resolve()):
        return None, f"{path} leaves the workspace"
    if not file.is_file():
        return None, f"no worksheet at {path}: call save_worksheet before submitting"
    if file.stat().st_size > MAX_FILE_BYTES:
        return None, f"{path} holds over {MAX_FILE_BYTES} bytes, more than any worksheet"
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (ValueError, RecursionError):
        return None, f"{path} is not JSON"
    if not isinstance(data, dict):
        return None, f"{path} holds no JSON object"
    return data, None


def differences(saved, submitted):
    """The fields in which a saved worksheet and a submission differ, sorted."""
    missing = object()
    return sorted(key for key in set(saved) | set(submitted) if saved.get(key, missing) != submitted.get(key, missing))
