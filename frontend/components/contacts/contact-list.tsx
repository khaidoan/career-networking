"use client";

import { useId, useState } from "react";
import { CircleCheck, ExternalLink, UsersRound } from "lucide-react";

import { CopyMessageDialog } from "@/components/contacts/copy-message-dialog";
import { useAnnounce } from "@/components/ui/announcer";
import {
  markConnectionRequestSent,
  type Contact,
  type ContactSearchStatus,
} from "@/lib/api/contacts";
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
  /** Picks the empty-state text: a prompt to use Find contacts, or why it is unavailable. */
  contactSearch?: ContactSearchStatus;
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

/** "Request sent" with an icon, so the state never relies on colour. */
function RequestSentIndicator() {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
      <CircleCheck aria-hidden="true" className="size-4 text-success" />
      Request sent
    </span>
  );
}

/**
 * One contact. With a LinkedIn URL the name is a link that, in the same click, opens the
 * profile in a new tab, copies the connection message and marks the request as sent.
 */
function ContactItem({
  contact: initialContact,
  companyName,
  jobTitle,
  hintId,
  onCopyFailed,
}: ContactItemProps) {
  const announce = useAnnounce();
  // The saved copy only applies to the contact it was saved from, so a list refreshed by a
  // contact search (with possibly newer titles) is shown as received.
  const [saved, setSaved] = useState<{
    from: Contact;
    contact: Contact;
  } | null>(null);
  const contact =
    saved && saved.from === initialContact ? saved.contact : initialContact;
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
    void markConnectionRequestSent(contact.id).then((result) => {
      if (result.ok) {
        setSaved({ from: initialContact, contact: result.contact });
      } else {
        announce(
          `Could not mark the request to ${name} as sent. ${result.message}`,
          "error",
        );
      }
    });
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
      {contact.connection_request_sent && <RequestSentIndicator />}
    </li>
  );
}

function emptyStateText(
  companyName: string,
  contactSearch: ContactSearchStatus | undefined,
): string {
  if (contactSearch && !contactSearch.available) {
    return contactSearch.unavailable_reason === "no_api_key"
      ? `Contacts at ${companyName} can be found once a SerpApi key is set up.`
      : `Contacts at ${companyName} can be found once one of its jobs is recommended or applied to.`;
  }
  if (contactSearch?.last_searched_at) {
    return `The last search found no one at ${companyName}. Select Find contacts to try again.`;
  }
  return `Select Find contacts to look for people at ${companyName} on LinkedIn.`;
}

/**
 * A company's networking contacts with click-to-connect, or an empty state. Used on Job
 * Details and Company Details. Nothing here sends anything to LinkedIn.
 */
export function ContactList({
  contacts,
  companyName,
  jobTitle,
  contactSearch,
}: ContactListProps) {
  const hintId = useId();
  const [fallbackMessage, setFallbackMessage] = useState<string | null>(null);

  if (contacts.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed bg-surface px-6 py-8 text-center">
        <UsersRound
          aria-hidden="true"
          className="size-7 text-muted-foreground"
        />
        <p className="font-medium text-foreground">No contacts yet</p>
        <p className="max-w-md text-sm text-muted-foreground">
          {emptyStateText(companyName, contactSearch)}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Found via search, may be out of date.
      </p>
      <p id={hintId} className="text-sm text-muted-foreground">
        {jobTitle === null
          ? "Selecting a name opens their LinkedIn profile."
          : "Selecting a name opens their LinkedIn profile, copies a connection message and marks the request as sent."}
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
