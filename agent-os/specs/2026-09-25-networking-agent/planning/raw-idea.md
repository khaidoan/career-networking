# Raw Idea

## Feature

Phase 4 — Networking Agent

## Source

`agent-os/product/roadmap.md`, Phase 4 (Phases 1-3 are already implemented).

## Goals

Automate discovery of relevant LinkedIn contacts at target companies.

## Deliverables

**Networking Agent (`networking.py`)**
- On job fetch, extract company name and skillset from posting
- Search LinkedIn for employees with matching skills
- Populate `company_networking` table
- Playwright-based LinkedIn outreach (user-triggered via UI button)

## Explicit User Constraint

"Do not auto-connect."

The app must never automatically send LinkedIn connection requests. The Playwright-based LinkedIn outreach must remain strictly user-triggered via a UI button — no automatic/background sending of connection requests. This aligns with the roadmap's Deferred / Out of Scope (v1) list, which excludes "Auto-connect to LinkedIn (due to rate limiting / account risk)."
