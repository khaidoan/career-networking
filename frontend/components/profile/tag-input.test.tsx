import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TagInput } from "./tag-input";

function Harness({ initial = [] as string[] }) {
  const [values, setValues] = useState(initial);
  return (
    <TagInput id="skills" label="Skills" values={values} onChange={setValues} />
  );
}

function tags() {
  return within(screen.getByRole("list", { name: "Skills tags" }))
    .getAllByRole("listitem")
    .map((item) => item.textContent);
}

describe("TagInput", () => {
  it("adds tags with Enter and comma and removes one with its chip button", async () => {
    const user = userEvent.setup();
    render(<Harness initial={["Go"]} />);
    const input = screen.getByLabelText("Skills");

    await user.type(input, "Python{Enter}");
    await user.type(input, "SQL, go,Rust");
    expect(tags()).toEqual(["Go", "Python", "SQL"]);
    expect(input).toHaveValue("Rust");

    // Leaving the field keeps the unconfirmed "Rust" as a tag.
    await user.click(screen.getByRole("button", { name: "Remove Python" }));
    expect(tags()).toEqual(["Go", "SQL", "Rust"]);
    expect(input).toHaveValue("");
  });
});
