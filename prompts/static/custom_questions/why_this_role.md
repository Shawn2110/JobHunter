---
name: custom_questions/why_this_role
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
max_tokens: 768
temperature: 0.3
notes: Target 80-150 words. Map the candidate's trajectory to the role's scope.
---

Answer: "Why this role?" Map the candidate's trajectory to the
specific scope and shape of THIS role (not just the title). 80-150
words.

What you must include:
- One specific aspect of the role (responsibility, scope, stack).
- One specific thing in the candidate's history that fits it.
- The forward-looking reason (what they want to do next).

Forbidden: generic "I'm looking for growth opportunities".

Return JSON only.

PROFILE: {{ profile }}
RESUME: {{ resume_json }}
JOB: {{ job }}
