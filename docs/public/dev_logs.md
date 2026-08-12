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

## Day 20 — Embedding Pipeline Integration

- Wired `embed_chunks()` into `process_document`, finally connecting the three independently-built-and-tested services (extract, chunk, embed) into one real write path. `Chunk` rows are now actually persisted for the first time since the schema was designed back on Day 12.
- Real field-name mapping caught before it became a bug: `chunk_pages()` returns `chunk_text`, but the `Chunk` model field is `content`. Easy to miss if copying field names by assumption instead of checking the model directly.
- Deliberate transaction-scope decision: extraction, chunking, and embedding all run *outside* `transaction.atomic()` — only the actual DB writes (`bulk_create` + status update) are inside it. These are slow, CPU-bound operations; holding a Postgres transaction open for however many seconds embedding takes would tie up a connection for no reason and hurt concurrency once multiple documents process at once. `atomic()` protects database consistency, not gates CPU work — worth being explicit about that distinction rather than wrapping the whole thing defensively.
- Added a genuine sanity check before any DB write: `assert len(chunks) == len(embeddings)`. If `embed_chunks()` ever returned a mismatched count due to a future bug, this catches it before a `zip()` silently truncates to the shorter list and writes wrong data.
- New `EmptyDocumentError`: if `chunk_pages()` somehow returns zero chunks, the document now explicitly fails instead of silently reaching `ready` with nothing searchable — a document marked "ready" that has nothing a search could ever find is a worse failure mode than an honest `failed`.
- **The rollback test was the real work today, not a formality.** First draft asserted `pytest.raises(Exception)` around the whole task call — wrong, because `process_document`'s own `except Exception` fallback (built Day 17) catches the forced failure and marks the document `FAILED` gracefully, exactly as designed. The task doesn't propagate the exception; it handles it. Rewrote the test to check the actual outcome (`status == FAILED`, zero orphaned chunks) instead of an exception that was never going to happen.
- Proved the rollback test is real, not passing by coincidence — the specific failure mode the original build-steps doc warned about. Manually removed `transaction.atomic()` from `tasks.py`, reran just this test: failed with `assert 2 == 0` — two real orphaned `Chunk` rows left behind, exactly the bug the test exists to catch. Restored `atomic()`, reran: passed. This round-trip is the only way to know a rollback test actually tests something, since the default `pytest.mark.django_db` fixture wraps every test in its own transaction that would otherwise mask a missing `atomic()` entirely — needed `@pytest.mark.django_db(transaction=True)` specifically to get real `TransactionTestCase`-style behavior.
- Side effect: `tasks.py`'s previously-untested generic `except Exception` fallback branch (open since Day 17, 87% coverage) is now at 100% — the rollback test's forced failure is exactly the kind of unclassified exception that branch exists to catch.
- Full suite: 65 tests passing, 99% coverage.

## Day Extra (Debugging and tests) — Pipeline Validation & Production-Like Document Testing

- Tested the complete ingestion pipeline with real legal documents instead of only synthetic test PDFs. Added multiple USA government legal documents including Federal Rules of Civil Procedure, Federal Rules of Evidence, and Supreme Court opinions to `test_documents/` for realistic workload testing.
- Built the manual upload workflow through Django shell first to verify the complete path: `Document creation → file storage → Celery task → extraction → chunking → embedding → Chunk persistence`.
- Found and fixed a small shell testing issue: forgot to import `default_storage` while manually creating documents. Confirmed the correct imports and storage flow before continuing.
- Verified the pipeline successfully processed a real Federal Rules of Civil Procedure PDF:
  - Document created successfully.
  - Celery task completed.
  - 391 chunks generated.
  - Embeddings stored correctly.
  - Document status reached `ready`.
- Added more confidence by checking tenant ownership after processing:
  - `document.firm_id` matched `uploaded_by.firm_id`.
  - Confirmed chunks remained attached to the correct document and firm.
- Improved the testing workflow by creating a plan to move away from manual shell uploads. Instead of repeatedly creating documents through Django shell, the next improvement is a reusable document uploader script that uses the real upload path and can batch upload legal PDFs automatically.
- Reviewed the existing upload architecture:
  - `upload_document` view already handles authentication, validation, storage, document creation, and Celery dispatch.
  - Confirmed the correct place for automation is a separate uploader utility, not inside the Django view.
  - The uploader will act like a client sending files to the API, keeping production behavior identical to real users uploading documents.
- Ran the document test suite:
  - `docker compose exec django pytest apps/documents/tests -v`
  - Result: **34 tests passed**
- Verified Django project health:
  - `python manage.py check` → no issues.
  - `makemigrations --check` → no pending migrations.
