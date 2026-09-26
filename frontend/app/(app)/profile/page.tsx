import type { Metadata } from "next";

import { ProfileForm } from "@/components/profile/profile-form";

export const metadata: Metadata = { title: "Profile / Preferences" };

export default function ProfilePage() {
  return (
    <div className="flex w-full max-w-3xl flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          Profile / Preferences
        </h1>
        <p className="text-muted-foreground">
          Your resume and job preferences decide which jobs are fetched and how
          they are scored.
        </p>
      </header>
      <ProfileForm />
    </div>
  );
}
