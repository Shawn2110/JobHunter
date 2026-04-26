---
name: parse_resume
kind: static
version: 1
inputs:
  - name: resume_text
    type: string
    description: Plain-text contents extracted from the user's resume PDF or DOCX.
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
  required: [name, experience, education, skills]
model: claude-sonnet-4-6
max_tokens: 4096
temperature: 0.0
notes: |
  Strict, deterministic extraction. Truthfulness matters: do NOT
  invent fields the source resume does not contain. Missing fields
  return null; missing arrays return [].
---

You are a meticulous resume parser. Extract the following resume into
clean, structured JSON. Follow the schema exactly. Do not invent
information; if the resume does not state something, return null (for
scalars) or [] (for arrays).

Rules:
- Preserve the candidate's wording for bullets — do not paraphrase.
- For dates, keep the format the resume uses ("Jan 2023", "01/2023",
  "2023-01"). Do not normalize.
- "Present", "Current", "Now" map to `end_date: null` for the most
  recent role.
- Skills should be a flat deduplicated list, not nested by category.
  Include both hard and soft skills if explicitly listed.
- For `links`, extract any handle URLs the resume includes (GitHub,
  LinkedIn, portfolio, LeetCode, Kaggle, personal site). Set `kind`
  to one of: github, linkedin, leetcode, kaggle, portfolio, blog, other.
- Return only the JSON object — no markdown fences, no commentary.

Resume text:
---
{{ resume_text }}
---
