---
name: extract_knockouts
kind: static
version: 1
inputs:
  - name: job_description
    type: string
    description: The full job description / requirements text.
  - name: job_title
    type: string
    description: The job title (used to disambiguate generic JDs).
output_schema:
  type: object
  properties:
    knockouts:
      type: array
      items:
        type: object
        properties:
          question_text: { type: string }
          type: { type: string, enum: ["yes_no", "years", "select"] }
          criterion: { type: string }
          required: { type: boolean }
        required: [question_text, type, criterion, required]
  required: [knockouts]
model: claude-sonnet-4-6
max_tokens: 1024
temperature: 0.0
notes: |
  Knockout questions are the single biggest auto-rejection vector
  (PRD § 3.4). Surface them aggressively but accurately — false
  positives are annoying, false negatives can cost the user the role.
---

You are detecting knockout questions in a job description. A knockout
question is a binary or short-answer question on the application form
that filters candidates before any human reads their resume.

Common knockout categories:
- Work authorization ("Are you authorized to work in <country>?")
- Years of experience ("Do you have at least N years of <skill>?")
- Education ("Do you hold a Bachelor's degree in <field>?")
- Certifications ("Are you AWS-certified?")
- Location ("Are you located in <city/region>?" or willing to relocate)
- Security clearance ("Do you hold an active <level> clearance?")
- Hard skills ("Do you have production experience with <stack>?")
- Visa sponsorship ("Will you require sponsorship?")

For each knockout you detect, output:
- question_text: the application form question, paraphrased clearly
- type: yes_no | years | select
- criterion: a snake_case key the system can use to compare against
  the user's profile (e.g., "us_work_auth", "min_5_years_python",
  "bachelors_cs")
- required: true if the JD treats it as a hard requirement, false if
  preferred / nice-to-have

Be conservative — only flag things that are plausibly going to appear
as a screening question. Soft skills like "team player" don't qualify.

Return JSON only. No markdown fences. No commentary.

Job title:
{{ job_title }}

Job description:
---
{{ job_description }}
---
