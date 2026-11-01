"""The verifier on contract instances, as NanoAgent's sandbox builds them from JSON: correct answers pass;
wrong, missing and malformed ones fail a named check (and never raise); boundary cases are judged exactly."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from helpers import (
    PERMANGANATE,
    PROPANE,
    WATER_TIE,
    answer,
    failing,
    judge,
    pinned,
    saved,
    task,
    unchecked,
    verify_input,
    verify_output,
)
from slimconfig import build_output, plain_output

import verifier
from contract import CheckBalanceInput, ParseFormulaInput, ParseFormulaOutput
from plugin import check_balance, parse_formula

CHECKS = [
    "task-input",
    "reference",
    "echo",
    "saved",
    "file-matches",
    "coefficients-form",
    "elements-balanced",
    "charge-balanced",
    "coefficients",
    "limiting",
    "yield",
]


# --- correct -------------------------------------------------------------------------------------------


def test_correct_propane_worksheet_holds_every_check(tmp_path: Path) -> None:
    verdict = judge(PROPANE, saved(PROPANE, tmp_path), tmp_path)
    assert verdict["valid"] is True and verdict["score"] == 1.0
    assert [entry["id"] for entry in verdict["details"]["checks"]] == CHECKS
    assert verdict["message"] == "All 11 checks hold: limiting O2, yield 8.2522 g"
    assert verdict["details"]["exact_yield"] == "44009/5333"


def test_correct_four_significant_figures_and_a_second_save(tmp_path: Path) -> None:
    saved(PROPANE, tmp_path, limiting=["C3H8"])
    verdict = judge(PROPANE, saved(PROPANE, tmp_path, theoretical_yield_g=8.252), tmp_path)
    assert verdict["valid"] is True


def test_correct_verdict_is_deterministic(tmp_path: Path) -> None:
    output = saved(PROPANE, tmp_path)
    first, second = judge(PROPANE, output, tmp_path), judge(PROPANE, output, tmp_path)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_correct_tool_outputs_pass_their_checks(tmp_path: Path) -> None:
    formulas = {"formulas": ["K4[Fe(CN)6]", "CuSO4·5H2O", "MnO4^-"]}
    parsed = plain_output(parse_formula(build_output(formulas, ParseFormulaInput), tmp_path))
    assert verify_input("parse_formula", formulas)["valid"] is True
    assert verify_output("parse_formula", formulas, parsed, tmp_path)["valid"] is True
    task_verdict = verifier.verify_task(
        "parse-formula",
        build_output(formulas, ParseFormulaInput),
        build_output(parsed, ParseFormulaOutput),
        None,
        str(tmp_path),
    )
    assert task_verdict["valid"] is True
    balance = {
        "reactants": ["C3H8", "O2"],
        "products": ["CO2", "H2O"],
        "reactant_coefficients": [1, 5],
        "product_coefficients": [3, 4],
    }
    made = plain_output(check_balance(build_output(balance, CheckBalanceInput), tmp_path))
    assert verify_output("check_balance", balance, made, tmp_path)["valid"] is True
    assert verify_output("save_worksheet", answer(PROPANE), saved(PROPANE, tmp_path), tmp_path)["valid"] is True
    assert verify_output("pin_yield", PROPANE, pinned(PROPANE), tmp_path)["valid"] is True


# --- incorrect -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "fails"),
    [
        ({"reactant_coefficients": [2, 10], "product_coefficients": [6, 8]}, ["coefficients-form", "coefficients"]),
        ({"product_coefficients": [3, 3]}, ["elements-balanced", "coefficients"]),
        ({"reactant_coefficients": [5, 1]}, ["elements-balanced", "coefficients"]),
        ({"limiting": ["C3H8"]}, ["limiting"]),
        ({"limiting": ["C3H8", "O2"]}, ["limiting"]),
        ({"theoretical_yield_g": 8.27}, ["yield"]),  # 0.216% high
        ({"theoretical_yield_g": 29.9399}, ["yield"]),  # from C3H8's extent: the wrong limiting reagent
        ({"theoretical_yield_g": 4.50403}, ["yield"]),  # H2O's yield: the wrong product
    ],
)
def test_incorrect_answers_fail_their_check(tmp_path: Path, changes: dict, fails: list) -> None:
    verdict = judge(PROPANE, saved(PROPANE, tmp_path, **changes), tmp_path)
    assert verdict["valid"] is False and failing(verdict) == fails
    assert verdict["message"].startswith(fails[0] + ": ")
    assert verdict["score"] == pytest.approx((11 - len(fails)) / 11)


def test_incorrect_charge_not_conserved(tmp_path: Path) -> None:
    verdict = judge(
        PERMANGANATE,
        saved(PERMANGANATE, tmp_path, reactant_coefficients=[1, 1, 8], product_coefficients=[1, 1, 4]),
        tmp_path,
    )
    assert failing(verdict) == ["charge-balanced", "coefficients"]
    assert "total charge is 9 on the left but 5 on the right" in verdict["message"]


def test_incorrect_tie_listed_in_the_wrong_order(tmp_path: Path) -> None:
    verdict = judge(WATER_TIE, saved(WATER_TIE, tmp_path, limiting=["O2", "H2"]), tmp_path)
    assert failing(verdict) == ["limiting"] and "['H2', 'O2']" in verdict["message"]


def test_incorrect_submission_differs_from_the_saved_file(tmp_path: Path) -> None:
    output = saved(PROPANE, tmp_path) | {"theoretical_yield_g": 8.2523}
    verdict = judge(PROPANE, output, tmp_path)
    assert failing(verdict) == ["file-matches"] and "theoretical_yield_g" in verdict["message"]


def test_incorrect_tampered_file(tmp_path: Path) -> None:
    output = saved(PROPANE, tmp_path)
    file = tmp_path / output["path"]
    file.write_text(json.dumps(output | {"limiting": ["C3H8"]}), encoding="utf-8")
    assert failing(judge(PROPANE, output, tmp_path)) == ["file-matches"]


def test_incorrect_echo_of_the_task(tmp_path: Path) -> None:
    output = saved(PROPANE, tmp_path) | {"reactants": ["O2", "C3H8"]}
    assert failing(judge(PROPANE, output, tmp_path)) == ["echo", "file-matches"]


def test_incorrect_worksheet_of_another_task(tmp_path: Path) -> None:
    other = PROPANE | {"given": [{"formula": "O2", "grams": 10.0}]}
    output = saved(other, tmp_path)  # right for the other task, saved under its own path
    verdict = judge(PROPANE, output, tmp_path)
    assert failing(verdict) == ["saved"] and "where save_worksheet saves this task's worksheet" in verdict["message"]


# --- missing -------------------------------------------------------------------------------------------


def test_missing_worksheet_file(tmp_path: Path) -> None:
    output = saved(PROPANE, tmp_path / "elsewhere")  # saved in another workspace: none here
    verdict = judge(PROPANE, output, tmp_path)
    assert failing(verdict) == ["saved"] and "no worksheet at worksheets/" in verdict["message"]
    assert unchecked(verdict) == ["file-matches"]


def test_missing_reference(tmp_path: Path) -> None:
    verdict = judge(PROPANE, saved(PROPANE, tmp_path), tmp_path, reference=None)
    assert verdict["valid"] is False and failing(verdict) == ["reference"]
    assert unchecked(verdict) == ["coefficients", "limiting", "yield"]
    assert verdict["message"] == "reference: no answer key: pin_yield was not pinned for this task"


def test_missing_tied_reagent(tmp_path: Path) -> None:
    verdict = judge(WATER_TIE, saved(WATER_TIE, tmp_path, limiting=["H2"]), tmp_path)
    assert failing(verdict) == ["limiting"]


def test_missing_coefficient_and_empty_answer(tmp_path: Path) -> None:
    output = saved(PROPANE, tmp_path)
    short = judge(PROPANE, output | {"product_coefficients": [3]}, tmp_path)
    assert failing(short) == ["file-matches", "coefficients-form", "coefficients"]
    assert unchecked(short) == ["elements-balanced", "charge-balanced"]
    empty = output | {"reactant_coefficients": [], "product_coefficients": [], "limiting": []}
    assert failing(judge(PROPANE, empty, tmp_path)) == ["file-matches", "coefficients-form", "coefficients", "limiting"]


# --- malformed -----------------------------------------------------------------------------------------

REFUSED_INPUTS = [
    (task(["C3H8", "Xx2"], ["CO2"], {"C3H8": 1.0}, "CO2"), "unknown element 'Xx'"),
    (task(["C3H8", "O2"], ["CO2", "H2O)"], {"C3H8": 1.0}, "CO2"), "closes no matching bracket"),
    (task(["Ca3(PO4", "O2"], ["CO2"], {"O2": 1.0}, "CO2"), "never closed"),
    (task(["C3H8", "O2"], ["CO2", "2H2O"], {"C3H8": 1.0}, "CO2"), "starts with a number"),
    (task(["C3H8", "O2"], ["CO2"], {"C3H8": 0.0}, "CO2"), "positive number of grams"),
    (task(["C3H8", "O2"], ["CO2"], {"C3H8": -2.0}, "CO2"), "positive number of grams"),
    (task(["C3H8", "O2"], ["CO2"], {"C3H8": math.nan}, "CO2"), "positive number of grams"),
    (task(["C3H8", "O2"], ["CO2"], {"C3H8": math.inf}, "CO2"), "positive number of grams"),
    (task(["C3H8", "O2"], ["CO2"], {"C3H8": 1e7}, "CO2"), "from 0.000001 to 1000000 g"),
    (task(["C3H8", "O2"], ["CO2"], {"CO2": 1.0}, "CO2"), "is not one of the reactants"),
    (task(["C3H8", "O2"], ["CO2"], {"c3h8": 1.0}, "CO2"), "is not one of the reactants"),
    (task(["C3H8", "O2"], ["CO2"], {}, "CO2"), "at least one reactant"),
    (task(["C3H8", "O2"], ["CO2"], {"O2": 1.0}, "H2O"), "is not one of the products"),
    (task([], ["CO2"], {}, "CO2"), "reactants must list 1 to 6"),
    (task(["O2"], [], {"O2": 1.0}, "CO2"), "products must list 1 to 6"),
    (task(["C3H8", "O2", "O2"], ["CO2"], {"O2": 1.0}, "CO2"), "duplicate species among the reactants"),
    (task(["C2H6O", "CH3OCH3"], ["CO2"], {"C2H6O": 1.0}, "CO2"), "duplicate species among the reactants"),
    (task(["H2O", "O2"], ["H2O", "H2O2"], {"O2": 1.0}, "H2O2"), "a species on both sides"),
    (task(["H", "He", "Li", "Be", "B", "C", "N"], ["CO2"], {"C": 1.0}, "CO2"), "reactants must list 1 to 6"),
]


@pytest.mark.parametrize(("arguments", "message"), REFUSED_INPUTS)
def test_malformed_task_inputs_are_refused_before_any_agent(arguments: dict, message: str) -> None:
    """verify_input on pin_yield refuses them, so the task never starts; the tool itself refuses them too."""
    verdict = verify_input("pin_yield", arguments)
    assert verdict["valid"] is False and message in verdict["message"]
    assert verify_input("save_worksheet", answer(PROPANE) | arguments)["valid"] is False
    with pytest.raises(ValueError):
        pinned(arguments)


def test_malformed_duplicate_given_is_refused() -> None:
    arguments = task(["C3H8", "O2"], ["CO2"], {"C3H8": 1.0}, "CO2")
    arguments["given"].append({"formula": "C3H8", "grams": 2.0})
    assert "duplicate given" in verify_input("pin_yield", arguments)["message"]
    assert (
        "duplicate given" in verify_input("save_worksheet", answer(PROPANE) | {"given": arguments["given"]})["message"]
    )


@pytest.mark.parametrize(
    ("tool", "value", "message"),
    [
        ("parse_formula", {"formulas": []}, "1 to 12"),
        ("parse_formula", {"formulas": ["H2O"] * 13}, "1 to 12"),
        ("parse_formula", {"formulas": ["H2O", "Fe^0+"]}, "malformed formula 'Fe^0+'"),
        (
            "check_balance",
            {"reactants": ["H2"], "products": ["H2O"], "reactant_coefficients": [1, 1], "product_coefficients": [1]},
            "one coefficient per formula",
        ),
        (
            "check_balance",
            {"reactants": ["H2"], "products": ["H2O"], "reactant_coefficients": [0], "product_coefficients": [1]},
            "positive integers",
        ),
        (
            "check_balance",
            {"reactants": ["H2O"], "products": ["H2O"], "reactant_coefficients": [1], "product_coefficients": [1]},
            "both sides",
        ),
        ("save_worksheet", answer(PROPANE, limiting=["CO2"]), "not a given reactant"),
        ("save_worksheet", answer(PROPANE, theoretical_yield_g=math.inf), "positive number"),
        ("save_worksheet", answer(PROPANE, product_coefficients=[3, 4, 1]), "one coefficient per formula"),
    ],
)
def test_malformed_tool_inputs_are_refused(tool: str, value: dict, message: str) -> None:
    verdict = verify_input(tool, value)
    assert verdict["valid"] is False and message in verdict["message"]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "is not JSON"),
        ("[1, 2]", "holds no JSON object"),
        ("x" * 70_000, "more than any worksheet"),
    ],
)
def test_malformed_worksheet_files(tmp_path: Path, content: str, message: str) -> None:
    output = saved(PROPANE, tmp_path)
    (tmp_path / output["path"]).write_text(content, encoding="utf-8")
    verdict = judge(PROPANE, output, tmp_path)
    assert failing(verdict) == ["saved"] and message in verdict["message"]


@pytest.mark.parametrize("path", ["../outside.json", "/etc/passwd", "", "worksheets/../../x.json", "answer.json"])
def test_malformed_paths_never_leave_the_workspace(tmp_path: Path, path: str) -> None:
    verdict = judge(PROPANE, saved(PROPANE, tmp_path) | {"path": path}, tmp_path)
    assert failing(verdict)[:1] == ["saved"] and verdict["valid"] is False


@pytest.mark.parametrize("value", [math.nan, math.inf, -8.2522, 0.0])
def test_malformed_yield_values_fail_without_raising(tmp_path: Path, value: float) -> None:
    verdict = judge(PROPANE, saved(PROPANE, tmp_path) | {"theoretical_yield_g": value}, tmp_path)
    assert "yield" in failing(verdict)
    json.dumps(verdict, allow_nan=False)  # the verdict is plain JSON, no NaN


@pytest.mark.parametrize(
    "changes",
    [
        {"theoretical_yield_exact": "44010/5333"},
        {"theoretical_yield_g": 8.3},
        {"limiting": ["C3H8"]},
        {"reactant_coefficients": [2, 10], "product_coefficients": [6, 8]},
        {
            "atomic_weights": [
                {"element": "C", "weight": "12.000"},
                {"element": "H", "weight": "1.0080"},
                {"element": "O", "weight": "15.999"},
            ]
        },
        {"data_sha256": "not a hash"},
        {"given": []},
        {"theoretical_yield_exact": "abc"},
    ],
)
def test_malformed_reference_is_caught_by_rederiving_it(tmp_path: Path, changes: dict) -> None:
    """A wrong answer key is never trusted: re-deriving it with the verifier's own parser catches it."""
    output = saved(PROPANE, tmp_path)
    verdict = judge(PROPANE, output, tmp_path, reference=pinned(PROPANE) | changes)
    assert failing(verdict) == ["reference"] and "the answer key is inconsistent" in verdict["message"]
    assert verify_output("pin_yield", PROPANE, pinned(PROPANE) | changes, tmp_path)["valid"] is False


