"""The answer key, pin_yield, against answers worked out by hand: coefficients checked atom by atom, molar
masses summed from the table's weights, yields as exact fractions."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest
from helpers import PERMANGANATE, PROPANE, WATER_TIE, task
from slimconfig import build_output

from contract import ReactionInput
from plugin.solver import decimal_text, nullspace, pin_yield


def pin(arguments: dict):
    return pin_yield(build_output(arguments, ReactionInput), Path("."))


def test_correct_propane_golden() -> None:
    """C3H8 + 5 O2 -> 3 CO2 + 4 H2O. 10.0 g C3H8 is 10/44.097 = 0.22677 mol (extent 0.22677); 10.0 g O2 is
    10/31.998 = 0.31252 mol (extent 0.062504): O2 limits. CO2 = 10 / 31.998 / 5 x 3 x 44.009 g
    = 1320.27 / 159.99 = 132027/15999 = 44009/5333 = 8.25220 g."""
    key = pin(PROPANE)
    assert (key.reactant_coefficients, key.product_coefficients) == ([1, 5], [3, 4])
    assert key.limiting == ["O2"]
    assert (
        Fraction(key.theoretical_yield_exact)
        == Fraction(44009, 5333)
        == Fraction(10) / Fraction("31.998") / 5 * 3 * Fraction("44.009")
    )
    assert key.theoretical_yield_g == pytest.approx(8.252203, rel=1e-6)
    assert [species.molar_mass_exact for species in key.reactants + key.products] == [
        "44.097",
        "31.998",
        "44.009",
        "18.015",
    ]
    assert [given.grams_exact for given in key.given] == ["10", "10"]
    assert len(key.data_sha256) == 64


@pytest.mark.parametrize(
    ("reactants", "products", "left", "right"),
    [
        # MnO4^- + 5 Fe^2+ + 8 H^+ -> Mn^2+ + 5 Fe^3+ + 4 H2O: O 4 = 4, H 8 = 8, charge -1 + 10 + 8 = 2 + 15 = 17.
        (["MnO4^-", "Fe^2+", "H^+"], ["Mn^2+", "Fe^3+", "H2O"], [1, 5, 8], [1, 5, 4]),
        # 2 C57H110O6 + 163 O2 -> 114 CO2 + 110 H2O: C 114, H 220, O 12 + 326 = 228 + 110 = 338.
        (["C57H110O6", "O2"], ["CO2", "H2O"], [2, 163], [114, 110]),
        # K4[Fe(CN)6] + 6 H2SO4 + 6 H2O -> 2 K2SO4 + FeSO4 + 3 (NH4)2SO4 + 6 CO: K 4, S 6, N 6, H 24, O 30.
        (["K4[Fe(CN)6]", "H2SO4", "H2O"], ["K2SO4", "FeSO4", "(NH4)2SO4", "CO"], [1, 6, 6], [2, 1, 3, 6]),
        # 2 Ca3(PO4)2 + 6 SiO2 + 10 C -> 6 CaSiO3 + P4 + 10 CO: Ca 6, P 4, Si 6, C 10, O 16 + 12 = 18 + 10.
        (["Ca3(PO4)2", "SiO2", "C"], ["CaSiO3", "P4", "CO"], [2, 6, 10], [6, 1, 10]),
        # CuSO4*5H2O -> CuSO4 + 5 H2O.
        (["CuSO4*5H2O"], ["CuSO4", "H2O"], [1], [1, 5]),
        # Co2(CO)8 -> 2 Co + 8 CO: Co (cobalt) and CO (carbon monoxide) told apart by case.
        (["Co2(CO)8"], ["Co", "CO"], [1], [2, 8]),
        # 2 CO + O2 -> 2 CO2.
        (["CO", "O2"], ["CO2"], [2, 1], [2]),
    ],
)
def test_boundary_balancings(reactants: list, products: list, left: list, right: list) -> None:
    key = pin(task(reactants, products, {reactants[0]: 1.0}, products[0]))
    assert (key.reactant_coefficients, key.product_coefficients) == (left, right)


def test_boundary_exact_tie_lists_both_in_reactant_order() -> None:
    """2 H2 + O2 -> 2 H2O. 4.032 g H2 = 2 mol (extent 1); 31.998 g O2 = 1 mol (extent 1): a tie, so both,
    in reactant order. H2O = 1 x 2 x 18.015 = 36.03 g. Given in the other order, the order is the reactants'."""
    key = pin(WATER_TIE)
    assert key.limiting == ["H2", "O2"]
    assert Fraction(key.theoretical_yield_exact) == Fraction("36.03")
    swapped = WATER_TIE | {"given": list(reversed(WATER_TIE["given"]))}
    assert pin(swapped).limiting == ["H2", "O2"]


