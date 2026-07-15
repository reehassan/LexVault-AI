# LexVault AI — Extraction Error Classification

Reference for how each extraction failure is handled: what gets logged,
what the user sees, and whether it warrants proactive alerting.

---

## `EncryptedPDFError`

- **Classification:** Visible to user
- **Log level:** `WARNING`
- **User sees:** "This PDF is password-protected. Please remove the
  password and re-upload."
- **Why not critical:** Expected, routine user input issue. Nothing wrong
  with the system — the user's file genuinely needs a password removed
  before it can be processed. No developer action needed.

---

## `EmptyPDFError`

- **Classification:** Visible to user
- **Log level:** `WARNING`
- **User sees:** "No readable text was found in this PDF. It may be a
  scanned document — try uploading a text-based version."
- **Why not critical:** Most commonly caused by a scanned/image-only PDF,
  which is a real and expected category of "input LexVault doesn't yet
  support" (OCR is a separate, unbuilt feature). Not a system bug.
- **Worth monitoring over time:** if this rate spikes unexpectedly across
  many documents, it may indicate OCR support should be prioritized —
  but that's a product decision, not an incident.

---

## `CorruptedPDFError`

- **Classification:** Visible to user
- **Log level:** `ERROR`
- **User sees:** "This file could not be read. It may be corrupted or
  not a valid PDF."
- **Why ERROR, not WARNING, despite still being visible-only:** unlike
  the other two, a corrupted file could theoretically also indicate an
  upload/storage bug on LexVault's side (e.g. a truncated write, a
  broken storage backend) rather than purely a bad input file — worth a
  slightly higher log severity to make it easier to spot in log review,
  even though the user-facing response is the same "handled gracefully,
  not critical" treatment.

---

## Unclassified `ExtractionError` (any future subclass not explicitly handled)

- **Classification:** Visible to user (generic message) + logged as ERROR
- **User sees:** "This document could not be processed."
- **Why this tier exists:** defensive catch-all — if a new exception
  subclass is added later and the Celery task isn't updated to handle it
  specifically, the pipeline still fails gracefully instead of crashing
  with an unhandled exception. The generic ERROR log is a signal that a
  new failure mode has appeared and probably deserves a proper subclass
  + specific handling + a real user message, not just this fallback.

---

## Critical (Sentry-style alerting) — not yet implemented

None of the current exception types are classified as critical, because
each represents a routine, expected category of "this particular file
has a problem" rather than "the system itself may be malfunctioning."

**What WOULD warrant critical alerting**, once built (e.g. via Sentry or
similar):
- A sudden, sustained spike in `CorruptedPDFError` across many unrelated
  uploads in a short window — could indicate a storage/upload bug, not
  bad files.
- Any exception from `extract_pages()` that ISN'T an `ExtractionError`
  subclass at all — i.e. `fitz` or the extraction logic raising something
  entirely unexpected, which would currently propagate up uncaught and
  crash the Celery task rather than being handled gracefully.
- `process_document` repeatedly failing for reasons unrelated to file
  content (e.g. `default_storage.path()` throwing because the storage
  backend itself is unreachable).

This is intentionally left as a TODO — not built now, since there's no
production traffic yet to monitor and no Sentry integration configured.
Revisit once deployed.