def test_malformed_tool_outputs_are_refused(tmp_path: Path) -> None:
    formulas = {"formulas": ["CO", "Co"]}
    made = {
        "species": [
            {
                "formula": "CO",
                "normalized": "CO",
                "elements": [{"element": "Co", "count": 1}],
                "charge": 0,
                "molar_mass": 58.933,
            },
            {
                "formula": "Co",
                "normalized": "Co",
                "elements": [{"element": "Co", "count": 1}],
                "charge": 0,
                "molar_mass": 58.933,
            },
        ],
        "atomic_weights": [{"element": "Co", "weight": "58.933"}],
    }
    assert verify_output("parse_formula", formulas, made, tmp_path)["valid"] is False
    balance = {
        "reactants": ["H2", "O2"],
        "products": ["H2O"],
        "reactant_coefficients": [2, 1],
        "product_coefficients": [2],
    }
    lying = {
        "elements": [
            {"element": "H", "left": 4, "right": 4, "difference": 0},
            {"element": "O", "left": 2, "right": 2, "difference": 0},
        ],
        "charge_left": 0,
        "charge_right": 0,
        "balanced": True,
        "gcd": 2,
    }
    assert "gcd must be 1" in verify_output("check_balance", balance, lying, tmp_path)["message"]
    output = saved(PROPANE, tmp_path)
    (tmp_path / output["path"]).write_text("{}", encoding="utf-8")
    assert verify_output("save_worksheet", answer(PROPANE), output, tmp_path)["valid"] is False


