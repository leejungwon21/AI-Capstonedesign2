# Luna manual extraction review rubric

Compare Luna output against the Slack evidence, not against model preference.

For each expected event, mark:
- Event found: yes/no
- Hallucinated extra event: yes/no
- subject correct
- actor correct
- action correct
- event_type correct
- status correct
- deadline_text correct
- prerequisite correct
- constraint correct
- certainty correct
- evidence traceable to source_id

Especially inspect these case_04 traps:
1. M001: submission deadline belongs to submission requirement, not "writing completed".
2. M002: "아직 승인 전" must not become approval completed.
3. M003: final approval is a prerequisite/constraint for submission.
4. M004: Hong is approver; this does not mean approval was completed.
5. M005: a question about changing approver is not an actual change request/completion.
6. M006: direct change is not allowed; purchase team request is required; Yeonseoyeong is uncertain; Hong's "I'll check" is a confirmed plan.
7. M007: submission and receipt-check are future plans after approval.

Suggested summary metrics:
- Event recall = expected events found / expected events
- Hallucination count
- Field accuracy across core fields
- Context benefit = fields corrected by context run minus fields worsened by context run