def test_boundary_one_reactant_given_and_target_coefficient_two() -> None:
    """N2 + 3 H2 -> 2 NH3 with only H2 given: 6.048 g = 3 mol, extent 1; NH3 = 1 x 2 x 17.031 = 34.062 g."""
    key = pin(task(["N2", "H2"], ["NH3"], {"H2": 6.048}, "NH3"))
    assert key.product_coefficients == [2] and key.limiting == ["H2"]
    assert Fraction(key.theoretical_yield_exact) == Fraction("34.062")


def test_boundary_ions_and_hydrate_yields() -> None:
    """1.18934 g MnO4^- = 0.01 mol (extent 0.01); 5.5845 g Fe^2+ = 0.1 mol (extent 0.02): MnO4^- limits,
    H2O = 0.01 x 4 x 18.015 = 0.7206 g. 24.9677 g CuSO4*5H2O = 0.1 mol: H2O = 0.1 x 5 x 18.015 = 9.0075 g."""
    key = pin(PERMANGANATE)
    assert key.limiting == ["MnO4^-"] and Fraction(key.theoretical_yield_exact) == Fraction("0.7206")
    hydrate = pin(task(["CuSO4*5H2O"], ["CuSO4", "H2O"], {"CuSO4*5H2O": 24.9677}, "H2O"))
    assert Fraction(hydrate.theoretical_yield_exact) == Fraction("9.0075")


def test_boundary_tiny_mass_and_large_coefficients() -> None:
    """0.00044097 g C3H8 = 1e-5 mol: CO2 = 3e-5 x 44.009 = 0.00132027 g. 8.91501 g C57H110O6 = 0.01 mol
    (extent 0.005) against 100 g O2 (extent 100 / 31.998 / 163 = 0.0192): CO2 = 0.005 x 114 x 44.009 = 25.08513 g."""
    tiny = pin(task(["C3H8", "O2"], ["CO2", "H2O"], {"C3H8": 0.00044097}, "CO2"))
    assert Fraction(tiny.theoretical_yield_exact) == Fraction("0.00132027")
    fat = pin(task(["C57H110O6", "O2"], ["CO2", "H2O"], {"C57H110O6": 8.91501, "O2": 100.0}, "CO2"))
    assert fat.limiting == ["C57H110O6"] and Fraction(fat.theoretical_yield_exact) == Fraction("25.08513")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (task(["H2", "O2"], ["H2O", "H2O2"], {"H2": 1.0}, "H2O"), "ambiguous: 2 independent balancings"),
        (task(["CO2"], ["CO", "C"], {"CO2": 1.0}, "CO"), "cannot be balanced with positive coefficients"),
        (task(["Fe^2+"], ["Fe^3+"], {"Fe^2+": 1.0}, "Fe^3+"), "only all-zero coefficients"),
        (task(["NaCl"], ["Na2O"], {"NaCl": 1.0}, "Na2O"), "cannot be balanced with positive coefficients"),
        (task(["H2", "O2", "N2"], ["H2O"], {"H2": 1.0}, "H2O"), "N2 0"),
        (task(["H2", "O2"], ["H2O"], {"H2": 4.032, "O2": 32.1}, "H2O"), "near tie"),
    ],
)
def test_malformed_reactions_the_answer_key_refuses(arguments: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        pin(arguments)


def test_boundary_near_tie_threshold() -> None:
    """Extents 1 and 1.0101 (1.01%) pass; 1 and 1.0099 (0.99%) are a refused near tie."""
    assert pin(task(["H2", "O2"], ["H2O"], {"H2": 4.032, "O2": 32.321}, "H2O")).limiting == ["H2"]
    with pytest.raises(ValueError, match="near tie"):
        pin(task(["H2", "O2"], ["H2O"], {"H2": 4.032, "O2": 32.315}, "H2O"))


def test_correct_nullspace_and_decimal_helpers() -> None:
    one = [Fraction(1)]
    assert nullspace([[Fraction(2), Fraction(-2)]], 2) == [[one[0], one[0]]]
    assert decimal_text(Fraction(44097, 1000)) == "44.097" and decimal_text(Fraction(1, 10**6)) == "0.000001"
