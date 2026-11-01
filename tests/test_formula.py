"""The formula grammar and molar masses: golden values computed by hand from the table's weights, malformed
formulas, and the plugin's parser against the verifier's own (a different algorithm) on random strings."""

from __future__ import annotations

import hashlib
import json
import random
from fractions import Fraction

import pytest

from plugin.formula import DATA, data_sha256, molar_mass, parse, table
from verifier.formula import SYMBOLS, read_formula

# Hand sums with the table's weights: H 1.008, C 12.011, N 14.007, O 15.999, P 30.974, S 32.06, K 39.098,
# Ca 40.078, Mn 54.938, Fe 55.845, Co 58.933, Cu 63.546.
GOLDEN = [
    ("H2O", {"H": 2, "O": 1}, 0, "18.015"),  # 2.016 + 15.999
    ("C3H8", {"C": 3, "H": 8}, 0, "44.097"),  # 36.033 + 8.064
    ("O2", {"O": 2}, 0, "31.998"),
    ("CO2", {"C": 1, "O": 2}, 0, "44.009"),  # 12.011 + 31.998
    ("CuSO4*5H2O", {"Cu": 1, "H": 10, "O": 9, "S": 1}, 0, "249.677"),  # 63.546 + 32.06 + 143.991 + 10.08
    ("K4[Fe(CN)6]", {"C": 6, "Fe": 1, "K": 4, "N": 6}, 0, "368.345"),  # 156.392 + 55.845 + 72.066 + 84.042
    ("Ca3(PO4)2", {"Ca": 3, "O": 8, "P": 2}, 0, "310.174"),  # 120.234 + 61.948 + 127.992
    ("Co2(CO)8", {"C": 8, "Co": 2, "O": 8}, 0, "341.946"),  # 117.866 + 96.088 + 127.992
    ("MnO4^-", {"Mn": 1, "O": 4}, -1, "118.934"),  # 54.938 + 63.996
    ("Fe^3+", {"Fe": 1}, 3, "55.845"),
    ("SO4^2-", {"O": 4, "S": 1}, -2, "96.056"),  # 32.06 + 63.996
    ("C57H110O6", {"C": 57, "H": 110, "O": 6}, 0, "891.501"),  # 684.627 + 110.88 + 95.994
]


@pytest.mark.parametrize(("text", "counts", "charge", "mass"), GOLDEN)
def test_correct_golden_formulas(text: str, counts: dict, charge: int, mass: str) -> None:
    formula = parse(text)
    assert formula.counts == counts and formula.charge == charge
    assert molar_mass(formula) == Fraction(mass)
    read, problem = read_formula(text)
    assert problem is None and read["counts"] == counts and read["charge"] == charge


def test_boundary_case_sensitive_symbols() -> None:
    assert parse("Co").counts == {"Co": 1}
    assert parse("CO").counts == {"C": 1, "O": 1}
    assert parse("Co2(CO)8").counts == {"C": 8, "Co": 2, "O": 8}
    assert parse("NO").counts == {"N": 1, "O": 1}
    with pytest.raises(ValueError, match="unknown element 'No'"):  # nobelium: no standard atomic weight
        parse("No")
    with pytest.raises(ValueError, match="unknown element 'Xx'"):
        parse("Xx")


@pytest.mark.parametrize(
    ("text", "normalized"),
    [
        ("CuSO4·5H2O", "CuSO4*5H2O"),
        ("CuSO4*1H2O", "CuSO4*H2O"),
        ("H1", "H"),
        ("Fe^1+", "Fe^+"),
        ("(OH)1", "(OH)"),
        ("[Cu(H2O)6]^2+", "[Cu(H2O)6]^2+"),
        ("Na2CO3*10H2O", "Na2CO3*10H2O"),
    ],
)
def test_boundary_normalized_form(text: str, normalized: str) -> None:
    assert parse(text).normalized == normalized
    assert read_formula(text)[0]["normalized"] == normalized


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "empty"),
        ("2H2O", "starts with a number"),
        ("H2O ", "unexpected ' '"),
        ("H2O(l)", "unexpected 'l'"),
        ("(H2O", "closed by the end"),
        ("H2O)", "closes no bracket"),
        ("(H2]", "closed by ']'"),
        ("()", "empty brackets"),
        ("H0", "positive integer"),
        ("H02", "positive integer"),
        ("Fe^", "a charge is"),
        ("Fe^0+", "positive integer"),
        ("Fe+3", "unexpected '+'"),
        ("Tc", "unknown element 'Tc'"),
        ("Np", "unknown element 'Np'"),
        ("CuSO4*", "holds no element"),
        ("CuSO4*5", "holds no element"),
        ("e^-", "unexpected 'e'"),
        ("H₂O", "unexpected '₂'"),
        ("C" * 101, "longer than 100"),
    ],
)
def test_malformed_formulas_are_refused_by_both_parsers(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match="malformed formula") as error:
        parse(text)
    assert reason in str(error.value)
    assert read_formula(text)[1] is not None


def test_correct_table_is_the_verifiers_symbols_and_its_hash() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    assert set(table()) == SYMBOLS and len(SYMBOLS) == 84
    assert [row["number"] for row in data["elements"]] == sorted(row["number"] for row in data["elements"])
    assert {
        "H": "1.0080",
        "C": "12.011",
        "N": "14.007",
        "O": "15.999",
        "Na": "22.990",
        "Cl": "35.45",
    }.items() <= table().items()
    assert all(Fraction(weight) > 0 for weight in table().values())
    assert data_sha256() == hashlib.sha256(DATA.read_bytes()).hexdigest()


PIECES = [
    "H",
    "C",
    "O",
    "Co",
    "N",
    "Fe",
    "Cl",
    "Xy",
    "(",
    ")",
    "[",
    "]",
    "2",
    "3",
    "0",
    "1",
    "10",
    "*",
    "·",
    "^",
    "+",
    "-",
    " ",
    "e",
]


def test_boundary_both_parsers_agree_on_random_strings() -> None:
    """20,000 random strings: the plugin's recursive descent and the verifier's regex-and-stack parser accept
    exactly the same ones, with the same atoms, charge and normalized form."""
    generator = random.Random(580)
    accepted = 0
    for _ in range(20_000):
        text = "".join(generator.choice(PIECES) for _ in range(generator.randint(1, 9)))
        read, problem = read_formula(text)
        try:
            formula = parse(text)
        except ValueError:
            assert problem is not None, text
            continue
        accepted += 1
        assert problem is None, (text, problem)
        assert (formula.counts, formula.charge, formula.normalized) == (
            read["counts"],
            read["charge"],
            read["normalized"],
        )
    assert accepted > 1_000
