---
name: outreach_brief
kind: meta
version: 1
inputs:
  - name: profile
    type: object
  - name: contact
    type: object
    description: Name, role, company, briefing_md from public signals.
  - name: job
    type: object
    description: Optional — null when intent is cold_intro and no specific role attached.
  - name: intent
    type: string
    description: One of "referral", "application_support", "cold_intro".
output_schema:
  type: object
  properties:
    hook: { type: string }
    bridge: { type: string }
    pitch: { type: string }
    ask: { type: string }
    tone: { type: string, enum: ["casual-warm", "professional-direct", "concise-formal"] }
    length_target_words: { type: integer, minimum: 60, maximum: 220 }
    donts:
      type: array
      items: { type: string }
  required: [hook, bridge, pitch, ask, tone, length_target_words, donts]
model: claude-sonnet-4-6
max_tokens: 1024
temperature: 0.3
notes: |
  Length targets:
    referral 80-150 words; application_support 100-180; cold_intro 60-120.
  This is the brief, NOT the message. The user reviews + edits before
  Layer-2 execution. Per Architecture § 6.
---

Produce an outreach brief — a structured strategy for one specific
message to one specific person. The user reviews this brief and edits
it before the message is generated.

Branch on `intent`:
- referral: ask for a referral / pre-application introduction. Be
  warm, specific, low-friction. Pull a hook from the contact's
  briefing.
- application_support: candidate has already applied. Ask for
  feedback or to flag the application. Mention the role + when applied.
- cold_intro: no role context — building a relationship. Hook +
  short pitch + an ask that's NOT a job ("would love to hear how X
  has changed since you started", etc.).

Output fields:
- hook: ONE specific concrete thing from the contact's briefing
  (recent talk, product launch, blog post). NOT "I love your
  mission". If briefing is empty, the hook is something specific
  from the company's recent public activity that the user can verify.
- bridge: connect the hook to the candidate. Why is the candidate
  reaching out to THIS person?
- pitch: 1-2 sentence value statement from the candidate. Concrete,
  not adjective-stacking.
- ask: the specific small action the candidate wants. Always small.
  "30-min chat", "intro to the EM", "feedback on application".
- tone: pick one based on contact role + company stage.
- length_target_words: see notes.
- donts: forbidden phrases for the execution prompt:
  - "I hope this finds you well"
  - "I came across your profile"
  - "I'm reaching out because"
  - "leverage", "synergy", "passionate"
  - Three parallel adjectives in a row

Return JSON only.

PROFILE: {{ profile }}
CONTACT: {{ contact }}
JOB: {{ job }}
INTENT: {{ intent }}
