import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Button } from "./button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./dialog";

function ConfirmDialog() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>Apply</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Did you apply?</DialogTitle>
          <DialogDescription>Confirm the application.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button>No</Button>
          <Button>Yes</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Opened from a plain button (no DialogTrigger), as the Apply and delete confirmations are.
function ControlledDialog() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Delete</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Acme?</DialogTitle>
            <DialogDescription>Its contacts are deleted too.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setOpen(false)}>Cancel</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

describe("Dialog", () => {
  it("traps focus while open and returns it to the trigger on close", async () => {
    const user = userEvent.setup();
    render(<ConfirmDialog />);
    const trigger = screen.getByRole("button", { name: "Apply" });

    await user.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Did you apply?" });
    expect(dialog).toContainElement(document.activeElement as HTMLElement);
    for (let step = 0; step < 5; step += 1) {
      await user.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("returns focus to the button that opened a controlled dialog", async () => {
    const user = userEvent.setup();
    render(<ControlledDialog />);
    const opener = screen.getByRole("button", { name: "Delete" });

    await user.click(opener);
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });
});
