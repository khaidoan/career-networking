# Career Networking — Mission

## Product Vision

Career Networking is a self-hosted, privacy-first job discovery and professional networking tool for job seekers. It automates the discovery of new job postings across major job boards and ATS platforms, then helps the user connect with employees at those companies to request mock interviews — a more effective alternative to the broken traditional job application process.

## The Problem

The modern job application process is broken:
- ATS systems filter out qualified candidates before humans review resumes
- Job postings receive hundreds of applications, burying individual candidates
- Cold applications have extremely low conversion rates
- Job seekers have no control over their data when using SaaS platforms

## The Solution

Rather than optimizing for ATS filtering, Career Networking focuses on **human connection**:
1. Discover new, relevant job postings automatically
2. Identify employees at those companies with similar skills
3. Reach out via LinkedIn to request mock interviews (and potential referrals)
4. Prepare tailored resumes and cover letters when the user chooses to apply

## Target Users

**Primary:** Individual job seekers who want to take a proactive, networking-first approach to their job search. They are comfortable self-hosting a Docker-based application on their own machine.

**Key traits:**
- Values data privacy (all data stays on their machine)
- Willing to use their own AI API credits (or local models via LiteLLM)
- Prefers networking over blind applications
- Technically capable of running Docker Compose

## Business Model

Pay-what-you-can after getting a job. No subscription, no SaaS fees, no data harvesting.

## Core Principles

1. **Privacy first** — All data is self-hosted; nothing leaves the user's machine
2. **Single user** — No multi-tenancy; designed for one person per installation
3. **Networking over applying** — The primary goal is human connection, not ATS optimization
4. **User control** — Manual actions (connect on LinkedIn, apply to jobs) are preferred over fully automated flows
5. **Bring your own AI** — Works with any LLM provider via LiteLLM, including local models

## Key Features

- Automated job discovery from all job boards supported by Career-Ops
- AI-powered job evaluation and scoring against user preferences
- LinkedIn employee discovery for networking outreach (button-triggered search; the app never sends connection requests or messages)
- Clipboard-ready connection request messages
- AI-assisted tailored resume and cover letter generation (markdown → PDF)
- Manual apply flow with PDF preview before submission
- Customizable AI agent system prompts
- Single-user JWT authentication (credentials in environment variables)
