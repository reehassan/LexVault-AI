# LexVault AI – Dev Log (Days 1–18)

Personal log of actual work completed on LexVault AI. Kept for future reference — what was built, what broke, and what was learned.

---

## Day 1 — Project Architecture Decision

- Picked multi-tenant RAG SaaS as the architecture, row-level tenant isolation over schema-per-tenant — same DB, same schema, every row scoped by a `Firm` FK.
- Rejected `django-tenants` outright. MVP doesn't need schema-per-tenant complexity, and honestly I don't yet understand it well enough to justify the extra moving parts.
- Locked the stack: Django, DRF (later), PostgreSQL 17, Docker Compose, django-environ, Python 3.14, UUIDv7 PKs, psycopg2, uv.
- The rule I'm building everything around: every row belongs to exactly one Firm, every query gets scoped to it. If I ever catch myself writing a query without a firm filter, that's a bug.

---

## Day 2 — Firm & Custom User Model

- Built `Firm` — UUIDv7 PK, name, created_at. Nothing fancy, it's just the tenant root.
- Extended `AbstractUser` for a custom `User` — UUID PK, FK to `Firm`.
- Decided usernames are unique per-firm, not globally. Two firms should both be able to have an `admin` user without colliding.
- Left `firm` nullable for now just to get `createsuperuser` working — flagged as temporary, needs to go away once things are wired properly.

---

## Day 3 — The AbstractUser Uniqueness Bug

- Hit a real gotcha: `AbstractUser` already makes `username` globally unique. My `(firm, username)` constraint didn't remove that — both existed at once, so per-firm duplicates were still blocked.
- Fixed by overriding `username` explicitly as non-unique. That immediately tripped Django's `auth.E003` check (`USERNAME_FIELD` must be unique).
- Silenced that check deliberately — I already know I'm building a custom auth backend to handle lookups properly, so the check doesn't apply to my actual design.

---

## Day 4 — Management Commands

- Built `createfirm` and `createfirmadmin` — the former makes a Firm, the latter makes a superuser scoped to one, with a manual duplicate-username guard within the same firm.
- Tested by hand: created two firms with admins named differently, then confirmed cross-firm duplicate usernames work as intended and same-firm duplicates get blocked.

---

## Day 5 — Django Admin Setup

- Registered `User` in admin with a firm-scoped `list_display`/`list_filter`.
- Found a real gap: Django admin's login uses `ModelBackend`, which looks up usernames globally, no firm filter. Only works right now because my test usernames happen to be unique across firms — this is fragile and needs the custom backend to actually fix it, not just paper over it.

---

## Day 6 — Debug Toolbar Fix

- `NoReverseMatch: 'djdt' is not a registered namespace` on `/admin/`. Toolbar was installed but never wired into `urls.py`.
- Added the URL include behind `DEBUG`, confirmed `INTERNAL_IPS` was set. Fixed.

---

## Day 7 — First Automated Test: Tenant Isolation

- Got pytest + pytest-django wired up properly, pointed at dev settings.
- Wrote the first real test proving `User.objects.filter(firm=firm_a)` actually isolates rows — first automated proof of the isolation design, not just something I checked by hand in the shell.

---

## Day 8 — Expanding the Regression Suite

- Added tests for duplicate usernames: allowed across firms, blocked within the same firm (proving the DB constraint actually raises `IntegrityError`, not just the app-level guard).
- 3 tests passing. This is now the locked-in suite protecting the tenant-isolation contract — if I ever accidentally revert the `unique=False` override, these catch it immediately.

---

## Day 9 — Custom Auth Backend

- Built `FirmBackend` — authenticates via `(firm, username, password)` instead of Django's global username lookup.
- Fails closed on `MultipleObjectsReturned` rather than guessing which user was meant.
- Kept `ModelBackend` as a fallback for admin login for now — a real trade-off, not a fix. Still need to decide: keep both long-term, or build a real firm-aware login form and drop `ModelBackend` outside admin.

---

## Day 10 — Backend Test Coverage + Coverage Tooling

- Wrote backend tests: correct auth, wrong password, wrong firm (the actual cross-tenant leak case), nonexistent user, and two identically-named users in different firms authenticating independently.
- 5 backend tests + 3 isolation tests, all passing.
- Set up `coverage` in `pyproject.toml`, scoped to `apps/`, excluding migrations/tests.