def test_malformed_task_input_reaches_verify_task_without_raising(tmp_path: Path) -> None:
    arguments = task(["C3H8", "Xx"], ["CO2"], {"C3H8": 1.0}, "CO2")
    output = {
        "reactants": ["C3H8", "Xx"],
        "products": ["CO2"],
        "reactant_coefficients": [1, 1],
        "product_coefficients": [1],
        "limiting": ["C3H8"],
        "theoretical_yield_g": 1.0,
        "path": "worksheets/x.json",
    }
    verdict = judge(arguments, output, tmp_path, reference=None)
    assert failing(verdict) == ["task-input", "reference"] and verdict["score"] == pytest.approx(1 / 11)


# --- boundary ------------------------------------------------------------------------------------------

BOUNDARY = {
    "ions": PERMANGANATE,
    "hydrate": task(["CuSO4*5H2O"], ["CuSO4", "H2O"], {"CuSO4*5H2O": 24.9677}, "H2O"),
    "nested": task(
        ["K4[Fe(CN)6]", "H2SO4", "H2O"], ["K2SO4", "FeSO4", "(NH4)2SO4", "CO"], {"K4[Fe(CN)6]": 3.68345}, "CO"
    ),
    "large-coefficients": task(["C57H110O6", "O2"], ["CO2", "H2O"], {"C57H110O6": 8.91501, "O2": 100.0}, "CO2"),
    "cobalt-vs-CO": task(["Co2(CO)8"], ["Co", "CO"], {"Co2(CO)8": 3.41946}, "CO"),
    "tie": WATER_TIE,
    "one-given": task(["N2", "H2"], ["NH3"], {"H2": 6.048}, "NH3"),
    "tiny-mass": task(["C3H8", "O2"], ["CO2", "H2O"], {"C3H8": 0.00044097}, "CO2"),
    "phosphate": task(["Ca3(PO4)2", "SiO2", "C"], ["CaSiO3", "P4", "CO"], {"Ca3(PO4)2": 31.0174, "C": 12.011}, "P4"),
}


