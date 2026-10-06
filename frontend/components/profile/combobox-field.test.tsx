import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { COUNTRY_OPTIONS } from "@/lib/profile/options";

import { ComboboxField, filterOptions } from "./combobox-field";

function Country({ initial = "", onSubmit = vi.fn() }) {
  const [value, setValue] = useState(initial);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(value);
      }}
    >
      <ComboboxField
        id="country"
        label="Country"
        value={value}
        onChange={setValue}
        options={COUNTRY_OPTIONS}
      />
      <button type="button">Elsewhere</button>
      <output>{value || "none"}</output>
    </form>
  );
}

function labels(query: string) {
  return filterOptions(COUNTRY_OPTIONS, query).map((option) => option.label);
}

describe("filterOptions", () => {
  it("ranks codes, then name prefixes, then word prefixes, ignoring accents", () => {
    expect(labels("us")[0]).toBe("United States");
    expect(labels("can")[0]).toBe("Canada");
    expect(labels("kingdom")).toContain("United Kingdom");
    expect(labels("cote")).toContain("Côte d'Ivoire");
    expect(labels("zzz")).toEqual([]);
  });
});

describe("ComboboxField", () => {
  it("filters as the user types and picks the highlighted match with Enter", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<Country onSubmit={onSubmit} />);

    await user.type(screen.getByRole("combobox", { name: "Country" }), "germ");

    expect(
      screen.getAllByRole("option").map((option) => option.textContent),
    ).toEqual(["Germany"]);
    await user.keyboard("{Enter}");

    expect(screen.getByRole("status")).toHaveTextContent("DE");
    expect(screen.getByRole("combobox")).toHaveValue("Germany");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("picks the best match when the user leaves the field", async () => {
    const user = userEvent.setup();
    render(<Country initial="US" />);

    const input = screen.getByRole("combobox");
    await user.clear(input);
    await user.type(input, "canad");
    await user.click(screen.getByRole("button", { name: "Elsewhere" }));

    expect(screen.getByRole("status")).toHaveTextContent("CA");
    expect(input).toHaveValue("Canada");
  });

  it("keeps the old value for text with no match or after Escape, and clears on erase", async () => {
    const user = userEvent.setup();
    render(<Country initial="US" />);
    const input = screen.getByRole("combobox");

    await user.type(input, "zzz");
    expect(screen.getByText("No matches")).toBeInTheDocument();
    await user.tab();
    expect(input).toHaveValue("United States");

    await user.type(input, "fra{Escape}");
    expect(input).toHaveValue("United States");
    expect(screen.getByRole("status")).toHaveTextContent("US");

    await user.clear(input);
    await user.tab();
    expect(screen.getByRole("status")).toHaveTextContent("none");
  });

  it("opens with the arrow keys and picks an option by click", async () => {
    const user = userEvent.setup();
    render(<Country initial="FR" />);

    await user.click(screen.getByRole("button", { name: "Open Country list" }));
    expect(screen.getByRole("option", { name: "France" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.click(screen.getByRole("option", { name: "Spain" }));

    expect(screen.getByRole("status")).toHaveTextContent("ES");
  });
});
