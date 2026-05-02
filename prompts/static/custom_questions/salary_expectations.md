---
name: custom_questions/salary_expectations
kind: static
version: 1
inputs:
  - name: profile
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
max_tokens: 256
temperature: 0.1
notes: |
  60-100 words. Pull profile.salary_floor + currency. If the JD
  discloses a band, mention alignment. Otherwise give a tight range
  starting at the floor.
---

Answer: "What are your salary expectations?" 60-100 words.

Rules:
- Use profile.salary_floor + salary_currency as the floor.
- If job.salary_text discloses a band, acknowledge alignment with
  it (or where you sit in it).
- If not, give a tight range: floor to floor*1.2.
- Never go below the user's stated floor.
- Mention notice_period_days if profile has it.

Return JSON only.

PROFILE: {{ profile }}
JOB: {{ job }}
