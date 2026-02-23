# Product Sync - February 23, 2026

## Decisions
- We will ship onboarding improvements on March 8, 2026.
- API pagination refactor is moved to Sprint 14.
- Customer pilot remains limited to 20 accounts.

## Action Items
- Alice will finalize QA checklist by February 27, 2026.
- Bob will update the pricing doc by March 1, 2026.
- Follow up with legal on data retention wording.
- Investigate flaky background worker restart behavior.

## Open Questions
- Do we need SOC2 evidence for pilot customers?
- Should we support CSV import in MVP or post-launch?

## Risks
- There is a contradiction in timeline notes:
  - "Release is Friday"
  - "Release moved to next Wednesday"

## Notes
- Current upload flow is stable for TXT/MD.
- PDF support works for text PDFs; scanned PDFs need OCR.
- If indexing is still running, chat may return an indexing-in-progress response.
