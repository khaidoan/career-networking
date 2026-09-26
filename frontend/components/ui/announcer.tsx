"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { CircleAlert, CircleCheck } from "lucide-react";

import { cn } from "@/lib/utils";

export type AnnounceTone = "status" | "error";
export type Announce = (message: string, tone?: AnnounceTone) => void;

type Announcement = { id: number; message: string; tone: AnnounceTone };

const STATUS_TOAST_MS = 5000;
const ERROR_TOAST_MS = 8000;
const MAX_TOASTS = 3;

const AnnounceContext = createContext<Announce>(() => {});

/**
 * Announces short results to screen readers and shows them as toasts. Status messages use a
 * polite live region and errors an assertive one. Toasts are visual only (hidden from assistive
 * tech, which already hears the live region) and never take focus.
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
    const timer = setTimeout(
      () => {
        setToasts((current) => current.filter((toast) => toast.id !== item.id));
        timers.current.delete(item.id);
      },
      tone === "error" ? ERROR_TOAST_MS : STATUS_TOAST_MS,
    );
    timers.current.set(item.id, timer);
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
        aria-hidden="true"
        data-testid="toasts"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-60 flex flex-col items-center gap-2 md:inset-x-auto md:right-6 md:bottom-6 md:items-end"
      >
        {toasts.map((toast) => {
          const Icon = toast.tone === "error" ? CircleAlert : CircleCheck;
          return (
            <div
              key={toast.id}
              className={cn(
                "flex w-full max-w-sm animate-in items-start gap-3 rounded-lg border border-l-4 bg-surface px-4 py-3 text-sm text-foreground shadow-soft-lg duration-150 fade-in-0 slide-in-from-bottom-2",
                toast.tone === "error"
                  ? "border-l-destructive"
                  : "border-l-success",
              )}
            >
              <Icon
                className={cn(
                  "mt-0.5 size-4 shrink-0",
                  toast.tone === "error" ? "text-destructive" : "text-success",
                )}
              />
              <span>{toast.message}</span>
            </div>
          );
        })}
      </div>
    </AnnounceContext.Provider>
  );
}

/** `announce(message, tone?)`; a no-op outside `AnnouncerProvider`. */
export function useAnnounce(): Announce {
  return useContext(AnnounceContext);
}
