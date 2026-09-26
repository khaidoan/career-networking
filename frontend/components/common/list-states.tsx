import type { LucideIcon } from "lucide-react";
import { RotateCw } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  message: string;
  children?: React.ReactNode;
};

/** A list with nothing to show (empty or filtered out), with an optional action. */
export function EmptyState({
  icon: Icon,
  title,
  message,
  children,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-surface px-6 py-12 text-center">
      <Icon aria-hidden="true" className="size-8 text-muted-foreground" />
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="max-w-md text-sm text-muted-foreground">{message}</p>
      {children}
    </div>
  );
}

/** Placeholder cards while the first page loads; `label` is announced, e.g. "Loading jobs…". */
export function LoadingCards({ label }: { label: string }) {
  return (
    <div className="flex flex-col gap-4">
      <p role="status" className="sr-only">
        {label}
      </p>
      {[0, 1, 2].map((index) => (
        <div
          key={index}
          aria-hidden="true"
          className="h-40 animate-pulse rounded-xl border bg-surface-alt"
        />
      ))}
    </div>
  );
}

type LoadErrorProps = {
  title: string;
  message: string | null;
  onRetry: () => void;
};

/** A failed load with the reason and a "Try again" button. */
export function LoadError({ title, message, onRetry }: LoadErrorProps) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription className="flex flex-col items-start gap-3">
        <p>{message}</p>
        <Button variant="outline" onClick={onRetry}>
          <RotateCw aria-hidden="true" />
          Try again
        </Button>
      </AlertDescription>
    </Alert>
  );
}
