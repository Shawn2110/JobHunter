---
name: custom_questions/why_leaving
kind: static
version: 1
inputs:
  - name: profile
    type: object
  - name: resume_json
    type: object
output_schema:
  type: object
  properties:
    answer_md: { type: string }
    word_count: { type: integer }
  required: [answer_md, word_count]
model: claude-sonnet-4-6
max_tokens: 512
temperature: 0.2
notes: Target 60-120 words. Forward-looking, never bash a previous employer.
---

Answer: "Why are you leaving / why did you leave your last role?"
60-120 words. Forward-looking, never speak negatively of a prior
employer or manager.

Frame: what you've gotten from the role + what you're looking to do
next that requires a change. If profile.about_me_text contains a
genuine reason (career pivot, scope change, founder-driven), use it.

Return JSON only.

PROFILE: {{ profile }}
RESUME: {{ resume_json }}
