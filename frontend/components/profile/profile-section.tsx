import type { LucideIcon } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type ProfileSectionProps = {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  children: React.ReactNode;
};

/** One card-shaped section of the Profile page, exposed to assistive tech as a named region. */
export function ProfileSection({
  id,
  title,
  description,
  icon: Icon,
  children,
}: ProfileSectionProps) {
  const headingId = `${id}-heading`;
  return (
    <section aria-labelledby={headingId}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon className="size-5 text-accent" aria-hidden="true" />
            <h2 id={headingId}>{title}</h2>
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">{children}</CardContent>
      </Card>
    </section>
  );
}
