"use client";

import { useId, useRef, useState } from "react";
import { Copy } from "lucide-react";

import { useAnnounce } from "@/components/ui/announcer";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { copyText } from "@/lib/outreach/clipboard";

type CopyMessageDialogProps = {
  /** The message to copy; the dialog is open while this is set. */
  message: string | null;
  onClose: () => void;
};

/**
 * Fallback for when the Clipboard API refuses to copy: shows the full message in a read-only
 * text area (selected on focus) with a "Copy" button.
 */
export function CopyMessageDialog({
  message,
  onClose,
}: CopyMessageDialogProps) {
  const announce = useAnnounce();
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const hintId = useId();
  const [manualCopy, setManualCopy] = useState(false);

  async function copy() {
    const textArea = textAreaRef.current;
    if (!message || !textArea) {
      return;
    }
    textArea.focus();
    textArea.select();
    if (await copyText(message, textArea)) {
      announce("Message copied");
      onClose();
      return;
    }
    setManualCopy(true);
  }

  return (
    <Dialog
      open={message !== null}
      onOpenChange={(open) => {
        if (!open) {
          setManualCopy(false);
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Copy your connection message</DialogTitle>
          <DialogDescription>
            The message could not be copied automatically. Copy it, then paste
            it into your LinkedIn connection note.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          ref={textAreaRef}
          readOnly
          aria-label="Connection message"
          aria-describedby={manualCopy ? hintId : undefined}
          value={message ?? ""}
          rows={7}
          onFocus={(event) => event.currentTarget.select()}
          className="resize-none"
        />
        {manualCopy && (
          <p id={hintId} role="status" className="text-sm text-foreground">
            The text is selected. Press Ctrl+C (Cmd+C on a Mac) to copy it.
          </p>
        )}
        <DialogFooter>
          <Button type="button" onClick={copy}>
            <Copy aria-hidden="true" />
            Copy
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
