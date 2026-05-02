---
name: custom_questions/biggest_project
kind: static
version: 1
inputs:
  - name: profile
    type: object
  - name: resume_json
    type: object
  - name: job
    type: object
output_schema:
  type: object
  properties:
    answer_md: { type: string }
    word_count: { type: integer }
  required: [answer_md, word_count]
model: claude-sonnet-4-6
max_tokens: 1024
temperature: 0.3
notes: Target 150-250 words. STAR-ish (situation/task/action/result) without being formulaic.
---

Answer: "Tell us about a difficult / impactful project."
150-250 words. Pick one project from resume_json that maps best to
the target job's stack or scope.

Structure (don't label, just follow):
- Situation: what was the problem / why it mattered.
- Task: what you specifically owned.
- Action: what you did (concrete, technical).
- Result: what changed (numbers if available in source).

Forbidden: making up metrics. If resume doesn't have numbers, don't
invent them — say "shipped to all customers" or similar.

Return JSON only.

PROFILE: {{ profile }}
RESUME: {{ resume_json }}
JOB: {{ job }}
