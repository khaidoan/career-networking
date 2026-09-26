import {
  BadgeCheck,
  CircleAlert,
  CircleSlash,
  SignalHigh,
  SignalLow,
  SignalMedium,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { matchStrength, type MatchStrength } from "@/lib/jobs/format";
import { cn } from "@/lib/utils";

const STRENGTH_STYLES = {
  Strong: { variant: "success", icon: SignalHigh },
  Good: { variant: "default", icon: SignalMedium },
  Weak: { variant: "outline", icon: SignalLow },
} as const satisfies Record<
  MatchStrength,
  { variant: "success" | "default" | "outline"; icon: typeof SignalHigh }
>;

/** Overall score as word + number + icon (never colour alone), e.g. "Strong · 86". */
export function MatchStrengthBadge({ score }: { score: number }) {
  const strength = matchStrength(score);
  const { variant, icon: Icon } = STRENGTH_STYLES[strength];
  return (
    <Badge variant={variant} className="text-sm [&>svg]:size-4">
      <Icon aria-hidden="true" />
      <span className="sr-only">Match strength: </span>
      {strength}
      <span aria-hidden="true">·</span>
      <span className="sr-only">, score</span>
      {score}
    </Badge>
  );
}

/** Marker for a job whose evaluation failed and so has no scores. */
export function NotScoredBadge() {
  return (
    <Badge variant="warning" className="text-sm [&>svg]:size-4">
      <CircleAlert aria-hidden="true" />
      Not scored
    </Badge>
  );
}

/** "Visa sponsorship" or "No visa sponsorship" with an icon; nothing when unknown. */
export function VisaIndicator({
  sponsorship,
  className,
}: {
  sponsorship: boolean | null;
  className?: string;
}) {
  if (sponsorship === null) {
    return null;
  }
  const Icon = sponsorship ? BadgeCheck : CircleSlash;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-sm text-foreground",
        className,
      )}
    >
      <Icon
        aria-hidden="true"
        className={cn(
          "size-4 shrink-0",
          sponsorship ? "text-success" : "text-muted-foreground",
        )}
      />
      {sponsorship ? "Visa sponsorship" : "No visa sponsorship"}
    </span>
  );
}
