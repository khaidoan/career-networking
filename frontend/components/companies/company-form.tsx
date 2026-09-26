"use client";

import { useState, type FormEvent } from "react";
import { LoaderCircle, TriangleAlert } from "lucide-react";

import { TagInput } from "@/components/profile/tag-input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useAnnounce } from "@/components/ui/announcer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import {
  createCompany,
  updateCompany,
  type Company,
  type CompanyDetail,
} from "@/lib/api/companies";
import type { FieldErrors } from "@/lib/api/request";
import {
  MAX_COMPANY_LONG_TEXT_LENGTH,
  MAX_COMPANY_NAME_LENGTH,
  MAX_COMPANY_SHORT_TEXT_LENGTH,
  MAX_COMPANY_URL_LENGTH,
  toCompanyFormValues,
  toCompanyWrite,
  validateCompany,
  type CompanyFormValues,
} from "@/lib/companies/form";

type CompanyFormProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The company to edit; `null` adds a new one. */
  company: Company | null;
  /** Receives the saved company. */
  onSaved: (company: CompanyDetail) => void;
};

type TextFieldKey = Exclude<keyof CompanyFormValues, "industries">;

type TextFieldSpec = {
  key: TextFieldKey;
  label: string;
  maxLength: number;
  optional?: boolean;
  multiline?: boolean;
  type?: "url";
  placeholder?: string;
  description?: string;
};

const CLIENT_INVALID_MESSAGE =
  "Some fields need your attention. Check the messages below.";

const BEFORE_INDUSTRIES: readonly TextFieldSpec[] = [
  { key: "name", label: "Name", maxLength: MAX_COMPANY_NAME_LENGTH },
  {
    key: "website_url",
    label: "Website URL",
    maxLength: MAX_COMPANY_URL_LENGTH,
    type: "url",
    placeholder: "https://example.com",
  },
  {
    key: "linkedin_url",
    label: "LinkedIn URL",
    maxLength: MAX_COMPANY_URL_LENGTH,
    type: "url",
    placeholder: "https://www.linkedin.com/company/example",
  },
  {
    key: "logo_url",
    label: "Logo URL",
    maxLength: MAX_COMPANY_URL_LENGTH,
    type: "url",
    optional: true,
    placeholder: "https://example.com/logo.png",
  },
  {
    key: "description",
    label: "Description",
    maxLength: MAX_COMPANY_LONG_TEXT_LENGTH,
    multiline: true,
  },
];

const AFTER_INDUSTRIES: readonly TextFieldSpec[] = [
  {
    key: "growth_stage",
    label: "Growth stage",
    maxLength: MAX_COMPANY_SHORT_TEXT_LENGTH,
    placeholder: "For example: Series B",
  },
  {
    key: "employee_estimate",
    label: "Employee estimate",
    maxLength: MAX_COMPANY_SHORT_TEXT_LENGTH,
    placeholder: "For example: 201-500",
  },
  {
    key: "history",
    label: "History",
    maxLength: MAX_COMPANY_LONG_TEXT_LENGTH,
    multiline: true,
    optional: true,
    description: "Founding story, milestones or recent news.",
  },
];

/** Field order, used to move focus to the first field with an error. */
const FIELD_ORDER: readonly (keyof CompanyFormValues)[] = [
  ...BEFORE_INDUSTRIES.map(({ key }) => key),
  "industries",
  ...AFTER_INDUSTRIES.map(({ key }) => key),
];

function fieldId(key: keyof CompanyFormValues) {
  return `company-form-${key.replaceAll("_", "-")}`;
}

