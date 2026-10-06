"use client";

import { useId, useState } from "react";
import { ExternalLink } from "lucide-react";

import { CopyMessageDialog } from "@/components/contacts/copy-message-dialog";
import { useAnnounce } from "@/components/ui/announcer";
import { markConnectionRequestSent, type Contact } from "@/lib/api/contacts";
import { copyText } from "@/lib/outreach/clipboard";
import { buildConnectionMessage } from "@/lib/outreach/message";

// Used in the greeting when a contact has no first name on record.
const FALLBACK_FIRST_NAME = "there";

type ContactListProps = {
  contacts: Contact[];
  companyName: string;
  /**
   * The job the message mentions: the current job on Job Details, the most recently discovered
   * job on Company Details. `null` (a company with no jobs) makes the name only open LinkedIn:
   * nothing is copied and the contact is not marked as sent.
   */
  jobTitle: string | null;
};

type ContactItemProps = {
  contact: Contact;
  companyName: string;
  jobTitle: string | null;
  hintId: string;
  onCopyFailed: (message: string) => void;
};

function displayName(contact: Contact): string {
  return contact.name?.trim() || "Unnamed contact";
}

/**
 * One contact. With a LinkedIn URL the name is a link that, in the same click, opens the
 * profile in a new tab, copies the connection message and records the request as sent (not
 * shown; it keeps a later contact search from changing the contact).
 */
function ContactItem({
  contact,
  companyName,
  jobTitle,
  hintId,
  onCopyFailed,
}: ContactItemProps) {
  const announce = useAnnounce();
  const name = displayName(contact);

  function connect() {
    // The link itself opens LinkedIn in a new tab, inside the user's click, so popup blockers
    // leave it alone. Everything below also starts synchronously within that click.
    if (jobTitle === null) {
      return;
    }
    const message = buildConnectionMessage({
      firstName: contact.first_name?.trim() || FALLBACK_FIRST_NAME,
      jobTitle,
      companyName,
    });
    void copyText(message).then((copied) => {
      if (copied) {
        announce("Message copied");
      } else {
        onCopyFailed(message);
      }
    });
    // Bookkeeping only (the status is not shown), so a failure is not reported.
    void markConnectionRequestSent(contact.id);
  }

  return (
    <li className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="flex min-w-0 flex-col">
        {contact.linkedin_url ? (
          <a
            href={contact.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={connect}
            aria-describedby={hintId}
            className="inline-flex min-h-11 w-fit items-center gap-1.5 rounded-sm font-medium text-accent underline-offset-4 hover:underline"
          >
            {name}
            <ExternalLink aria-hidden="true" className="size-4 shrink-0" />
            <span className="sr-only"> (opens LinkedIn in a new tab)</span>
          </a>
        ) : (
          <span className="flex min-h-11 items-center font-medium text-foreground">
            {name}
          </span>
        )}
        {contact.title && (
          <span className="text-sm text-muted-foreground">{contact.title}</span>
        )}
      </div>
    </li>
  );
}

/**
 * A company's networking contacts with click-to-connect; nothing at all until there are
 * contacts. Used on Job Details and Company Details. Nothing here sends anything to LinkedIn.
 */
export function ContactList({
  contacts,
  companyName,
  jobTitle,
}: ContactListProps) {
  const hintId = useId();
  const [fallbackMessage, setFallbackMessage] = useState<string | null>(null);

  if (contacts.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Found via search, may be out of date.
      </p>
      <p id={hintId} className="text-sm text-muted-foreground">
        {jobTitle === null
          ? "Selecting a name opens their LinkedIn profile."
          : "Clicking on a name opens their LinkedIn profile.  A sample connection message will be copied to the clipboard for you to use."}
      </p>
      <ul aria-label={`Contacts at ${companyName}`} className="divide-y">
        {contacts.map((contact) => (
          <ContactItem
            key={contact.id}
            contact={contact}
            companyName={companyName}
            jobTitle={jobTitle}
            hintId={hintId}
            onCopyFailed={setFallbackMessage}
          />
        ))}
      </ul>
      <CopyMessageDialog
        message={fallbackMessage}
        onClose={() => setFallbackMessage(null)}
      />
    </div>
  );
}