@pytest.mark.parametrize("name", sorted(BOUNDARY))
def test_boundary_cases_pass_when_right(tmp_path: Path, name: str) -> None:
    arguments = BOUNDARY[name]
    assert judge(arguments, saved(arguments, tmp_path), tmp_path)["valid"] is True


def test_boundary_golden_answers_by_hand(tmp_path: Path) -> None:
    """Ca3(PO4)2 0.1 mol (extent 0.05) vs C 1 mol (extent 0.1): P4 = 0.05 x 123.896 = 6.1948 g. Co2(CO)8
    0.01 mol: CO = 0.08 x 28.010 = 2.2408 g. K4[Fe(CN)6] 0.01 mol: CO = 0.06 x 28.010 = 1.6806 g."""
    assert pinned(BOUNDARY["phosphate"])["theoretical_yield_exact"] == "15487/2500"
    assert pinned(BOUNDARY["cobalt-vs-CO"])["theoretical_yield_exact"] == "2801/1250"
    assert pinned(BOUNDARY["nested"])["theoretical_yield_exact"] == "8403/5000"


@pytest.mark.parametrize(("factor", "valid"), [(1.00099, True), (0.99901, True), (1.00101, False), (0.99899, False)])
def test_boundary_yield_tolerance_is_one_part_per_thousand(tmp_path: Path, factor: float, valid: bool) -> None:
    exact = 44009 / 5333
    verdict = judge(PROPANE, saved(PROPANE, tmp_path, theoretical_yield_g=exact * factor), tmp_path)
    assert verdict["valid"] is valid


