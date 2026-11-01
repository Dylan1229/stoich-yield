"""Building tool and verifier arguments as NanoAgent does: JSON built into contract classes."""

from __future__ import annotations

from pathlib import Path

from slimconfig import build_output, plain_output

import verifier
from contract import TASKS, TOOLS, PinnedYieldOutput, ReactionInput, Task, Tool, WorksheetInput, WorksheetOutput
from plugin import pin_yield, save_worksheet


def task(reactants: list[str], products: list[str], given: dict[str, float], target: str) -> dict:
    return {
        "reactants": reactants,
        "products": products,
        "given": [{"formula": formula, "grams": grams} for formula, grams in given.items()],
        "target": target,
    }


PROPANE = task(["C3H8", "O2"], ["CO2", "H2O"], {"C3H8": 10.0, "O2": 10.0}, "CO2")
WATER_TIE = task(["H2", "O2"], ["H2O"], {"H2": 4.032, "O2": 31.998}, "H2O")
PERMANGANATE = task(["MnO4^-", "Fe^2+", "H^+"], ["Mn^2+", "Fe^3+", "H2O"], {"MnO4^-": 1.18934, "Fe^2+": 5.5845}, "H2O")


def pinned(arguments: dict) -> dict:
    """pin_yield's output as NanoAgent pins it: JSON."""
    return plain_output(pin_yield(build_output(arguments, ReactionInput), Path(".")))


def answer(arguments: dict, **changes) -> dict:
    """The right answer as an agent would save it (the yield to 6 significant figures), with ``changes``."""
    key = pinned(arguments)
    right = {
        "reactant_coefficients": key["reactant_coefficients"],
        "product_coefficients": key["product_coefficients"],
        "limiting": key["limiting"],
        "theoretical_yield_g": float(f"{key['theoretical_yield_g']:.6g}"),
    }
    return arguments | right | changes


def saved(arguments: dict, workspace: Path, **changes) -> dict:
    """save_worksheet's output, as JSON, for the answer with ``changes``."""
    return plain_output(save_worksheet(build_output(answer(arguments, **changes), WorksheetInput), workspace))


def judge(arguments: dict, output: dict, workspace: Path, reference: dict | None | str = "pin") -> dict:
    """verify_task's verdict on ``output``, against the pinned answer key unless ``reference`` is given."""
    key = pinned(arguments) if reference == "pin" else reference
    return verifier.verify_task(
        "balance-and-yield",
        build_output(arguments, TASKS[Task.BALANCE_AND_YIELD][0]),
        build_output(output, WorksheetOutput),
        None if key is None else build_output(key, PinnedYieldOutput),
        str(workspace),
    )


def verify_input(tool: str, value: dict) -> dict:
    return verifier.verify_input(tool, build_output(value, TOOLS[Tool(tool)][0]))


def verify_output(tool: str, given: dict, made: dict, workspace: Path) -> dict:
    given_class, made_class = TOOLS[Tool(tool)]
    return verifier.verify_output(
        tool, build_output(given, given_class), build_output(made, made_class), str(workspace)
    )


def failing(verdict: dict) -> list[str]:
    """The ids of the checks that fail."""
    return [entry["id"] for entry in verdict["details"]["checks"] if entry["ok"] is False]


def unchecked(verdict: dict) -> list[str]:
    return [entry["id"] for entry in verdict["details"]["checks"] if entry["ok"] is None]