- Attempted to run coverage reporting using `pytest --cov`, discovered `pytest-cov` is not installed in the environment. Existing coverage setup from previous days uses the `coverage` package directly, so pytest coverage flags are currently unavailable until the plugin is added.
- Current state:
  - Upload endpoint works.
  - Storage layer works.
  - Celery pipeline works.
  - Extraction works.
  - Chunking works.
  - Local embeddings work.
  - Real legal documents successfully process end-to-end.
  - Automated test suite remains green.
- Next milestone: build the vector search layer — the system can now ingest legal knowledge; the next step is retrieving relevant chunks and generating grounded answers.

## Day 21 — Vector Similarity Search with pgvector

- Built the first retrieval layer of LexVault AI — the system can now search stored document chunks using vector similarity instead of keyword matching. This is the first step where the RAG pipeline moves from "knowledge ingestion" into "knowledge retrieval."

- Created `apps/search/services/retriever.py` with `retrieve_chunks(query_embedding, firm_id, top_k)` as the main retrieval function.
  - Input:
    - Query embedding vector.
    - Current firm's ID.
    - Number of chunks to retrieve.
  - Output:
    - Top matching chunks.
    - Similarity scores.
    - Document metadata needed later for citations.

- Learned the critical difference between cosine similarity and cosine distance:
  - Humans think in similarity: higher = more similar.
  - pgvector's `CosineDistance` returns distance: lower = more similar.
  - Formula:
    ```
    cosine_distance = 1 - cosine_similarity
    ```
  - This means the correct ordering is:
    ```
    .order_by("distance")
    ```
    not:
    ```
    .order_by("-distance")
    ```
  - A reversed order would not crash anything — it would silently return the worst matching chunks first.

- Implemented the retrieval query using Django ORM + pgvector:


## Day 22 — HNSW Performance Validation

* Verified LexVault's HNSW vector index using `EXPLAIN ANALYZE` instead of assuming it was being used. The goal was to confirm PostgreSQL's query planner behavior and measure vector search performance at different dataset sizes.

* Confirmed the HNSW index existed correctly:

  ```
  idx_chunk_embedding hnsw (embedding vector_cosine_ops)
  ```

  Then tested the vector search query with the original dataset (~391 chunks). PostgreSQL chose `Seq Scan` with ~15ms execution time, which was expected because small datasets are often cheaper to scan directly than traverse through an HNSW graph.

* Tested the real LexVault tenant-scoped retrieval query with `firm_id` filtering and confirmed the same behavior. The query was correct from a multi-tenant isolation perspective, but the dataset was too small for PostgreSQL to benefit from HNSW.

* Created a benchmark management command `generate_test_chunks` and generated 100,000 additional chunks with 384-dimensional embeddings to simulate a realistic vector search workload.

* Re-ran `EXPLAIN ANALYZE` after increasing the dataset size to ~100k chunks. PostgreSQL switched from `Seq Scan` to `Index Scan using idx_chunk_embedding`, proving that the HNSW index was correctly configured and being used when the dataset size justified it.

* Verified the production-style query:

  ```
  WHERE firm_id = tenant_id
  ORDER BY embedding <=> query_vector
  LIMIT 5
  ```

  also used the HNSW index with ~3.4ms execution time.

* Documented the benchmark results in `docs/performance/vector_search.md`, including query plans, execution times, and the lesson that PostgreSQL chooses indexes based on cost rather than simply because they exist.

* Main takeaway: vector search optimization is not just about creating an index. You need to verify execution plans, understand database planner decisions, and test with realistic data sizes before making performance assumptions.

## Day 23 — Pipeline Integration Testing

- Wrote the complete pipeline integration tests the roadmap asked for: `Upload PDF → Extract → Chunk → Embed → Store → Retrieve`, exercised through the real `process_document` task rather than testing each service in isolation. `test_process_document_marks_ready_on_success` confirms status reaches `ready`, chunk count is correct, every chunk has a 384-dim embedding, and content is non-empty — the full checklist in one test against real Celery execution.

- Added the tenant-isolation test the roadmap specifically called for: Firm A and Firm B, different PDFs, both processed through the real task. Confirmed `storage_path` never crosses firms and every resulting `Chunk` row's `firm_id` matches its owning firm — not just at write time, checked again after processing completes.

- Reorganized `test_pipeline.py` by concern along the way — fixtures grouped, success path grouped, failure paths grouped, transactional-integrity tests grouped — and added the encrypted/empty/isolation coverage that had been thin.

- What I didn't catch until Day 24: this suite proves ingestion produces well-formed embeddings, but never actually proves those embeddings are *findable*. "Retrieval returns relevant chunks" was on this day's checklist and I marked it done because chunks existed with correct dimensions — that's not the same claim. A broken pooling strategy or a mis-normalized embedding could pass every test here and still return garbage for a real query. Caught this gap during Day 24's review, not today — recorded here since the gap originated in this day's scope, not tomorrow's.

- Real commit dates for this work, checked via git log rather than trusted from memory, since I'd lost track of exactly which day this landed:

This entry is going in four days late. Lesson: write the devlog the same day the work lands, not whenever I happen to circle back — I nearly lost the actual date this work was done and only recovered it by checking git history line by line.

---

## Day 24 — Pipeline Validation & Developer Documentation

- Started by closing the gap Day 23 actually left open: no test proved retrieval works against *real* embedded content, only against hand-built vectors in `test_search.py` (deliberately, per that file's own docstring — testing ordering logic shouldn't depend on model behavior, which is a legitimate reason for that test to exist as-is). Added `test_end_to_end_retrieval_finds_relevant_chunk`: runs a real PDF through `process_document()`, embeds a real query phrase with the actual embedder, and asserts `retrieve_chunks()` returns the correct page. This is the first test in the whole suite that proves the embedding model itself produces vectors where semantically similar text ends up close together, not just that the pipeline plumbing is wired correctly.

- Reviewed logs stage by stage, per the roadmap's checklist, and found the pipeline's observability was much thinner than it looked. `tasks.py` had exactly one real per-stage log ("Upload received," in `uploader.py`) plus three lines that were clearly leftover debug prints (`CELERY PATH`, `CELERY FILE EXISTS`, `CELERY STORAGE PATH`) firing unconditionally on every run, and one combined summary log that fired only after extraction, chunking, *and* embedding had all already finished — meaning a task stuck partway through gave zero signal about which stage it was actually in.

- Deleted the three debug-print lines and replaced the single combined summary with five real stage-boundary logs: extraction complete, chunking complete, embedding complete, database write complete, processing finished. Verified these live, not just by reading the code — triggered two real uploads through the actual Celery worker and grepped `docker compose logs celery_worker`, watching all five appear in order with correct counts (391 chunks, matching the known-good baseline).

- The upload-side log was the harder problem, and the more interesting one. `logger.info("Upload received...")` in `uploader.py` had existed since Day 14 and ran without error every time — but never produced output anywhere. Root cause: `base.py` has no `LOGGING` config at all, so the app logger fell back to Python's root logger with no handler attached. The call wasn't failing, it was just going nowhere — a genuinely worse failure mode than a missing log line, because nothing about it looks broken.

- Added a minimal root `LOGGING` config (one console handler, INFO level) to fix it. Kept it deliberately small — this isn't the day to build out per-module formatters or file handlers, just to make the existing calls actually land somewhere reviewable.

- Verifying the fix took three wrong attempts before I understood why. `python manage.py shell -c "..."` runs as its own one-off process with its own stdout — it never routes through the same log stream `docker compose logs django` captures, no matter what the `LOGGING` config says, because that stream belongs to the long-running `runserver` process specifically. Confirmed this properly two ways: first by live-tailing `docker compose logs -f django` in parallel while running the shell command and watching the line simply never appear there despite printing to my own terminal; then by forcing a real HTTP request through curl (manually building a session and a CSRF token, since `force_login()`-style shortcuts don't exist outside test code) and watching "Upload received" finally show up with the `lexvault_django |` prefix, twice, across two separate real requests. Real lesson: a passing log call and a log call that's actually observable in production-style output are two different claims, and only a request through the real server process can prove the second one.

- Reviewed the architecture doc for drift, as required, and left two known mismatches in place rather than silently fixing them mid-review:
  - `02_arcitechture.md` still documents Redis-backed sessions; actual settings use Django's default DB-backed sessions. Never reconciled since it was first noted.
  - The same doc describes SSE pushing stage-transition status as part of the ingestion pipeline today — SSE doesn't exist yet, that's Day 29's work. This one's expected drift (the doc describes target state, not current state) but still worth writing down rather than assuming it's obviously fine.

- Full suite: 71 passing, 96% overall coverage. `tasks.py` and `uploader.py` both at 100%.

- Bigger-picture takeaway for the day: "add logging" and "prove logging works" turned out to be almost entirely different amounts of effort. The code changes took minutes; confirming they actually produced durable, reviewable output — and understanding *why* my first three verification attempts kept failing silently — took most of the session. Worth remembering next time observability work feels done after the code compiles and the tests pass: that's necessary, not sufficient.

### Day 25 — Search Endpoint & Vector Retrieval

On Day 25, LexVault AI’s semantic search layer was completed. Implemented `search_documents(question, firm_id, top_k=5)` to generate query embeddings using the local **bge-small-en-v1.5** model, filter chunks by `firm_id` for strict tenant isolation, perform cosine-similarity vector search through pgvector, and return the top matching chunks with similarity scores, document filename, page number, and content. A `POST /search/` Django endpoint was added with authentication, firm-association, JSON validation, empty-query handling, and appropriate HTTP error responses. Comprehensive tests were added for the search service and endpoint, covering query validation, successful searches, empty vaults, top-k limits, similarity ordering, and cross-firm isolation. Final verification passed **16 search tests**, confirming that the complete semantic-search and tenant-isolated retrieval flow is working correctly.
