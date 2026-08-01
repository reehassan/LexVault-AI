# ADR-006 — Document Ingestion Pipeline

## Status
Accepted (upload, extraction, chunking — Days 14–16). Embedding/storage stage (Day 17+) is a stub, documented below as planned but not yet implemented.

---

## Context

An uploaded PDF has to become searchable content: a file on disk becomes text, text becomes chunks, chunks will eventually become vectors. This pipeline runs asynchronously via Celery so the upload request returns immediately (per `02_arcitechture.md`'s ingestion pipeline decision), and every stage has to preserve page attribution precisely, since the project's proof metric (`01_mvp_scope.md`) is 90% correct-citation accuracy — right document, right page number, no partial credit.

Four concerns had to be decided independently: how to validate/store the raw file, how to extract text per page, how to chunk that text, and how each stage fails without corrupting state or losing information.

---

## Decision 1 — Upload validation and storage

**Validate before storing, in order: empty check → size ceiling → real MIME sniff.**

`validate_document_file()` checks, in this specific order, cheapest-first: zero-byte files rejected outright, then a size ceiling (`MAX_DOCUMENT_UPLOAD_SIZE`, currently 20MB — chosen as demo-appropriate, large enough for real contracts, small enough a bad upload can't stall Celery for minutes), then MIME type via `python-magic` reading the file's actual header bytes.

MIME sniffing over trusting `Content-Type` or the filename extension, because both are client-supplied and spoofable — `python-magic` reads real magic-number bytes, so a renamed `.txt` file is caught regardless of what the browser claims.

**Storage path is fully server-generated: `firms/{firm_id}/{uuid4()}.pdf`.** The client's original filename never touches disk I/O — only `Document.filename` stores it, for display only. This was a deliberate rework partway through Day 14: an earlier draft built the stored extension from the client's filename via `os.path.splitext`, which reintroduced a small trust gap (the extension came from the client, not from the verified MIME type). Fixed to hardcode `.pdf` unconditionally, since the MIME check already proves that's what the file is — the stored extension should reflect a verified fact, not a client claim.

---

## Decision 2 — PDF text extraction

**PyMuPDF (`fitz`), one page at a time, via a pure function with zero Django dependency.**

`extract_pages(path)` takes a file path, returns `[{"page": N, "text": "..."}]` for every page with real text content. No Django imports, no database access — this mirrors the chunker's design and for the same reason: fast plain-pytest tests, reusable outside the Celery task that calls it.

**Four distinct failure modes, not one generic exception:**
- `CorruptedPDFError` — `fitz.open()` itself throws (garbage bytes, truncated file, or genuinely broken PDF structure).
- `EncryptedPDFError` — the PDF opens but `document.is_encrypted` is true. Confirmed by hand, not assumed: a real AES-256-encrypted test PDF was generated and run through the function to verify it actually raises this specific exception rather than getting misclassified by the broader `except Exception` around `fitz.open()`. This mattered because some encryption states could plausibly throw at `open()` time rather than surface via the `is_encrypted` flag afterward — worth testing directly rather than trusting the two failure modes are cleanly separated.
- `EmptyPDFError` — every page came back with no extractable text (most commonly a scanned/image-only PDF with no text layer — OCR is out of scope for this MVP).
- Individual blank pages within an otherwise-real document are **not** an error — they're silently skipped. Only "every page blank" raises `EmptyPDFError`. This distinction matters: a document with one real page among several blank separator pages is normal, not a failure.

**Resource safety:** `document.close()` runs inside a `try/finally`, not scattered after each success path — an earlier draft only closed the file handle after the encrypted-check passed, meaning an encrypted PDF leaked its handle since `EncryptedPDFError` was raised before that point was reached. Fixed by moving everything after `fitz.open()` succeeds into a `try/finally` block.

---

## Decision 3 — Chunking

**Fixed-size overlapping token windows: 350 tokens per chunk, 50-token overlap, chunks never span page boundaries.**

`chunk_pages(pages, chunk_size=350, overlap=50)` — pure function, same zero-Django-dependency design as the extractor. Takes the extractor's output directly, returns `[{"chunk_index": N, "page_number": N, "chunk_text": "...", "token_count": N}]`.

**Fixed-size over semantic/paragraph-based chunking**, per `02_arcitechture.md`'s original reasoning, which still holds: predictable, testable boundaries are needed for the citation-accuracy proof metric, and PDF layout inconsistency across arbitrary documents makes paragraph detection unreliable without heavier NLP tooling this project doesn't need.

**350 tokens, not 500.** The originally-planned 500-token size (from the now-superseded `chunking_strategy.md`) was revised down during implementation to stay comfortably under bge-small-en-v1.5's 512-token limit with real headroom — 500 tokens of chunk text plus a query-instruction prefix (a common technique for instruction-tuned embedding models) could exceed the model's limit; 350 leaves margin.

**Tokenizer: `tiktoken`'s `cl100k_base` encoding, not the embedding model's own tokenizer.** This is a real, deliberate divergence from the original plan (which called for the embedding model to supply its own tokenizer via dependency injection). `tiktoken` was chosen instead because it's a fast, dependency-light, already-available library that gives a consistent, real token count without requiring the embedding model itself to be loaded just to measure chunk boundaries — decoupling chunking from which embedding model is eventually used. The tradeoff: `cl100k_base`'s token boundaries won't exactly match bge-small's own tokenizer, so `token_count` is an accurate proxy for chunk size, not a guarantee of the literal token count bge-small will see. Acceptable for a fixed-size chunking strategy where the goal is consistent, bounded chunk sizes — not exact token parity with a specific downstream model.

**Chunks never span page boundaries — this is a real divergence from the original ADR, decided deliberately.** The earlier plan allowed a chunk to span two pages and recorded "the page where the chunk begins." The implemented version instead resets the token window at every page boundary, so a chunk is always drawn from exactly one page's text. Reasoning: given the citation-accuracy metric requires an *exact* page number match with no partial credit, a chunk's page number should be unambiguous by construction, not a convention ("we record the start page even though content might belong to the next page"). This trades a small amount of chunking efficiency (a chunk near a page boundary may be shorter than 350 tokens rather than pulling content from the next page) for zero ambiguity in citation.

**`chunk_index` increments sequentially across the whole document, not reset per page** — this matches the schema's `UniqueConstraint(document, chunk_index)`, which assumes one continuous index space per document.

**Guard against misconfiguration:** `chunk_pages` raises `ValueError` if `overlap >= chunk_size`, since that combination would either loop forever or produce chunks that never advance the window. Caught during code review before it shipped, not found via a bug report — worth noting because it's the kind of input-validation gap that's easy to miss when only testing the "happy path" default parameters.

---

## Decision 4 — Error handling philosophy across the pipeline

Every stage distinguishes **expected, routine failures** (bad input file) from **unexpected system failures** (something is actually broken), and logs/surfaces them differently:

- Expected failures (`EncryptedPDFError`, `EmptyPDFError`) log at `WARNING` and produce a specific, actionable user-facing message.
- `CorruptedPDFError` logs at `ERROR` rather than `WARNING` despite being routine-ish, because a corrupted file could theoretically also indicate a storage/upload bug on this system's side (a truncated write, a broken storage backend), not purely a bad input file — worth a higher severity so it's easier to spot in log review even though the user-facing treatment is the same.
- Any future `ExtractionError` subclass not yet explicitly handled still fails gracefully via a generic catch-all rather than crashing the Celery task outright — the generic ERROR log in that case is itself a signal that a new failure mode has appeared and probably deserves real handling, not just the fallback.

None of the current failure types are classified as needing proactive alerting (e.g., Sentry) — each represents "this particular file has a problem," not "the system may be malfunctioning." What *would* warrant alerting, once built: a sustained spike in `CorruptedPDFError` across unrelated uploads (points at a storage bug, not bad files), or any exception escaping `extract_pages()`/`chunk_pages()` that isn't one of the defined custom exceptions at all. Deferred — no production traffic yet to monitor, no Sentry configured.

---

## Current pipeline state (Day 16)

```
PDF Upload
  → validate_document_file()   [size, MIME]
  → save_document_file()        [server-generated path]
  → Document row created, status=uploaded
  → process_document.delay(document_id)
      → status=processing
      → [STUB — Day 17 will wire in the real chain below]
```

**Not yet wired into `process_document`:** `extract_pages()` and `chunk_pages()` exist and are independently tested, but the Celery task itself is still the Day 14 stub — it flips status to `processing` and stops. Day 17's job is assembling `Document → processing → extract → chunk → store Chunk rows → ready`, inside `transaction.atomic()`, with `failed` + `error_message` on any exception. Embedding generation (Day 19+) and vector storage are not yet started.

---

## Consequences

**Positive:** every stage is independently testable with zero Django/DB overhead for extraction and chunking specifically; page attribution is unambiguous by construction; failure modes are specific enough to give users actionable messages rather than a generic "something went wrong."

**Negative / accepted tradeoffs:** `tiktoken`'s token boundaries don't exactly match bge-small's tokenizer, so `token_count` is an approximation, not an exact figure the embedding model will reproduce. Chunks near page boundaries may be shorter than the 350-token target. Neither is expected to matter at demo scale (3 documents, 20 test questions) but would be worth revisiting if this pipeline were ever pointed at real production documents with tighter embedding-budget constraints.