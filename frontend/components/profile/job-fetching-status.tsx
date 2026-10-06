import { CircleCheck, PauseCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type {
  FetchingRequirement,
  JobFetchingStatus as Status,
} from "@/lib/api/preferences";

const REQUIREMENT_LABELS: Record<FetchingRequirement, string> = {
  desired_titles: "Desired job titles",
  country: "Country",
  fetch_time: "Daily job fetch time",
  fetch_timezone: "Time zone",
};

/** `iso` in `timeZone` (falling back to the browser's zone if it does not know that name). */
function formatNextRun(iso: string, timeZone: string | null): string {
  const date = new Date(iso);
  const options: Intl.DateTimeFormatOptions = {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  };
  try {
    return new Intl.DateTimeFormat(undefined, {
      ...options,
      timeZone: timeZone ?? undefined,
    }).format(date);
  } catch {
    return new Intl.DateTimeFormat(undefined, options).format(date);
  }
}

type JobFetchingStatusProps = {
  /** From the saved preferences, so it changes only when the page is saved. */
  status: Status;
  timeZone: string | null;
};

/** Whether the job fetcher will run, and what to save to turn it on. */
export function JobFetchingStatus({
  status,
  timeZone,
}: JobFetchingStatusProps) {
  if (status.enabled) {
    return (
      <Alert variant="success" role="status">
        <CircleCheck aria-hidden="true" />
        <AlertTitle>Job fetching is enabled</AlertTitle>
        <AlertDescription>
          {status.next_run_at
            ? `Next run: ${formatNextRun(status.next_run_at, timeZone)}. `
            : null}
          A server restart also starts a run.
        </AlertDescription>
      </Alert>
    );
  }
  return (
    <Alert variant="warning" role="status">
      <PauseCircle aria-hidden="true" />
      <AlertTitle>Job fetching is disabled</AlertTitle>
      <AlertDescription>
        To turn it on, fill in and save:{" "}
        {status.missing
          .map((requirement) => REQUIREMENT_LABELS[requirement])
          .join(", ")}
        .
      </AlertDescription>
    </Alert>
  );
}
