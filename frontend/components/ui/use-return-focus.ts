"use client";

import { useRef } from "react";

type AutoFocusHandler = (event: Event) => void;

/**
 * Returns focus to whatever was focused when a Radix dialog opened. Radix only restores focus
 * to its own `Trigger`, so dialogs opened in controlled mode (from a plain button) would
 * otherwise drop focus to the page body on close. A consumer can still take over by calling
 * `event.preventDefault()` in its own `onCloseAutoFocus`.
 */
export function useReturnFocus(
  onOpenAutoFocus?: AutoFocusHandler,
  onCloseAutoFocus?: AutoFocusHandler,
) {
  const returnTo = useRef<HTMLElement | null>(null);

  return {
    onOpenAutoFocus(event: Event) {
      // Runs before Radix moves focus into the dialog, so this is still the opener.
      const active = document.activeElement;
      returnTo.current =
        active instanceof HTMLElement && active !== document.body
          ? active
          : null;
      onOpenAutoFocus?.(event);
    },
    onCloseAutoFocus(event: Event) {
      onCloseAutoFocus?.(event);
      const target = returnTo.current;
      returnTo.current = null;
      if (event.defaultPrevented || !target?.isConnected) {
        return;
      }
      event.preventDefault();
      target.focus();
    },
  };
}
