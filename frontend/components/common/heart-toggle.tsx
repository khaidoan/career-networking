"use client";

import { Heart } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type HeartToggleProps = {
  liked: boolean;
  /** What is being liked, e.g. a job title or company name ("Like {name}"). */
  name: string;
  onToggle: () => void;
  className?: string;
};

/** Like / unlike toggle button: `aria-pressed` carries the state and the label stays fixed. */
export function HeartToggle({
  liked,
  name,
  onToggle,
  className,
}: HeartToggleProps) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-pressed={liked}
      aria-label={`Like ${name}`}
      title={liked ? "Liked" : "Like"}
      onClick={onToggle}
      className={cn("shrink-0", className)}
    >
      <Heart
        aria-hidden="true"
        className={cn(
          "size-5",
          liked ? "fill-accent text-accent" : "text-muted-foreground",
        )}
      />
    </Button>
  );
}
