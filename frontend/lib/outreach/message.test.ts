import { describe, expect, it } from "vitest";

import { buildConnectionMessage, CONNECTION_MESSAGE_TEMPLATE } from "./message";

describe("buildConnectionMessage", () => {
  it("keeps the approved template word for word", () => {
    expect(CONNECTION_MESSAGE_TEMPLATE).toBe(
      "Hello {first_name}, I came across a job posting for {job_title} at your current company, {company_name}. Can you help me with a mock interview? If your company has a referral program, you may be able to earn the referral. Otherwise, you may enjoy getting to know me. Thank you!",
    );
  });

  it("replaces every placeholder with the bare, trimmed value", () => {
    expect(
      buildConnectionMessage({
        firstName: "  Jane ",
        jobTitle: " Senior Backend Engineer",
        companyName: "Acme Corp  ",
      }),
    ).toBe(
      "Hello Jane, I came across a job posting for Senior Backend Engineer at your current company, Acme Corp. Can you help me with a mock interview? If your company has a referral program, you may be able to earn the referral. Otherwise, you may enjoy getting to know me. Thank you!",
    );
  });

  it("keeps long values in full even past LinkedIn's 300-character limit", () => {
    const jobTitle = `Principal Distributed Systems Engineer ${"(Platform) ".repeat(12)}Team`;
    const companyName = `The Extremely Long Company Name $& ${"Holdings ".repeat(10)}Inc`;

    const message = buildConnectionMessage({
      firstName: "Bartholomew",
      jobTitle,
      companyName,
    });

    expect(message).toBe(
      CONNECTION_MESSAGE_TEMPLATE.split("{first_name}")
        .join("Bartholomew")
        .split("{job_title}")
        .join(jobTitle)
        .split("{company_name}")
        .join(companyName),
    );
    expect(message.length).toBeGreaterThan(300);
    expect(message).toContain(jobTitle);
    expect(message).toContain(companyName);
    expect(message.endsWith("Thank you!")).toBe(true);
  });
});
