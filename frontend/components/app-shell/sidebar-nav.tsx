"use client";

import { Fragment, useId } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { NAV_GROUPS, isActivePath } from "@/lib/navigation";

type SidebarNavProps = {
  /** Called after a link is chosen, e.g. to close the mobile sheet. */
  onNavigate?: () => void;
  className?: string;
};

/** Main navigation links, grouped, with the current page highlighted. */
export function SidebarNav({ onNavigate, className }: SidebarNavProps) {
  const pathname = usePathname();
  const idPrefix = useId();

  return (
    <nav aria-label="Main" className={cn("flex flex-col gap-4 p-4", className)}>
      {NAV_GROUPS.map((group, index) => {
        const headingId = `${idPrefix}-group-${index}`;
        return (
          <Fragment key={group.label ?? index}>
            {index > 0 && <Separator />}
            <div className="flex flex-col gap-1">
              {group.label && (
                <p
                  id={headingId}
                  className="px-3 pb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
                >
                  {group.label}
                </p>
              )}
              <ul
                className="flex flex-col gap-1"
                aria-labelledby={group.label ? headingId : undefined}
              >
                {group.items.map(({ href, label, icon: Icon }) => {
                  const active = isActivePath(pathname, href);
                  return (
                    <li key={href}>
                      <Link
                        href={href}
                        onClick={onNavigate}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "relative flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                          active
                            ? "bg-surface-alt font-semibold text-foreground before:absolute before:inset-y-2 before:left-0 before:w-1 before:rounded-full before:bg-accent"
                            : "text-muted-foreground hover:bg-surface-alt hover:text-foreground",
                        )}
                      >
                        <Icon
                          aria-hidden="true"
                          className={cn("size-4", active && "text-accent")}
                        />
                        {label}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          </Fragment>
        );
      })}
    </nav>
  );
}
