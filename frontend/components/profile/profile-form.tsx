"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  CircleCheck,
  Loader2,
  RotateCw,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import { CompensationSection } from "@/components/profile/compensation-section";
import { JobPreferencesSection } from "@/components/profile/job-preferences-section";
import { OtherSection } from "@/components/profile/other-section";
import { PersonalEeoSection } from "@/components/profile/personal-eeo-section";
import { ResumeCard } from "@/components/profile/resume-card";
import { SetupDialog } from "@/components/profile/setup-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  getPreferences,
  savePreferences,
  type FieldErrors,
  type Preferences,
  type ResumeUpload,
} from "@/lib/api/preferences";
import { detectCountry } from "@/lib/profile/detect-country";
import {
  applyResumeDefaults,
  applySuggestions,
  emptySuggestedTags,
  missingSetup,
  toFormValues,
  toUpdate,
  validate,
  type ProfileFormValues,
  type SuggestedTags,
} from "@/lib/profile/form";
import { COUNTRY_CURRENCY } from "@/lib/profile/options";
import { cn } from "@/lib/utils";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready" };

type SaveStatus =
  { kind: "idle" } | { kind: "saved" } | { kind: "error"; message: string };

/** Form keys whose API (and error) name differs. */
const FORM_TO_API_FIELD: Record<string, string> = {
  salaryMin: "salary_min",
  salaryMax: "salary_max",
};

const CLIENT_INVALID_MESSAGE =
  "Some fields need your attention. Check the messages above.";

/** Form values for `preferences`, with the browser's country filled in when none is saved. */
function initialValues(preferences: Preferences) {
  const values = toFormValues(preferences);
  const detectedCountry = values.country ? undefined : detectCountry();
  if (detectedCountry) {
    values.country = detectedCountry;
    values.currency ||= COUNTRY_CURRENCY[detectedCountry] ?? "";
  }
  return { values, detectedCountry };
}

