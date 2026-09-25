"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";

import { endSession } from "@/lib/auth/client";
import { LOGIN_PATH } from "@/lib/auth/safe-redirect";

/** Logout action: end the session, then show the login page with fresh server state. */
export function useLogout() {
  const router = useRouter();

  return useCallback(async () => {
    await endSession();
    router.replace(LOGIN_PATH);
    router.refresh();
  }, [router]);
}