def test_boundary_coefficient_order_follows_the_input(tmp_path: Path) -> None:
    flipped = PROPANE | {"reactants": ["O2", "C3H8"]}
    assert pinned(flipped)["reactant_coefficients"] == [5, 1]
    assert judge(flipped, saved(flipped, tmp_path), tmp_path)["valid"] is True
    assert failing(judge(flipped, saved(flipped, tmp_path, reactant_coefficients=[1, 5]), tmp_path)) == [
        "elements-balanced",
        "coefficients",
    ]


def test_malformed_parse_formula_task_input_does_not_raise(tmp_path: Path) -> None:
    """The parse-formula task is judged by verify_output, which must refuse, not raise, on a bad input."""
    made = {"species": [], "atomic_weights": []}
    verdict = verifier.verify_task(
        "parse-formula",
        build_output({"formulas": ["Xx"]}, ParseFormulaInput),
        build_output(made, ParseFormulaOutput),
        None,
        str(tmp_path),
    )
    assert verdict["valid"] is False and "unknown element" in verdict["message"]
    bad = {"reactants": ["H2"], "products": ["H2O"], "reactant_coefficients": [], "product_coefficients": [1]}
    lying = {"elements": [], "charge_left": 0, "charge_right": 0, "balanced": True, "gcd": 1}
    assert verify_output("check_balance", bad, lying, tmp_path)["valid"] is False
