import { SidebarNav } from "@/components/app-shell/sidebar-nav";
import { TopBar } from "@/components/app-shell/top-bar";

/** Shared shell for every signed-in page: top bar, sidebar (md and up) and main content. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-accent-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <TopBar />
      <div className="flex flex-1">
        <aside className="hidden w-64 shrink-0 border-r bg-surface md:block">
          <div className="sticky top-16 max-h-[calc(100dvh-4rem)] overflow-y-auto">
            <SidebarNav />
          </div>
        </aside>
        <main
          id="main-content"
          tabIndex={-1}
          className="min-w-0 flex-1 px-4 py-8 focus:outline-none md:px-8"
        >
          <div className="mx-auto w-full max-w-5xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
