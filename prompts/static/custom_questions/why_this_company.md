---
name: custom_questions/why_this_company
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
notes: Target 80-150 words. Concrete, not "I love your mission".
---

Answer: "Why this company?" Write a tight, specific answer (80-150
words). Reference one or two concrete things about the company —
their actual product, a recent launch, an engineering choice, an
explicit hiring philosophy. Bridge to the candidate's experience.

Forbidden:
- "I'm passionate about your mission"
- "I love what you're doing"
- "I've always wanted to work at a company like X"
- Any phrase that could apply to 100 other companies

Return JSON only.

PROFILE: {{ profile }}
RESUME: {{ resume_json }}
JOB: {{ job }}