---

## Day 11 — Document and Chunk Models

- Formalized the schema doc — six entities total: Firm, User, Document, Chunk, SearchQuery, Citation. Locked UUIDv7 PKs, VARCHAR+CheckConstraint over native enums for status, denormalized `firm_id` on Chunk/SearchQuery, bge-small-en-v1.5 for embeddings, HNSW over IVFFlat.
- Grouped Document and Chunk into one `apps/documents` app rather than one-app-per-model — neither has independent meaning without its parent.
- Wrote the `Document` model: firm FK (cascade), uploaded_by FK (protect — no user-deletion story yet), status as TextChoices, composite index on (firm, status).
- Caught a field-name mismatch (`processing_status` vs `status`) before migrating — worth checking the model against the schema doc every time instead of trusting memory.

---

## Day 12 — Chunk Model and pgvector

- Wrote `Chunk`: document FK (cascade), denormalized firm FK (cascade) — deliberate duplication so tenant filtering never needs a join through Document.
- Learned the difference between constraints Django's field types already enforce vs. ones that need an explicit DB-level CheckConstraint regardless — kept the "redundant-looking" ones anyway as defense against raw SQL bypassing Django validation.
- Added `VectorField(dimensions=384)` and an HNSW index via `pgvector.django`.
- Hit a broken CheckConstraint attempt using a `__length` lookup that doesn't exist by default — fixed by comparing against an empty string directly instead.
- **The pgvector extension saga:** first migration failed — `type "vector" does not exist`. The Python package was installed but the Postgres *server* had no vector extension binary. Manual `CREATE EXTENSION` attempts failed the same way. Root cause: `postgres:17` doesn't ship pgvector at all. Switched the compose image to `pgvector/pgvector:pg17`, wiped the volume, re-migrated clean. Real lesson: the extension has to live in the Docker image, not just get installed via pip — client library and server extension are two separate things.

---

## Day 13 — Celery & Redis Setup

- Wrote `config/celery.py` — app instance, settings pulled from Django via `namespace="CELERY"`, `autodiscover_tasks()`.
- Added `add(x, y)` as the smoke-test task. Deliberately trivial — just proves the wiring works.
- Discovered `django` was missing from `docker-compose.yml` entirely — added it back (build context, volumes, port 8000).
- Hit a real network outage mid-build — Docker couldn't resolve anything over IPv6. Disabled IPv6 at the Docker daemon level, confirmed IPv4 worked underneath with a raw `curl -4`.
- Restored the non-root `appuser` pattern in the Dockerfile — had been dropped somewhere along the way, worker was running as root with no fix applied.
- Proved the real round-trip: `add.delay(2, 3)` in a live shell returned `5` through an actual worker process, not eager mode. Same check written as a passing pytest test using `CELERY_TASK_ALWAYS_EAGER`.
- Blew through 100% disk usage mid-session — `sentence-transformers` was quietly pulling full GPU `torch` (CUDA libs alone ran ~4GB per image) on a machine with no GPU. Spent real time trying to force `uv`'s CPU-only torch backend; confirmed via verbose `uv lock -v` output the feature isn't actually activating on this `uv` version. Deferred rather than kept fighting it — `sentence-transformers` isn't needed until Day 19 anyway, so commented it out of `pyproject.toml` for now.
- Cleaned ~75GB of stale Docker images/build cache in the process. Lesson either way: a dependency doesn't need to be in `pyproject.toml` before the week that actually uses it.

---
## Day 14 — PDF Upload & Document Creation

