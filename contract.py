"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    PARSE_FORMULA = "parse_formula"
    CHECK_BALANCE = "check_balance"
    SAVE_WORKSHEET = "save_worksheet"
    PIN_YIELD = "pin_yield"


class Task(Enum):
    PARSE_FORMULA = "parse-formula"
    BALANCE_AND_YIELD = "balance-and-yield"


FORMULAS = (
    "1 to 12 formulas to parse. A formula has no spaces: case-sensitive element symbols (Co is cobalt, CO is"
    " carbon and oxygen), each with an optional positive integer count; groups in () or [] may nest and take a"
    " count, e.g. Ca3(PO4)2,"
    " K4[Fe(CN)6]; hydrate parts are joined by * or ·, and a later part may start with a count, e.g. CuSO4*5H2O;"
    " an optional charge suffix ends it: ^+, ^-, ^2+, ^3-, e.g. Fe^3+, MnO4^-, SO4^2-. No phases, no electrons,"
    " no leading coefficient (H2O, not 2H2O)"
)
REACTANTS = (
    "The reactants' formulas, 1 to 6, all different, none also a product; each in parse_formula's grammar, e.g."
    " C3H8, CuSO4*5H2O, K4[Fe(CN)6], MnO4^-"
)
PRODUCTS = (
    "The products' formulas, 1 to 6, all different, none also a reactant; each in parse_formula's grammar, e.g."
    " CO2, H2O, Mn^2+"
)
REACTANT_COEFFICIENTS = "One positive integer per reactant, in the order of reactants"
PRODUCT_COEFFICIENTS = "One positive integer per product, in the order of products"
GIVEN = "The reactants whose mass is known, at least one; every other reactant is in excess"
TARGET = "The product whose theoretical yield is asked for, spelled exactly as in products"
LIMITING = (
    "The limiting reagent(s): the given reactant(s) with the smallest moles / coefficient, every tied one listed,"
    " in the order of reactants, spelled exactly as there"
)
YIELD = "The target's theoretical yield in grams, at least 4 significant figures"
WORKSHEET_PATH = "The saved worksheet, worksheets/<slug>.json, relative to the plugin workspace"
ELEMENTS = "Atoms per element, one entry per element present, sorted by symbol"
MOLAR_MASS = "g/mol: the sum of count x standard atomic weight over the elements (exact, shown as a float)"


@dataclass
class ElementCount(Output):
    element: Annotated[str, "An element symbol, as in the atomic weight table"]
    count: Annotated[int, "How many atoms of it one formula unit holds, hydrate parts and groups multiplied out"]


@dataclass
class AtomicWeight(Output):
    element: Annotated[str, "An element symbol"]
    weight: Annotated[str, "Its standard atomic weight in g/mol, the table's decimal text, e.g. 12.011"]


@dataclass
class ParsedFormula(Output):
    formula: Annotated[str, "The formula, as given"]
    normalized: Annotated[str, "The formula normalized: · as *, counts and multipliers of 1 dropped, ^1+ as ^+"]
    elements: Annotated[list[ElementCount], ELEMENTS]
    charge: Annotated[int, "The charge in elementary charges, 0 without a suffix"]
    molar_mass: Annotated[float, MOLAR_MASS]


@dataclass
class ParseFormulaInput(Output):
    formulas: Annotated[list[str], FORMULAS]


@dataclass
class ParseFormulaOutput(Output):
    species: Annotated[list[ParsedFormula], "One entry per formula, in the order given"]
    atomic_weights: Annotated[list[AtomicWeight], "The table's weight of every element present, sorted by symbol"]


@dataclass
class CheckBalanceInput(Output):
    reactants: Annotated[list[str], REACTANTS]
    products: Annotated[list[str], PRODUCTS]
    reactant_coefficients: Annotated[list[int], REACTANT_COEFFICIENTS]
    product_coefficients: Annotated[list[int], PRODUCT_COEFFICIENTS]


@dataclass
class ElementBalance(Output):
    element: Annotated[str, "An element symbol"]
    left: Annotated[int, "Its atoms on the reactant side: the sum of coefficient x count"]
    right: Annotated[int, "Its atoms on the product side: the sum of coefficient x count"]
    difference: Annotated[int, "left - right; 0 when the element is conserved"]


