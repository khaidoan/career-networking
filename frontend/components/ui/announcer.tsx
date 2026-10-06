"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { Check, CircleAlert, CircleCheck, Copy, XIcon } from "lucide-react";

import { copyText } from "@/lib/outreach/clipboard";
import { cn } from "@/lib/utils";

export type AnnounceTone = "status" | "error";
export type Announce = (message: string, tone?: AnnounceTone) => void;

type Announcement = { id: number; message: string; tone: AnnounceTone };

const STATUS_TOAST_MS = 5000;
const MAX_TOASTS = 3;

const AnnounceContext = createContext<Announce>(() => {});

// The container lets clicks through to the page; each toast takes them, so its text can be
// selected and its buttons used.
const TOAST_CLASSES =
  "pointer-events-auto flex w-full max-w-sm animate-in items-start gap-3 rounded-lg border border-l-4 bg-surface px-4 py-3 text-sm text-foreground shadow-soft-lg duration-150 select-text fade-in-0 slide-in-from-bottom-2";

/** An error that stays until dismissed; already announced by the assertive live region. */
function ErrorToast({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <div className={cn(TOAST_CLASSES, "border-l-destructive")}>
      <CircleAlert
        aria-hidden="true"
        className="mt-0.5 size-4 shrink-0 text-destructive"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="break-words">{message}</p>
        <button
          type="button"
          onClick={async () => setCopied(await copyText(message))}
          className="inline-flex cursor-pointer items-center gap-1.5 self-start text-xs font-medium text-accent underline-offset-2 hover:underline"
        >
          {copied ? (
            <Check aria-hidden="true" className="size-3.5" />
          ) : (
            <Copy aria-hidden="true" className="size-3.5" />
          )}
          {copied ? "Copied" : "Copy error"}
        </button>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="-m-1 cursor-pointer rounded p-1 text-muted-foreground hover:text-foreground"
      >
        <XIcon aria-hidden="true" className="size-4" />
        <span className="sr-only">Dismiss</span>
      </button>
    </div>
  );
}

/**
 * Announces short results to screen readers and shows them as toasts. Status messages use a
 * polite live region and errors an assertive one. Toasts never take focus and their text can be
 * selected. Status toasts fade after a few seconds and are hidden from assistive tech (which
 * already hears the live region). Error toasts stay until dismissed and have Copy and Dismiss
 * buttons, so the message can be pasted into a bug report.
 */
export function AnnouncerProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Announcement[]>([]);
  const [polite, setPolite] = useState<Announcement | null>(null);
  const [assertive, setAssertive] = useState<Announcement | null>(null);
  const nextId = useRef(0);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const announce = useCallback<Announce>((message, tone = "status") => {
    nextId.current += 1;
    const item: Announcement = { id: nextId.current, message, tone };
    if (tone === "error") {
      setAssertive(item);
    } else {
      setPolite(item);
    }
    setToasts((current) => [...current, item].slice(-MAX_TOASTS));
    if (tone === "error") {
      return;
    }
    const timer = setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== item.id));
      timers.current.delete(item.id);
    }, STATUS_TOAST_MS);
    timers.current.set(item.id, timer);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach(clearTimeout);
  }, []);

  return (
    <AnnounceContext.Provider value={announce}>
      {children}
      {/* A new key per message makes repeated identical messages announce again. */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {polite && <span key={polite.id}>{polite.message}</span>}
      </div>
      <div aria-live="assertive" aria-atomic="true" className="sr-only">
        {assertive && <span key={assertive.id}>{assertive.message}</span>}
      </div>
      <div
        data-testid="toasts"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-60 flex flex-col items-center gap-2 md:inset-x-auto md:right-6 md:bottom-6 md:items-end"
      >
        {toasts.map((toast) =>
          toast.tone === "error" ? (
            <ErrorToast
              key={toast.id}
              message={toast.message}
              onDismiss={() => dismiss(toast.id)}
            />
          ) : (
            <div
              key={toast.id}
              aria-hidden="true"
              className={cn(TOAST_CLASSES, "border-l-success")}
            >
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" />
              <span>{toast.message}</span>
            </div>
          ),
        )}
      </div>
    </AnnounceContext.Provider>
  );
}

/** `announce(message, tone?)`; a no-op outside `AnnouncerProvider`. */
export function useAnnounce(): Announce {
  return useContext(AnnounceContext);
}
