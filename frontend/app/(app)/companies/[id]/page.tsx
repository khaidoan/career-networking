import type { Metadata } from "next";

import {
  CompanyDetails,
  CompanyNotFound,
} from "@/components/companies/company-details";

export const metadata: Metadata = { title: "Company details" };

export default async function CompanyDetailsPage({
  params,
}: PageProps<"/companies/[id]">) {
  const { id } = await params;
  const companyId = /^\d+$/.test(id) ? Number(id) : null;

  return (
    <div className="flex w-full flex-col gap-8">
      {companyId === null ? (
        <CompanyNotFound />
      ) : (
        <CompanyDetails key={companyId} companyId={companyId} />
      )}
    </div>
  );
}
