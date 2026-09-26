import type { Metadata } from "next";

import { JobDetails, JobNotFound } from "@/components/jobs/job-details";

export const metadata: Metadata = { title: "Job details" };

export default async function JobDetailsPage({
  params,
}: PageProps<"/jobs/[id]">) {
  const { id } = await params;
  const jobId = /^\d+$/.test(id) ? Number(id) : null;

  return (
    <div className="flex w-full flex-col gap-8">
      {jobId === null ? (
        <JobNotFound />
      ) : (
        <JobDetails key={jobId} jobId={jobId} />
      )}
    </div>
  );
}