- Wrote the upload endpoint: `apps/documents/views.py`, `urls.py`, wired into `config/urls.py`.
- `validate_document_file()` — three checks in order: empty file, size ceiling, then real MIME sniffing via `python-magic` reading actual header bytes (never trusting the client's `Content-Type` or filename extension).
- `save_document_file()` — deliberately ignores the client's filename entirely, always writes `{uuid4()}.pdf`. Caught myself accidentally reintroducing a version that trusted the client's extension during a rewrite — fixed before it shipped. The MIME check already proves the file is a real PDF; the stored extension should reflect that fact, not the client's claim.
- `process_document` — Day 14 stub only. Flips status to `processing` and stops. Real extraction/chunking/embedding is Days 15–17, not now.
- Found and fixed a stale leftover: `apps/documents/tests.py` still imported a Celery smoke-test task (`add`) that no longer exists in `tasks.py` — this was blocking test collection entirely until removed. There was also a second, empty `apps/documents/tests/` package sitting alongside the `tests.py` file from an earlier recovery — deleted it, since Python can't have both a module and a package of the same name anyway.
- Wrote real tests: valid PDF, non-PDF rejected, oversized rejected, empty file rejected, unauthenticated request rejected. All passing, no mocking on the validation logic itself.
- Hit the `libmagic` ImportError a second time — same root cause as a few days ago, but this time because a Dockerfile rewrite for the non-root `appuser` fix dropped the `apt-get install libmagic1` step entirely. Re-added it with a comment explaining why it's there, specifically so a future edit doesn't drop it a third time.
- Reconciled a real discrepancy: `MAX_DOCUMENT_UPLOAD_SIZE` in settings said 20MB, but `04_api_contract.md` had locked 25MB with written reasoning. Decided 20MB is fine for a demo and updated the doc to match, rather than silently letting code and contract disagree.
- Full suite check: 36 tests passing, 97% coverage. One real gap coverage caught: the "no file field submitted" branch in the view had no dedicated test — different failure mode from "empty file content," worth adding.
- Manually tested the upload via `curl` against the real HTTP path (not `Client().force_login()`) to close the gap `force_login()` leaves — it skips both the login flow and CSRF checking entirely, which is fine for testing view logic in isolation but means the full auth-cookie-CSRF round trip stays unverified by the automated suite alone.

## Day 15 — PDF Extraction Service

- Wrote `extract_pages(path)` — pure function, no Django imports, zero DB access. PyMuPDF opens the file, returns `[{page, text}]` for every non-blank page.
- Custom exceptions: `ExtractionError` base, with `CorruptedPDFError`/`EncryptedPDFError`/`EmptyPDFError` subclasses.
- First draft leaked a file handle on the encrypted-PDF path — `document.close()` was only called after success, never reached if `EncryptedPDFError` fired first. Fixed with `try/finally` so it always runs regardless of exit path.
- Didn't assume PyMuPDF's exact behavior on encrypted files — generated a real encrypted PDF and ran it through the function by hand before writing the test, confirmed it raises `EncryptedPDFError` correctly rather than getting caught by the broad `except Exception` around `fitz.open()`.
- Wrote 7 tests: valid multi-page PDF, blank pages skipped without erroring, all-blank raises `EmptyPDFError`, encrypted, corrupted, missing file, and — the one that actually matters — page numbers stay correct across a skipped blank page (page 3 stays page 3, doesn't get renumbered to page 2). This one directly protects the citation-accuracy metric later.
- Real scare mid-session: thought a test file was written and confirmed via `cat`, but the "confirmation" was actually this chat's own scrollback repeating earlier content, not a real terminal read. The file was genuinely empty on disk (`wc -l` = 0) despite looking fine in the pasted output. Caught it before running anything destructive, but it's a real lesson: verify file state with `wc -l`/`cat` against the actual filesystem, don't trust a chat transcript as proof something landed on disk.
- Consolidated `apps/documents/tests.py` into the `tests/` package alongside `test_extractor.py` — a flat single file doesn't scale once there's more than one or two test modules, and Day 16 adds `test_chunker.py` next.
- Full suite: all passing after the move, no regressions.

## Day 16 — Chunking Service

- Wrote `chunk_pages(pages, chunk_size=350, overlap=50)` — same pure-function design as the extractor. Sliding token window per page, never spans page boundaries.
- Real design decision, not in the roadmap by default: chunks never cross a page. The original chunking ADR allowed page-spanning chunks with "record the page where it starts" — changed this on purpose, since the citation metric needs an unambiguous page number per chunk, not a convention.
- Guard added: raises `ValueError` if `overlap >= chunk_size`, since that combination would infinite-loop instead of crashing — a silent hang is worse than a loud failure.
- Tokenizer is `tiktoken`'s `cl100k_base`, not the embedding model's own tokenizer as originally planned — decouples chunking from which embedding model eventually gets used, at the cost of `token_count` being an approximation rather than exact parity with bge-small's tokenizer.
- 8 tests: empty input, single short page, large page splitting into multiple chunks, exact-boundary size, never-spans-pages, blank pages skipped, determinism (same input twice → identical output), and the overlap/chunk_size guard.
- Spent most of tonight's real time on an unrelated blocker: `sentence-transformers` was still resolving full GPU torch (73 `nvidia-*` packages) despite multiple previous attempts to force CPU-only. Tried `torch-backend` config, `--preview`, and a direct wheel-URL pin — none of them actually took effect; verbose `uv lock -v` output showed it kept resolving a macOS ARM wheel regardless of the override. Gave up trying to fix the root cause tonight and instead added a `uv_cache` Docker volume so dependency downloads are cached across rebuilds — doesn't fix GPU torch being installed, but stops every unrelated dependency change from re-triggering a 15+ minute redownload. Real fix still open.
- Replaced the old `chunking_strategy.md` and `error_classifications.md` ADRs with one combined ingestion-pipeline ADR reflecting what's actually built — the old docs had drifted (500 vs 350 token chunks, embedding-model tokenizer vs tiktoken, page-spanning vs never-spanning) since they were written before implementation started.

## Day 17 — Celery Pipeline Assembly

- Wired `extract_pages()` and `chunk_pages()` into the real `process_document` task: `Document → processing → extract → chunk → ready`.
- Real scope decision made up front: `Chunk` rows aren't written yet. `Chunk.embedding` is a non-nullable `VectorField`, and embeddings don't exist until Day 19–20 — writing chunk rows with a placeholder vector felt like the wrong tradeoff. Extraction and chunking run in-memory this stage, proving the pipeline works end to end; actual chunk persistence is Day 20's job, once there's a real embedding to store alongside it.
- `page_count` is total PDF page count via `fitz`, not "pages with text" — decided deliberately, since a user asking "how many pages" wants the real number, not an internal implementation detail about which pages had extractable text.
- Real bug caught by a failing test, not by review: the standalone `fitz.open()` call used just to read total page count wasn't wrapped in the same exception handling as `extract_pages()`. A corrupted file failed at that first open, fell through to the generic `except Exception` fallback, and reported "Unexpected processing error" instead of the correct, specific "Unable to open PDF" message. Fixed by wrapping that call so it raises the same `CorruptedPDFError` the extractor uses — both open attempts now fail identically.
- Added a broad `except Exception` fallback around the whole pipeline, separate from the specific `ExtractionError` handling — so any future bug or unclassified failure still ends in `status=failed` with a generic message, instead of leaving a document stuck in `processing` forever with no way to know something went wrong.
- Two integration tests: real PDF through the full pipeline reaches `ready` with correct `page_count`; corrupted PDF reaches `failed` with the correct, specific error message.
- Kept `transaction.atomic()` around the final status update even though it's not protecting much yet with no `Chunk` rows being written — it's there for Day 20, when it'll actually matter.


## Day 18 — Ingestion Pipeline Testing & Status Tracking

- Extended `test_pipeline.py` to cover the remaining failure modes through the *real task*, not just the extractor directly: encrypted PDF and empty/no-text PDF both now go through `process_document` end-to-end, not just `extract_pages()` in isolation.
- The encrypted-PDF test exercises a genuinely different code path than the corrupted-file test — opening an encrypted PDF succeeds (no password needed just to open), so the failure has to come from `extract_pages()`'s own `is_encrypted` check, not the page-count wrapper fixed on Day 17. Worth confirming this distinction rather than assuming both tests hit the same line.
- Added a real tenant-isolation test through the pipeline: two firms, two documents, both processed, confirming each document's `page_count` and `storage_path` stay correctly scoped and never cross firms. This was the one Day 18 item that wasn't just "add another PDF variant" — genuinely new coverage.
- Reorganized `test_pipeline.py` — helpers grouped together, fixtures grouped together, tests grouped together — since the file had grown by simple appending across two sessions and was getting harder to scan. Also deduplicated a `save_document_file` import that had been repeated inline in every fixture.
- Full suite: 56 tests passing, 98% coverage. Confirmed `apps/documents/tasks.py`'s one uncovered branch (87%) is the generic `except Exception` fallback — a legitimate, known gap, since none of the current tests trigger a truly unclassified failure. Not fixed tonight; noted as a real TODO rather than ignored.

## The CPU-torch resolution — finally solved

- This had been open since Day 13, deferred twice, across multiple failed attempts: `torch-backend` config, `--preview` flag, a direct URL pin in `[tool.uv.sources]` — none of them ever took effect. Every attempt still resolved full GPU torch (73 `nvidia-*` packages, ~4-5GB per image), confirmed repeatedly via `uv lock -v` showing GPU wheels selected regardless of config.
- Root-caused properly this time instead of trying another blind guess. Two real findings, found in sequence:
  1. `pyproject.toml` had no `[tool.uv]` platform restriction, so `uv.lock` was resolving universally — for every OS and Python version the project could theoretically run on, not just this actual Linux+3.14 container. A single URL pin can't satisfy every platform at once, so uv fell back to its normal resolver for torch specifically. Added `environments = ["sys_platform == 'linux' and python_full_version >= '3.14'"]` to narrow the lock to the one real target.
  2. That alone wasn't enough — `[tool.uv.sources]` was still being silently ignored. Built a minimal isolated reproduction outside the real project (`torch` listed as a **direct** dependency, same URL pin) — it worked immediately, `source` correctly showed the pinned URL. Compared against the real project: `torch` was only ever present as a **transitive** dependency, pulled in by `sentence-transformers`, never listed directly. That's the actual mechanism: `[tool.uv.sources]` overrides only apply to packages listed directly in `dependencies`, not to transitive dependencies pulled in by another package. Adding `"torch"` directly to `dependencies` — redundant with what `sentence-transformers` already requires, but that's fine, they resolve to one shared version — finally let the override take effect.
- Also caught and fixed a `uv lock` false-negative along the way: `uv lock` was repeatedly reporting `Resolved 137 packages in 4ms` — far too fast to be a real resolution — because it kept deciding the existing (stale, broken) lock file "satisfies workspace requirements" and skipping re-resolution entirely, even after `pyproject.toml` had genuinely changed. `rm uv.lock` before every `uv lock` call is what actually forces a fresh resolution; a plain `uv lock` alone isn't reliable for this.
- Verified, not assumed: `nvidia` package count in the lock file went from 73 to 0, image size dropped from 5.51GB to 1.5GB per image, `torch.__version__` reports `2.13.0+cpu`, `torch.cuda.is_available()` returns `False`.
- Real lesson: three earlier fix attempts all failed silently instead of erroring, which made this genuinely hard to diagnose — no error message ever pointed at "this package is only transitive" or "your lock file is stale." The thing that actually broke the logjam was building a minimal isolated reproduction to separate "is my syntax wrong" from "is something in my real project's config interfering" — comparing the two side by side is what surfaced the direct-vs-transitive distinction, not another round of guessing at uv flags.


## Day 19 — Local Embedding Service

- Wrote `embed_chunks(chunks)` — takes the same chunk-dict shape `chunk_pages()` produces, returns a parallel list of 384-dim float vectors using `bge-small-en-v1.5` via `sentence-transformers`, CPU-only.
- Model loads once via a lazy module-level singleton, reused across every call — reloading a transformer model per call would be slow and pointless. Verified this actually works, not just assumed: a dedicated test checks the module-level `_model` reference is the same object across two separate calls.
- Input validation mirrors the extractor/chunker's pattern: a dedicated `InvalidChunkInputError` for non-list input, chunks missing the `chunk_text` key, or empty/whitespace-only text — same "fail loud and specific, not silent" philosophy as the rest of the pipeline.
- Real infrastructure step taken proactively this time, not after hitting a problem: added a `hf_cache` Docker volume before writing any embedder code, since `sentence-transformers` downloads the model (~130MB) from Hugging Face on first use and caches it locally — without a persistent volume, that cache would live in the container's writable layer and get silently wiped on every rebuild, same failure mode as the `uv_cache` issue from a few nights ago. Applied the lesson before repeating the mistake instead of after.
- This is the first Day since the CPU-torch fix landed where a `sentence-transformers`-dependent feature actually got built — first real proof the infrastructure fix holds up under real use, not just an isolated `torch.cuda.is_available()` check.
- 7 tests: single chunk, multiple chunks (order + count preserved), empty list, and all three invalid-input cases, plus the model-reuse check. All passing, first run took ~70s for the one-time model download, cached after that.
- `embed_chunks()` is fully built and tested in isolation but **not yet wired into `process_document`** — that's Day 20's job: call it inside the task, pair each chunk with its embedding, `bulk_create` real `Chunk` rows, only then transition to `ready`. Right now the pipeline still stops at chunking, same as Day 17-18.