/** The Profile page: loads the saved preferences, edits them in sections and saves with PUT. */
export function ProfileForm() {
  const [load, setLoad] = useState<LoadState>({ status: "loading" });
  const [saved, setSaved] = useState<Preferences | null>(null);
  const [values, setValues] = useState<ProfileFormValues | null>(null);
  const [suggested, setSuggested] = useState<SuggestedTags>(emptySuggestedTags);
  const [suggestionCount, setSuggestionCount] = useState(0);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>({ kind: "idle" });
  // Opened once per visit when the profile loads without a resume, titles or a country.
  const [setupOpen, setSetupOpen] = useState(false);
  // Pre-filled when no country is saved; cleared by the first successful save.
  const [detectedCountry, setDetectedCountry] = useState<string>();

  // Bumped by "Try again" to re-run the load effect.
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getPreferences(controller.signal)
      .then((result) => {
        if (!result.ok) {
          setLoad({ status: "error", message: result.message });
          return;
        }
        const initial = initialValues(result.preferences);
        setDetectedCountry(initial.detectedCountry);
        setSaved(result.preferences);
        setValues(initial.values);
        setSetupOpen(missingSetup(result.preferences).length > 0);
        setLoad({ status: "ready" });
      })
      .catch(() => {
        // Aborted on unmount.
      });
    return () => controller.abort();
  }, [loadAttempt]);

  function retryLoad() {
    setLoad({ status: "loading" });
    setLoadAttempt((attempt) => attempt + 1);
  }

  // Stable (it only uses state setters) so memoized fields can skip unrelated edits.
  const update = useCallback((patch: Partial<ProfileFormValues>) => {
    setValues((current) => (current ? { ...current, ...patch } : current));
    setSaveStatus({ kind: "idle" });
    // Clear the errors of the fields being edited.
    setErrors((current) => {
      const next = { ...current };
      for (const key of Object.keys(patch)) {
        delete next[FORM_TO_API_FIELD[key] ?? key];
      }
      if ("eeoAnswers" in patch) {
        for (const errorKey of Object.keys(next)) {
          if (errorKey.startsWith("eeo_answers.")) {
            delete next[errorKey];
          }
        }
      }
      return next;
    });
  }, []);

  function handleUploaded(upload: ResumeUpload) {
    setSaved(upload.preferences);
    if (!upload.suggestions || !values) {
      return;
    }
    // The server already saved the suggestions; merging them into the form (rather than taking
    // the saved values) keeps any edits the user has not saved yet.
    const merged = applySuggestions(values, suggested, upload.suggestions);
    setValues(
      applyResumeDefaults(merged.values, upload.preferences, detectedCountry),
    );
    setSuggested(merged.suggested);
    setSuggestionCount((count) => count + merged.addedCount);
    setSaveStatus({ kind: "idle" });
  }

  function handleResumeDeleted() {
    setSaved((current) => current && { ...current, resume: null });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!values || saving) {
      return;
    }
    const clientErrors = validate(values);
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      setSaveStatus({ kind: "error", message: CLIENT_INVALID_MESSAGE });
      return;
    }

    setSaving(true);
    setSaveStatus({ kind: "idle" });
    const result = await savePreferences(toUpdate(values));
    setSaving(false);
    if (!result.ok) {
      setErrors(result.fieldErrors);
      setSaveStatus({ kind: "error", message: result.message });
      return;
    }
    setSaved(result.preferences);
    setValues(toFormValues(result.preferences));
    setSuggested(emptySuggestedTags());
    setSuggestionCount(0);
    setErrors({});
    setSaveStatus({ kind: "saved" });
  }

  if (load.status === "loading") {
    return (
      <p
        role="status"
        className="flex items-center gap-2 text-muted-foreground"
      >
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading your profile…
      </p>
    );
  }

  if (load.status === "error" || !values || !saved) {
    return (
      <Alert variant="destructive">
        <TriangleAlert aria-hidden="true" />
        <AlertTitle>Your profile could not be loaded.</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-3">
          <p>{load.status === "error" ? load.message : null}</p>
          <Button type="button" variant="outline" onClick={retryLoad}>
            <RotateCw aria-hidden="true" />
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <SetupDialog
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        missing={missingSetup(saved)}
      />

      <ResumeCard
        resume={saved.resume}
        onUploaded={handleUploaded}
        onDeleted={handleResumeDeleted}
      />

      {suggestionCount > 0 && (
        <Alert variant="info" role="status">
          <Sparkles aria-hidden="true" />
          <AlertTitle>
            {suggestionCount === 1
              ? "1 suggestion added from your resume"
              : `${suggestionCount} suggestions added from your resume`}
          </AlertTitle>
          <AlertDescription>
            Remove any that do not fit, then click Save.
          </AlertDescription>
        </Alert>
      )}

      <form
        onSubmit={handleSubmit}
        noValidate
        aria-label="Profile and preferences"
        className="flex flex-col gap-6"
      >
        <JobPreferencesSection
          values={values}
          errors={errors}
          onChange={update}
          suggested={suggested}
        />
        <CompensationSection
          values={values}
          errors={errors}
          onChange={update}
          detectedCountry={saved.country ? undefined : detectedCountry}
        />
        <PersonalEeoSection values={values} errors={errors} onChange={update} />
        <OtherSection values={values} errors={errors} onChange={update} />

        <div className="flex flex-col items-center gap-3">
          <Button type="submit" disabled={saving} aria-busy={saving}>
            {saving && <Loader2 className="animate-spin" aria-hidden="true" />}
            {saving ? "Saving…" : "Save"}
          </Button>
          <p
            aria-live="polite"
            aria-atomic="true"
            className={cn(
              "flex items-center gap-2 text-center text-sm font-medium",
              saveStatus.kind === "idle" && "sr-only",
            )}
          >
            {saveStatus.kind === "saved" && (
              <>
                <CircleCheck
                  className="size-4 text-success"
                  aria-hidden="true"
                />
                Your profile was saved.
              </>
            )}
            {saveStatus.kind === "error" && (
              <span className="text-destructive">{saveStatus.message}</span>
            )}
          </p>
        </div>
      </form>
    </div>
  );
}
