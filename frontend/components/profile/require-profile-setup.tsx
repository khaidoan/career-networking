"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getPreferences } from "@/lib/api/preferences";
import { PROFILE_PATH } from "@/lib/auth/safe-redirect";
import { missingSetup } from "@/lib/profile/form";

/**
 * Renders `children` only once the profile has a resume, desired titles and a country; otherwise
 * replaces the page with the Profile page, which explains what is missing. If the preferences
 * cannot be loaded the page is shown anyway, so an API outage never locks the user out.
 */
export function RequireProfileSetup({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getPreferences(controller.signal)
      .then((result) => {
        if (result.ok && missingSetup(result.preferences).length > 0) {
          router.replace(PROFILE_PATH);
          return;
        }
        setReady(true);
      })
      .catch(() => {
        // Aborted on unmount.
      });
    return () => controller.abort();
  }, [router]);

  if (!ready) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Loading…
      </p>
    );
  }
  return children;
}
