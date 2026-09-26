"use client";

import { useCallback, useRef, useState } from "react";

import { useAnnounce } from "@/components/ui/announcer";
import type { ApiFailure } from "@/lib/api/request";

type UseOptimisticLikeOptions<T> = {
  /** The saved value. */
  liked: boolean;
  /** Name used in the failure message, e.g. the job title. */
  name: string;
  save: (liked: boolean) => Promise<({ ok: true } & T) | ApiFailure>;
  /** Called with the successful result so the owner can store the saved record. */
  onSaved?: (result: { ok: true } & T) => void;
};

/**
 * Like toggle that shows the new value at once, saves it, and on failure goes back to the saved
 * value and announces the error.
 */
export function useOptimisticLike<T>({
  liked,
  name,
  save,
  onSaved,
}: UseOptimisticLikeOptions<T>) {
  const announce = useAnnounce();
  const [pendingValue, setPendingValue] = useState<boolean | null>(null);
  const saving = useRef(false);
  const shown = pendingValue ?? liked;

  const toggle = useCallback(async () => {
    if (saving.current) {
      return;
    }
    saving.current = true;
    const next = !shown;
    setPendingValue(next);
    const result = await save(next);
    saving.current = false;
    if (result.ok) {
      onSaved?.(result);
    } else {
      announce(
        `Could not ${next ? "like" : "unlike"} ${name}. ${result.message}`,
        "error",
      );
    }
    setPendingValue(null);
  }, [announce, name, onSaved, save, shown]);

  return { liked: shown, toggle };
}
