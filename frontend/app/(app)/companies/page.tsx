import { Suspense } from "react";
import type { Metadata } from "next";

import { CompanyList } from "@/components/companies/company-list";

export const metadata: Metadata = { title: "Companies" };

export default function CompaniesPage() {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          Companies
        </h1>
        <p className="text-muted-foreground">
          Your target employers, liked companies first, then A to Z.
        </p>
      </header>
      {/* The list reads its search and filters from the URL, which is only known in the browser. */}
      <Suspense
        fallback={
          <p role="status" className="text-sm text-muted-foreground">
            Loading companies…
          </p>
        }
      >
        <CompanyList />
      </Suspense>
    </div>
  );
}
