// How this plugin's page draws its tasks' outputs: a saved worksheet as its balanced equation, limiting
// reagent(s) and theoretical yield; parsed formulas as a table of atoms, charge and molar mass.
import { dataTable, h, icon, statusPill } from "./kit/components.js";

/** "C3H8 + 5 O2", a coefficient of 1 left out. */
const side = (formulas, coefficients) =>
  formulas.map((formula, index) => (coefficients[index] === 1 ? formula : `${coefficients[index]} ${formula}`)).join(" + ");

/** "C 3, H 8". */
const atoms = (elements) => elements.map(({ element, count }) => `${element} ${count}`).join(", ");

export default {
  WorksheetOutput: (sheet) =>
    h(
      "div",
      { class: "worksheet" },
      h(
        "p",
        { class: "equation" },
        h("code", {
          text: `${side(sheet.reactants, sheet.reactant_coefficients)} → ${side(sheet.products, sheet.product_coefficients)}`,
        }),
      ),
      h(
        "dl",
        { class: "worksheet-facts" },
        h("dt", { text: "Limiting" }),
        h("dd", {}, sheet.limiting.map((name) => statusPill(name, "info"))),
        h("dt", { text: "Theoretical yield" }),
        h("dd", { text: `${sheet.theoretical_yield_g} g` }),
      ),
      h("p", { class: "worksheet-path muted" }, icon("file", { size: 14 }), h("code", { text: sheet.path })),
    ),
  ParseFormulaOutput: ({ species }) =>
    dataTable({
      columns: [
        { key: "formula", label: "Formula" },
        { key: "atoms", label: "Atoms" },
        { key: "charge", label: "Charge", numeric: true },
        { key: "molar_mass", label: "Molar mass (g/mol)", numeric: true },
      ],
      rows: species.map((row) => ({ ...row, atoms: atoms(row.elements) })),
    }),
};
