import type { LucideIcon } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type DetailSectionProps = {
  id: string;
  title: string;
  description?: string;
  icon: LucideIcon;
  children: React.ReactNode;
};

/**
 * One card-shaped section of a details page (same pattern as `ProfileSection`), exposed to
 * assistive tech as a region named by its `h2`.
 */
export function DetailSection({
  id,
  title,
  description,
  icon: Icon,
  children,
}: DetailSectionProps) {
  const headingId = `${id}-heading`;
  return (
    <section aria-labelledby={headingId}>
      <Card className="gap-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon className="size-5 text-accent" aria-hidden="true" />
            <h2 id={headingId}>{title}</h2>
          </CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent className="flex flex-col gap-4">{children}</CardContent>
      </Card>
    </section>
  );
}

export type DetailField = { label: string; value: React.ReactNode };

/** Labelled values as a `dl`; fields with no value are left out. */
export function DetailFields({ fields }: { fields: DetailField[] }) {
  const known = fields.filter(
    ({ value }) => value !== null && value !== undefined && value !== "",
  );
  if (known.length === 0) {
    return null;
  }
  return (
    <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
      {known.map(({ label, value }) => (
        <div key={label} className="flex min-w-0 flex-col gap-0.5">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="min-w-0 font-medium break-words text-foreground">
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