function TextField({
  spec,
  value,
  error,
  onChange,
}: {
  spec: TextFieldSpec;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  const id = fieldId(spec.key);
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;
  const describedBy =
    [spec.description ? descriptionId : null, error ? errorId : null]
      .filter(Boolean)
      .join(" ") || undefined;
  const shared = {
    id,
    value,
    maxLength: spec.maxLength,
    placeholder: spec.placeholder,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": describedBy,
    "aria-required": spec.optional ? undefined : true,
  } as const;

  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>
        {spec.label}
        {spec.optional && (
          <span className="font-normal text-muted-foreground">(optional)</span>
        )}
      </Label>
      {spec.description && (
        <p id={descriptionId} className="text-sm text-muted-foreground">
          {spec.description}
        </p>
      )}
      {spec.multiline ? (
        <Textarea
          {...shared}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : (
        <Input
          {...shared}
          type={spec.type ?? "text"}
          inputMode={spec.type === "url" ? "url" : undefined}
          autoComplete="off"
          onChange={(event) => onChange(event.target.value)}
        />
      )}
      {error && (
        <p id={errorId} className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

/** The form itself; mounted each time the sheet opens, so it starts from the saved values. */
function CompanyFormBody({
  company,
  onSaved,
  onCancel,
}: {
  company: Company | null;
  onSaved: (company: CompanyDetail) => void;
  onCancel: () => void;
}) {
  const announce = useAnnounce();
  const [values, setValues] = useState(() => toCompanyFormValues(company));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function update(patch: Partial<CompanyFormValues>) {
    setValues((current) => ({ ...current, ...patch }));
    setErrors((current) => {
      const next = { ...current };
      for (const key of Object.keys(patch)) {
        delete next[key];
      }
      return next;
    });
  }

  function showErrors(fieldErrors: FieldErrors, summary: string) {
    setErrors(fieldErrors);
    setMessage(summary);
    const first = FIELD_ORDER.find((key) => key in fieldErrors);
    if (first) {
      document.getElementById(fieldId(first))?.focus();
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) {
      return;
    }
    const clientErrors = validateCompany(values);
    if (Object.keys(clientErrors).length > 0) {
      showErrors(clientErrors, CLIENT_INVALID_MESSAGE);
      return;
    }
    setSaving(true);
    setMessage(null);
    const body = toCompanyWrite(values);
    const result = company
      ? await updateCompany(company.id, body)
      : await createCompany(body);
    setSaving(false);
    if (!result.ok) {
      showErrors(result.fieldErrors, result.message);
      return;
    }
    announce(
      company
        ? `${result.company.name} saved.`
        : `${result.company.name} added.`,
    );
    onSaved(result.company);
  }

  const renderField = (spec: TextFieldSpec) => (
    <TextField
      key={spec.key}
      spec={spec}
      value={values[spec.key]}
      error={errors[spec.key]}
      onChange={(value) => update({ [spec.key]: value })}
    />
  );

  return (
    <form
      noValidate
      onSubmit={handleSubmit}
      className="flex min-h-0 flex-1 flex-col"
      aria-label={company ? `Edit ${company.name}` : "Add company"}
    >
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 pb-4">
        {message && (
          <Alert variant="destructive" role="alert">
            <TriangleAlert aria-hidden="true" />
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}
        {BEFORE_INDUSTRIES.map(renderField)}
        <TagInput
          id={fieldId("industries")}
          label="Industries"
          description="Press Enter or type a comma after each industry."
          values={values.industries}
          onChange={(industries) => update({ industries })}
          placeholder="For example: Fintech"
          error={errors.industries}
        />
        {AFTER_INDUSTRIES.map(renderField)}
      </div>
      <div className="flex flex-col-reverse gap-2 border-t p-4 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" aria-disabled={saving || undefined}>
          {saving && (
            <LoaderCircle aria-hidden="true" className="animate-spin" />
          )}
          {saving ? "Saving…" : company ? "Save changes" : "Add company"}
        </Button>
      </div>
    </form>
  );
}

/**
 * Add or edit a company in a side sheet (full width on phones). Every field is labelled, the
 * client checks mirror the server rules, and the server's 422 messages show next to each field.
 */
export function CompanyForm({
  open,
  onOpenChange,
  company,
  onSaved,
}: CompanyFormProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full max-w-full sm:max-w-lg">
        <SheetHeader className="border-b">
          <SheetTitle>
            {company ? `Edit ${company.name}` : "Add company"}
          </SheetTitle>
          <SheetDescription>
            Fields marked optional can be left blank; everything else is
            required.
          </SheetDescription>
        </SheetHeader>
        {open && (
          <CompanyFormBody
            company={company}
            onSaved={(saved) => {
              onSaved(saved);
              onOpenChange(false);
            }}
            onCancel={() => onOpenChange(false)}
          />
        )}
      </SheetContent>
    </Sheet>
  );
}
