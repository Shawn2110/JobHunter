---
name: resume_rewrite
kind: execution
version: 1
inputs:
  - name: brief
    type: object
    description: The (possibly user-edited) tailoring brief from Layer 1.
  - name: resume_json
    type: object
    description: Parsed master resume.
  - name: job
    type: object
    description: Target job (title, company).
output_schema:
  type: object
  properties:
    name: { type: string }
    email: { type: ["string", "null"] }
    phone: { type: ["string", "null"] }
    location: { type: ["string", "null"] }
    summary: { type: ["string", "null"] }
    experience:
      type: array
      items:
        type: object
        properties:
          company: { type: string }
          title: { type: string }
          start_date: { type: ["string", "null"] }
          end_date: { type: ["string", "null"] }
          location: { type: ["string", "null"] }
          bullets:
            type: array
            items: { type: string }
        required: [company, title, bullets]
    education:
      type: array
      items:
        type: object
        properties:
          institution: { type: string }
          degree: { type: string }
          field: { type: ["string", "null"] }
          start_date: { type: ["string", "null"] }
          end_date: { type: ["string", "null"] }
          gpa: { type: ["string", "null"] }
        required: [institution, degree]
    skills:
      type: array
      items: { type: string }
    projects:
      type: array
      items:
        type: object
        properties:
          name: { type: string }
          description: { type: ["string", "null"] }
          url: { type: ["string", "null"] }
          tech:
            type: array
            items: { type: string }
        required: [name]
    links:
      type: array
      items:
        type: object
        properties:
          kind: { type: string }
          url: { type: string }
        required: [kind, url]
    diff_summary:
      type: array
      items: { type: string }
  required: [name, experience, education, skills, diff_summary]
model: claude-opus-4-7
max_tokens: 6144
temperature: 0.1
notes: |
  Layer-2 execution: produce the rewritten resume in the SAME schema
  as parse_resume.md output, plus a diff_summary array describing what
  changed. The truthfulness post-check (backend/app/ai/truthfulness_check.py)
  validates this output structurally — invented companies/titles/dates
  fail and trigger regeneration.
---

You are rewriting a resume for a specific job, guided by the tailoring
brief. Apply the brief faithfully but DO NOT exceed it. Output the same
JSON schema as the parsed master resume, plus a `diff_summary` array.

ABSOLUTE HARD RULES (enforced by automated post-check):
- Companies in your output MUST be a subset of companies in the input
  resume.
- Titles for each company MUST match the input.
- Start/end dates MUST match the input.
- Education entries MUST match the input.
- Skills you add MUST be present in the input resume's skills, in the
  input resume's bullet text, OR explicitly approved in the brief's
  `keywords_truthfully_supported` (with a `source`).
- No new bullet may claim experience the input doesn't support.

Allowed:
- Rephrase existing bullets using the JD's language (per
  brief.vocabulary_shifts).
- Reorder bullets within an experience entry.
- Reorder experience entries (most-relevant first).
- Add the JD's exact keywords from brief.keywords_truthfully_supported
  into existing bullets where they fit truthfully.
- Trim de-emphasized bullets.
- Update the summary to reflect positioning.

Avoid AI-tells:
- "Leveraged synergies", "passionate about", "results-driven",
  "I hope this finds you well" (none of these belong in a resume anyway,
  but: also no over-formal hedging like "endeavored to" or
  "strategically positioned").
- Keep verbs concrete. Numbers come from the source resume only.

diff_summary: 5-15 short strings, one per material change. e.g.
"Reordered Razorpay bullets to lead with payment-API throughput",
"Added 'TypeScript' to Acme.bullet1 (sourced from skills list)".

Return JSON only. No markdown fences. No commentary.

TAILORING BRIEF:
{{ brief }}

MASTER RESUME (parsed):
{{ resume_json }}

TARGET JOB:
{{ job }}