@dataclass
class CheckBalanceOutput(Output):
    elements: Annotated[list[ElementBalance], "One entry per element present, sorted by symbol"]
    charge_left: Annotated[int, "The reactant side's total charge: the sum of coefficient x charge"]
    charge_right: Annotated[int, "The product side's total charge: the sum of coefficient x charge"]
    balanced: Annotated[bool, "Whether every element and the charge are conserved"]
    gcd: Annotated[int, "The greatest common divisor of all the coefficients; the smallest integers have gcd 1"]


@dataclass
class GivenMass(Output):
    formula: Annotated[str, "A reactant, spelled exactly as in reactants, each at most once"]
    grams: Annotated[float, "Its mass in grams, from 0.000001 to 1000000; read as the decimal it is written as"]


@dataclass
class ReactionInput(Output):
    reactants: Annotated[list[str], REACTANTS]
    products: Annotated[list[str], PRODUCTS]
    given: Annotated[list[GivenMass], GIVEN]
    target: Annotated[str, TARGET]


@dataclass
class WorksheetInput(Output):
    reactants: Annotated[list[str], "The task's reactants, exactly as given"]
    products: Annotated[list[str], "The task's products, exactly as given"]
    given: Annotated[list[GivenMass], "The task's given masses, exactly as given"]
    target: Annotated[str, "The task's target, exactly as given"]
    reactant_coefficients: Annotated[list[int], REACTANT_COEFFICIENTS]
    product_coefficients: Annotated[list[int], PRODUCT_COEFFICIENTS]
    limiting: Annotated[list[str], LIMITING]
    theoretical_yield_g: Annotated[float, YIELD]


@dataclass
class WorksheetOutput(Output):
    reactants: Annotated[list[str], "The task's reactants, as given"]
    products: Annotated[list[str], "The task's products, as given"]
    reactant_coefficients: Annotated[list[int], REACTANT_COEFFICIENTS]
    product_coefficients: Annotated[list[int], PRODUCT_COEFFICIENTS]
    limiting: Annotated[list[str], LIMITING]
    theoretical_yield_g: Annotated[float, YIELD]
    path: Annotated[str, WORKSHEET_PATH]


@dataclass
class PinnedSpecies(Output):
    formula: Annotated[str, "The formula, as given"]
    elements: Annotated[list[ElementCount], ELEMENTS]
    charge: Annotated[int, "The charge in elementary charges"]
    molar_mass: Annotated[float, MOLAR_MASS]
    molar_mass_exact: Annotated[str, "The molar mass in g/mol as an exact decimal"]


@dataclass
class PinnedGiven(Output):
    formula: Annotated[str, "A given reactant, as given"]
    grams: Annotated[float, "Its mass in grams, as given"]
    grams_exact: Annotated[str, "The mass as the exact decimal it is written as"]
    moles: Annotated[float, "grams / molar mass"]
    extent: Annotated[float, "moles / its coefficient"]
    extent_exact: Annotated[str, "The extent as an exact fraction, p/q"]


@dataclass
class PinnedYieldOutput(Output):
    reactants: Annotated[list[PinnedSpecies], "The reactants, in input order"]
    products: Annotated[list[PinnedSpecies], "The products, in input order"]
    reactant_coefficients: Annotated[list[int], REACTANT_COEFFICIENTS]
    product_coefficients: Annotated[list[int], PRODUCT_COEFFICIENTS]
    given: Annotated[list[PinnedGiven], "The given reactants, in the task's order"]
    limiting: Annotated[list[str], LIMITING]
    target: Annotated[str, TARGET]
    theoretical_yield_g: Annotated[float, "The exact theoretical yield in grams, as a float"]
    theoretical_yield_exact: Annotated[str, "The theoretical yield in grams as an exact fraction, p/q"]
    atomic_weights: Annotated[list[AtomicWeight], "The table's weight of every element present, sorted by symbol"]
    data_sha256: Annotated[str, "The sha256 of the atomic weight table file the answer was computed from"]


TOOLS = {
    Tool.PARSE_FORMULA: (ParseFormulaInput, ParseFormulaOutput),
    Tool.CHECK_BALANCE: (CheckBalanceInput, CheckBalanceOutput),
    Tool.SAVE_WORKSHEET: (WorksheetInput, WorksheetOutput),
    Tool.PIN_YIELD: (ReactionInput, PinnedYieldOutput),
}
TASKS = {
    Task.PARSE_FORMULA: (ParseFormulaInput, ParseFormulaOutput),
    Task.BALANCE_AND_YIELD: (ReactionInput, WorksheetOutput),
}
