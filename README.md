# Stoichiometry Yield

A `nanoagent.plugin/v0001` plugin with the structure of NanoAgent's reference plugin,
[arxiv-source](https://github.com/zeyuyang8/arxiv-source). Its task, `balance-and-yield`, gives an agent a
chemical reaction (its reactants and products as formulas), the mass in grams of one or more reactants, and a
target product. The agent must balance the equation, find the limiting reagent(s) and compute the target's
theoretical yield in grams. The tools parse formulas and check a balancing but solve nothing; the answer key
solves the reaction exactly with rational arithmetic, and the verifier re-derives both the answer key and the
agent's balance with a formula parser of its own. Everything runs offline from one bundled table of IUPAC
standard atomic weights.

## Tools

| Tool | Does | Code |
|---|---|---|
| `parse_formula` | Parses 1 to 12 formulas in one call: each one's normalized form, atoms per element (sorted by symbol), charge and molar mass in g/mol, plus the table's weight of every element present | `src/plugin/formula.py` |
| `check_balance` | For given coefficients: each element's atoms on the left and right and their difference, both sides' total charge, `balanced` (every element and the charge conserved) and the `gcd` of all coefficients. It checks; it does not solve | `src/plugin/reaction.py` |
| `save_worksheet` | Saves the agent's answer as `worksheets/<slug>.json` in the workspace (saving again replaces it) and returns it with its `path`. It checks the answer's shape, never its values | `src/plugin/worksheet.py` |
| `pin_yield` | The answer key (a task's `reference`, never an agent's tool): the exact balancing, limiting reagent(s) and yield, every molar mass, and the sha256 of the weight table | `src/plugin/solver.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `balance-and-yield` | Balances a reaction, finds its limiting reagent(s) and the target product's theoretical yield | `agent`, with `parse_formula`, `check_balance` and `save_worksheet`; reference `pin_yield` |
| `parse-formula` | Parses chemical formulas into atoms, charge and molar mass (for chat) | `tool`, with `parse_formula` |

## The task

**Input** (`ReactionInput`): `reactants` (1 to 6 formulas), `products` (1 to 6 formulas), `given` (one or
more `{formula, grams}`; each formula one of the reactants, spelled exactly as there, at most once; grams
from 0.000001 to 1000000), `target` (one of the products, spelled exactly as there). Reactants without a
given mass are in excess. Example:

```json
{"reactants": ["C3H8", "O2"], "products": ["CO2", "H2O"],
 "given": [{"formula": "C3H8", "grams": 10.0}, {"formula": "O2", "grams": 10.0}], "target": "CO2"}
```

**Output** (`WorksheetOutput`, exactly what `save_worksheet` returns): `reactants` and `products` (echoed),
`reactant_coefficients` and `product_coefficients` (aligned with the input order), `limiting` (formulas),
`theoretical_yield_g` (a number) and `path`. For the example: `[1, 5]`, `[3, 4]`, `["O2"]`, `8.2522`,
`worksheets/CO2-from-C3H8-O2-1230fe3974.json`.

**The rules** (all stated in the task's instructions):

1. The coefficients are the unique smallest positive integers (gcd 1) that conserve every element and the
   total charge, one per species, in the input order of `reactants` and of `products`.
2. Molar masses are `parse_formula`'s `molar_mass` values (g/mol). For each given reactant, moles = grams /
   molar mass and its extent = moles / its coefficient.
3. The limiting reagent is the given reactant with the smallest extent; a reactant without a given mass is
   never limiting. When several given reactants have exactly equal extents, all of them are listed, in the
   order of `reactants`. Every accepted task keeps distinct extents more than 1% apart (see below), so extents
   within 1% of each other are a tie.
4. Theoretical yield = smallest extent x target coefficient x target molar mass, in grams. Report at least 4
   significant figures; it is accepted when |reported - exact| <= 0.1% of the exact value. The tolerance is
   there because the agent has no calculator: it divides and multiplies by hand from 5-significant-figure molar
   masses, and 4 significant figures alone carry up to 0.05% rounding error.
5. Given masses are read as the decimal they are written as (the JSON number's shortest form): `4.032` is
   exactly 4032/1000, so masses can be chosen to make extents exactly equal.

**The plan** the instructions prescribe fits RUSH Lab's limits (6 model turns, 2,048 tokens per reply):
turn 1, `parse_formula` with every species; turn 2, solve the coefficients by hand and `check_balance` them
(one spare turn to fix them); turn 3, compute the limiting reagent(s) and yield by hand and `save_worksheet`;
turn 4, `submit` exactly what `save_worksheet` returned. Tool outputs stay small (`parse_formula` on 6 species
is about 1 KB of JSON).

**Success**: the verdict is valid only when all 11 checks below hold.

## Formula grammar

```text
formula    := part (("*" | "·") [multiplier] part)* [charge]
part       := unit+
unit       := (symbol | "(" part ")" | "[" part "]") [count]
symbol     := uppercase letter + optional lowercase letter, an element of the table (case-sensitive)
count, multiplier := positive integer without leading zeros
charge     := "^" [positive integer] ("+" | "-")
```

So `Co` is cobalt and `CO` carbon monoxide; `Ca3(PO4)2` and `K4[Fe(CN)6]` nest groups; `CuSO4*5H2O` (or
`CuSO4·5H2O`) is a hydrate; `Fe^3+`, `MnO4^-` and `SO4^2-` are ions. No spaces, phases (`H2O(l)`), electrons
(`e^-`), leading coefficients (`2H2O`), unknown or weightless elements (`Xx`, `Tc`) or Unicode subscripts:
each is malformed. The normalized form writes `·` as `*`, drops counts and multipliers of 1, and writes `^1+`
as `^+`. A formula is at most 100 characters. Two formulas with the same atoms and charge are the same species.

## The answer key

`pin_yield` runs on the task input in a scratch workspace before the agent starts. It builds the matrix of
element counts plus a charge row (products negated), computes its rational nullspace by Fraction Gaussian
elimination, requires it to be one-dimensional with a strictly positive vector, and scales that vector to the
smallest integers. Molar masses are exact sums of count x weight from the table's decimal strings; moles,
extents and the yield are exact Fractions. Its output holds each species' atoms, charge and molar mass (float
and exact decimal), the coefficients, each given reactant's grams, moles and extent (float and exact
fraction), the limiting reagent(s), the yield (float and exact fraction `p/q`), the weights it used and the
table's `data_sha256`.

A task never starts when its input is refused, either by `verify_input` (every tool's) or by the answer key:

| Refused input | Example message |
|---|---|
| Unknown element, bad syntax, unbalanced brackets | `malformed formula 'Xx2': unknown element 'Xx'` |
| Zero, negative, NaN, infinite or out-of-range grams | `the mass of 'C3H8' must be a positive number of grams, not 0.0` |
| Given formula not a reactant / given twice / none given | `given formula 'CO2' is not one of the reactants (spell it as there)` |
| Target not a product | `target 'H2O' is not one of the products (spell it as there)` |
| Empty or over-long side, duplicate species, species on both sides | `a species on both sides: reactant 'H2O' and product 'H2O' have the same atoms and charge` |
| More than one independent balancing | `ambiguous: 2 independent balancings conserve every element and the charge, ...` |
| No positive balancing | `cannot be balanced with positive coefficients: the only balancing is CO2 1, CO 2, C -1` |
| Two distinct extents within 1% | `near tie: the extents (moles / coefficient) of 'H2' and 'O2' differ by only 0.319%; ...` |

The near-tie rule is this plugin's own: an agent working by hand cannot tell a 0.3% difference from a tie, so
such a task would not be fair. Exact ties are allowed and listed.

## Data

`src/plugin/data/atomic_weights.json`: the 84 elements up to uranium (92) that have a standard atomic weight
(Tc, Pm and Po to Ac have none), each with its number, symbol, name and weight as decimal text in g/mol. The
values are CIAAW's abridged standard atomic weights (2024 revision of the IUPAC Atomic Weights 2021 report,
which revised Zr, Gd and Lu), transcribed exactly as printed at
<https://www.ciaaw.org/abridged-atomic-weights.htm> on 2026-11-01, without uncertainties: e.g. H 1.0080
(= 1.008), C 12.011, N 14.007, O 15.999, Na 22.990, Cl 35.45. The file names its source and date. It was
written by hand, not generated; to change it, edit the file (the answer key's `data_sha256` then changes).

sha256: `ac39e59652b29872d2f8486bc4f2e0063a766fa3aee6cb384e6d555955eff306`

The verifier never reads this file: it re-derives every molar mass from the weights the answer key reports,
and holds its own list of the 84 symbols (`verifier/formula.py`); a test checks the two agree.

## Verifier

`verifier/task.py` judges a `balance-and-yield` submission with 11 named checks, in order. Each entry of
`details.checks` is `{id, ok, expected, actual, message}`; `ok` is `true`, `false`, or `null` (not checked
because a check it needs failed). The verdict is valid only when all 11 hold; the score is the share that
hold; the message is the first failing check, its reason and how many more fail.

| # | id | What it checks | Example failure message |
|---|---|---|---|
| 1 | `task-input` | The task input is valid, read with the verifier's own parser | `the task input is invalid: malformed formula 'Xx': unknown element 'Xx'` |
| 2 | `reference` | The answer key was pinned, and re-derives exactly: its atoms and charges equal the verifier's reading, its molar masses the sums of its weights, its coefficients balance with gcd 1, and its extents, limiting reagents and yield recompute from the task's grams | `the answer key is inconsistent: its limiting reagents ['C3H8'] are not the smallest extents' ['O2']` |
| 3 | `echo` | The submission's reactants and products are the task's, in order | `the submission's reactants and products are not the task's, in its order` |
| 4 | `saved` | `path` is this task's `worksheets/<slug>.json`, inside the workspace, a JSON object of at most 64 KB | `no worksheet at worksheets/CO2-from-C3H8-O2-1230fe3974.json: call save_worksheet before submitting` |
| 5 | `file-matches` | The saved file equals the submission, field by field | `the saved worksheet differs from the submission in theoretical_yield_g: submit exactly what save_worksheet returned` |
| 6 | `coefficients-form` | One coefficient per species, each a positive integer, gcd 1 | `the coefficients have gcd 2: divide them by it for the smallest integers` |
| 7 | `elements-balanced` | Every element is conserved (verifier's own parser) | `not every element is conserved: H 8 on the left, 6 on the right; O 10 on the left, 9 on the right` |
| 8 | `charge-balanced` | The total charge is conserved | `the total charge is 9 on the left but 5 on the right` |
| 9 | `coefficients` | The coefficients equal the answer key's | `the coefficients are not the unique smallest positive integers [1, 5] -> [3, 4]` |
| 10 | `limiting` | The limiting reagent list equals the answer key's (order included) | `the limiting reagent(s) are ['H2', 'O2'] (smallest moles / coefficient, ties in reactant order), not ['H2']` |
| 11 | `yield` | `theoretical_yield_g` is finite, positive and within 0.1% of the exact yield | `theoretical_yield_g 8.3 g is 0.579% from the exact yield 8.252203262703919 g; at most 0.1% is accepted` |

`details` also holds `exact_yield` (the answer key's `p/q`) and `tolerance`. The worksheet slug is
`<target>-from-<reactants>` (`+` as `p`, `-` as `m`, other symbols as `_`, at most 60 characters) and the
first 10 hex digits of the sha256 of the task input as compact key-sorted JSON, so two tasks never share a
file. A path that is absolute, holds `..`, or is not this slug fails `saved` before any file is read.

Every tool call is checked as well. `verify_input` refuses the inputs in the table above (for
`check_balance`, also coefficient lists of the wrong length or with a coefficient below 1; for
`save_worksheet`, an empty or unknown or repeated limiting reagent and a non-positive or non-finite yield).
`verify_output` re-parses every formula `parse_formula` returns (normalized form, atoms, charge, and molar mass
as the sum of the returned weights), recomputes `check_balance`'s whole tally, requires `save_worksheet`'s file
to equal its output at this task's path, and re-derives `pin_yield`'s answer key as check 2 does. The
`parse-formula` task is judged by `parse_formula`'s `verify_output`.

## Layout

```text
.
├── nanoagent.yaml   # manifest: id, runtime, permissions (no network), tools, tasks and the agent's instructions
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml   # no dependencies beyond the template's
├── uv.lock
├── .gitignore
├── .env             # needed environment variable names (none)
├── src/plugin/      # the MCP server (__main__.py) and the tools: formula.py (grammar, weights, parse_formula),
│                    #   reaction.py (input checks, check_balance), solver.py (pin_yield), worksheet.py
│                    #   (save_worksheet), data/atomic_weights.json
├── tests/           # test_formula.py, test_solver.py, test_tools.py, test_verifier.py; helpers.py
├── ui/              # renderers.js: a worksheet as its balanced equation, limiting reagents and yield
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier: formula.py (its own parser), checks.py, one module per tool,
                     #   task.py (the 11 checks)
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest            # 168 tests, named test_correct_*, test_incorrect_*, test_missing_*, test_malformed_*, test_boundary_*
uv run ruff check .
```

The golden values in `tests/test_formula.py` and `tests/test_solver.py` are worked out by hand from the
table's weights (e.g. propane: 10 / 31.998 / 5 x 3 x 44.009 = 44009/5333 g of CO2), not by the code under test.
`test_boundary_both_parsers_agree_on_random_strings` runs the plugin's and the verifier's parsers on 20,000
random strings and requires the same verdict and reading.

From NanoAgent's checkout, inspect, pack, run the tool task, and replay the scripted agent cases (each calls
`save_worksheet` through the real MCP server and hands the submission to the sandboxed verifier):

```bash
uv run nanoagent plugin inspect <this folder>
uv run nanoagent plugin pack <this folder> stoich-yield.tar.gz
uv run nanoagent plugin run config=run.yaml home=runs/parse   # run.yaml: plugin, task: parse-formula, arguments: args.json
.venv/bin/python <hw2>/evidence/replay.py <this folder> <hw2>/evidence/cases/stoich-yield
```

with `args.json` such as `{"formulas": ["K4[Fe(CN)6]", "CuSO4*5H2O", "MnO4^-"]}`. NanoAgent passes the folder
the plugin may write to as `NANOAGENT_WORKSPACE`; worksheets go in its `worksheets/` folder.

## Limitations

- **Abridged weights.** Molar masses use 5-significant-figure abridged weights (conventional values for
  elements such as H, Li, B, C, N, O, S, Cl), not a sample's isotopic composition; charged species ignore the
  electron's mass, as is standard.
- **One balancing only.** Reactions with several independent balancings (two reactions in one, e.g.
  H2 + O2 -> H2O + H2O2) are refused, as are redox half-reactions, which would need electrons.
- **The near-tie refusal** narrows which masses a task may use (distinct extents more than 1% apart).
- **Hand arithmetic.** The 0.1% tolerance accepts any yield within it, so a careless but lucky answer passes;
  it also means a yield computed from a wrong molar mass that happens to fall within 0.1% would pass.
- **Theoretical only.** No percent yield, side reactions, phases or equilibria.
- **Transcribed data.** The weights were copied by hand from CIAAW's page and compared with it entry by entry;
  a test pins the values the golden examples use, but nothing re-checks the table against CIAAW at run time
  (the plugin is offline). A changed table shows as a changed `data_sha256` in the answer key.
