import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Coloured variants keep text on solid surfaces: a coloured left border marks the tone,
// because text on translucent tints fails WCAG AA with this palette.
const alertVariants = cva(
  "relative grid w-full gap-1 rounded-lg border border-l-4 px-4 py-3 text-left text-sm has-[>svg]:grid-cols-[auto_1fr] has-[>svg]:gap-x-3 *:[svg]:row-span-2 *:[svg]:translate-y-0.5 *:[svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "border-l-border bg-surface text-foreground",
        info: "border-l-accent bg-surface text-foreground *:[svg]:text-accent",
        success:
          "border-l-success bg-surface text-foreground *:[svg]:text-success",
        warning:
          "border-l-warning bg-surface text-foreground *:[svg]:text-warning",
        destructive:
          "border-l-destructive bg-surface text-destructive *:[svg]:text-destructive",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Alert({
  className,
  variant,
  role = "alert",
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      data-variant={variant}
      role={role}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  );
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn("font-medium", className)}
      {...props}
    />
  );
}

function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "text-sm text-muted-foreground [&_p:not(:last-child)]:mb-2",
        className,
      )}
      {...props}
    />
  );
}

export { Alert, AlertTitle, AlertDescription };
