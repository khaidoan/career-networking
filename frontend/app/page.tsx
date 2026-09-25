import { redirect } from "next/navigation";

import { DEFAULT_AUTHENTICATED_PATH } from "@/lib/auth/safe-redirect";

// The proxy normally redirects "/" first; this is the fallback.
export default function HomePage() {
  redirect(DEFAULT_AUTHENTICATED_PATH);
}
