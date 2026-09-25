import Link from "next/link";

import { MobileNav } from "@/components/app-shell/mobile-nav";
import { UserMenu } from "@/components/app-shell/user-menu";
import { DEFAULT_AUTHENTICATED_PATH } from "@/lib/auth/safe-redirect";

/** App header: mobile menu button, app name (home link) and the account menu. */
export function TopBar() {
  return (
    <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-2 border-b bg-surface px-2 md:px-6">
      <MobileNav />
      <Link
        href={DEFAULT_AUTHENTICATED_PATH}
        className="flex min-h-11 items-center rounded-lg px-2 text-lg font-semibold tracking-tight text-foreground md:px-0"
      >
        Career Networking
      </Link>
      <div className="ml-auto flex items-center">
        <UserMenu />
      </div>
    </header>
  );
}
