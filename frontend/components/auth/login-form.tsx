"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/lib/auth/client";

type LoginFormProps = {
  /** Already-validated in-app path to open after a successful login. */
  redirectTo: string;
};

const ERROR_ID = "login-error";

export function LoginForm({ redirectTo }: LoginFormProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setSubmitting(true);
    setError(null);

    const result = await login(
      String(formData.get("username") ?? ""),
      String(formData.get("password") ?? ""),
    );
    if (result.ok) {
      router.replace(redirectTo);
      router.refresh();
      return;
    }
    setError(result.message);
    setSubmitting(false);
  }

  const describedBy = error ? ERROR_ID : undefined;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Label htmlFor="username">Username</Label>
        <Input
          id="username"
          name="username"
          type="text"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
        />
      </div>

      <p
        id={ERROR_ID}
        aria-live="polite"
        aria-atomic="true"
        className="-my-2 min-h-5 text-sm font-medium text-destructive"
      >
        {error}
      </p>

      <Button type="submit" disabled={submitting} aria-busy={submitting}>
        {submitting && <Loader2 className="animate-spin" aria-hidden="true" />}
        {submitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
