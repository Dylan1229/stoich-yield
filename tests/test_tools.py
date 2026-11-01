"""The agent's tools: parse_formula, check_balance and save_worksheet, called as the MCP server calls them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import PERMANGANATE, PROPANE, answer, saved
from slimconfig import build_output, plain_output

from contract import (
    CheckBalanceInput,
    CheckBalanceOutput,
    ParseFormulaInput,
    ParseFormulaOutput,
    PinnedYieldOutput,
    ReactionInput,
    WorksheetInput,
    WorksheetOutput,
)
from plugin import check_balance, parse_formula, pin_yield, save_worksheet


def test_correct_parse_formula_takes_a_batch(tmp_path: Path) -> None:
    made = parse_formula(ParseFormulaInput(formulas=["C3H8", "O2", "CO2", "H2O", "MnO4^-", "CuSO4·5H2O"]), tmp_path)
    assert [row.molar_mass for row in made.species] == [44.097, 31.998, 44.009, 18.015, 118.934, 249.677]
    assert [row.charge for row in made.species] == [0, 0, 0, 0, -1, 0]
    assert made.species[5].normalized == "CuSO4*5H2O"
    assert [[entry.element, entry.count] for entry in made.species[0].elements] == [["C", 3], ["H", 8]]
    assert [entry.element for entry in made.atomic_weights] == ["C", "Cu", "H", "Mn", "O", "S"]
    assert len(json.dumps(plain_output(made))) < 3000  # compact for an agent with 2,048-token replies


def test_malformed_parse_formula_batch_sizes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="1 to 12"):
        parse_formula(ParseFormulaInput(formulas=[]), tmp_path)
    with pytest.raises(ValueError, match="1 to 12"):
        parse_formula(ParseFormulaInput(formulas=["H2O"] * 13), tmp_path)


def test_correct_check_balance_reports_each_element(tmp_path: Path) -> None:
    right = check_balance(CheckBalanceInput(["C3H8", "O2"], ["CO2", "H2O"], [1, 5], [3, 4]), tmp_path)
    assert right.balanced is True and right.gcd == 1
    assert [(row.element, row.left, row.right, row.difference) for row in right.elements] == [
        ("C", 3, 3, 0),
        ("H", 8, 8, 0),
        ("O", 10, 10, 0),
    ]
    doubled = check_balance(CheckBalanceInput(["C3H8", "O2"], ["CO2", "H2O"], [2, 10], [6, 8]), tmp_path)
    assert doubled.balanced is True and doubled.gcd == 2
    short = check_balance(CheckBalanceInput(["C3H8", "O2"], ["CO2", "H2O"], [1, 4], [3, 4]), tmp_path)
    assert short.balanced is False and [row.difference for row in short.elements] == [0, 0, -2]


def test_boundary_check_balance_counts_charge(tmp_path: Path) -> None:
    """MnO4^- + Fe^2+ + 8 H^+ -> Mn^2+ + Fe^3+ + 4 H2O conserves every atom but not the charge (9 vs 5)."""
    value = CheckBalanceInput(PERMANGANATE["reactants"], PERMANGANATE["products"], [1, 1, 8], [1, 1, 4])
    made = check_balance(value, tmp_path)
    assert all(row.difference == 0 for row in made.elements)
    assert (made.charge_left, made.charge_right, made.balanced) == (9, 5, False)


@pytest.mark.parametrize(
    ("coefficients", "message"),
    [(([1], [3, 4]), "one coefficient per formula"), (([1, 0], [3, 4]), "positive integers")],
)
def test_malformed_check_balance_coefficients(tmp_path: Path, coefficients: tuple, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_balance(CheckBalanceInput(["C3H8", "O2"], ["CO2", "H2O"], *coefficients), tmp_path)


def test_correct_save_worksheet_writes_what_it_returns(tmp_path: Path) -> None:
    made = saved(PROPANE, tmp_path)
    assert made["path"].startswith("worksheets/CO2-from-C3H8-O2-") and made["path"].endswith(".json")
    assert json.loads((tmp_path / made["path"]).read_text(encoding="utf-8")) == made
    again = saved(PROPANE, tmp_path, theoretical_yield_g=8.2522)
    assert again["path"] == made["path"]  # saving again replaces the worksheet
    assert json.loads((tmp_path / made["path"]).read_text(encoding="utf-8"))["theoretical_yield_g"] == 8.2522


def test_boundary_worksheet_paths_tell_tasks_apart(tmp_path: Path) -> None:
    first = saved(PROPANE, tmp_path)["path"]
    other = PROPANE | {"given": [{"formula": "C3H8", "grams": 10.0}, {"formula": "O2", "grams": 20.0}]}
    assert saved(other, tmp_path)["path"] != first
    ions = saved(PERMANGANATE, tmp_path)["path"]
    assert ions.startswith("worksheets/H2O-from-MnO4_m-Fe_2p-H_p-")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"reactant_coefficients": [1]}, "one coefficient per formula"),
        ({"product_coefficients": [3, 0]}, "positive integers"),
        ({"limiting": []}, "at least one"),
        ({"limiting": ["CO2"]}, "not a given reactant"),
        ({"limiting": ["O2", "O2"]}, "twice"),
        ({"theoretical_yield_g": -1.0}, "positive number"),
        ({"theoretical_yield_g": float("nan")}, "positive number"),
        ({"target": "CO"}, "not one of the products"),
    ],
)
def test_malformed_save_worksheet_shapes(tmp_path: Path, changes: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        save_worksheet(build_output(answer(PROPANE, **changes), WorksheetInput), tmp_path)
    assert not (tmp_path / "worksheets").exists()


def test_correct_outputs_round_trip_through_their_classes(tmp_path: Path) -> None:
    """Every output, floats like 2.0 included, is JSON its contract class builds back unchanged."""
    ions = PERMANGANATE | {"target": "Fe^3+"}  # MnO4^- limits at extent 0.01: 0.01 x 5 x 55.845 = 2.79225 g
    outputs = [
        (parse_formula(ParseFormulaInput(formulas=["Fe^2+", "Fe^3+"]), tmp_path), ParseFormulaOutput),
        (check_balance(CheckBalanceInput(["H2", "O2"], ["H2O"], [2, 1], [2]), tmp_path), CheckBalanceOutput),
        (pin_yield(build_output(ions, ReactionInput), tmp_path), PinnedYieldOutput),
        (
            save_worksheet(build_output(answer(PROPANE, theoretical_yield_g=2.0), WorksheetInput), tmp_path),
            WorksheetOutput,
        ),
    ]
    for output, cls in outputs:
        assert build_output(json.loads(json.dumps(plain_output(output))), cls) == output
