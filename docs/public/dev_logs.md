# LexVault AI – Dev Log (Days 1–10)

Personal log of actual work completed on LexVault AI. Kept for future reference — what was built, what broke, and what was learned.

---

## Day 1 — Project Architecture Decision

- Decided on **multi-tenant AI Knowledge Base (RAG) SaaS** architecture.
- Chose **row-level tenant isolation** over schema-per-tenant: same database, same schema, every row scoped by a `Firm` FK.
- Explicitly rejected `django-tenants` — MVP doesn't need schema-per-tenant complexity.
- Locked stack: Django, DRF (later), PostgreSQL 17, Docker Compose, django-environ, Python 3.14, UUIDv7 PKs, psycopg2, uv.
- Documented the guiding principle: *every piece of application data belongs to exactly one Firm, and every query must be scoped to that Firm.*

---

## Day 2 — Firm & Custom User Model

- Built `Firm` model — UUIDv7 PK, name, created_at. Tenant root.
- Extended `AbstractUser` for custom `User` model: UUID PK, FK to `Firm`.
- Decision: tenant-scoped usernames — `(firm, username)` unique, not global username uniqueness. Rationale: different firms should both be able to have a user named `admin`.
- `firm` FK temporarily set `null=True, blank=True` to unblock `createsuperuser` during early development.

---

## Day 3 — The AbstractUser Uniqueness Discovery

- Hit a subtle bug: `AbstractUser` already defines `username` as globally unique (`unique=True`). Adding `UniqueConstraint(fields=["firm", "username"])` doesn't remove that — both constraints existed simultaneously.
- Fix: explicitly override `username = models.CharField(max_length=150, unique=False, db_index=True)`.
- This immediately triggered Django's system check `auth.E003`: `USERNAME_FIELD` must be unique.
- Resolved by adding `SILENCED_SYSTEM_CHECKS = ["auth.E003"]` — a deliberate override, justified because a custom auth backend was already planned to replace Django's default lookup behavior.

---

## Day 4 — Management Commands

- Built `createfirm` — creates a `Firm` by name, prints UUID.
- Built `createfirmadmin` — creates a superuser scoped to a `Firm`, with a manual `.exists()` guard blocking duplicate usernames *within the same firm*.
- Verified end-to-end via CLI: created `PixelLawFirm` + admin `areebahassan`, then `SamarJafriLaws` + admin `samarjafri`.
- Confirmed cross-firm duplicate usernames succeed (as designed) and same-firm duplicates are blocked by the command's guard.

---

## Day 5 — Django Admin Setup

- Registered `User` in `apps/accounts/admin.py` using a `CustomUserAdmin(UserAdmin)` subclass with `list_display`/`list_filter` scoped by firm.
- Verified admin login works for firm-scoped admins created via `createfirmadmin`.
- Noted a real risk: Django admin's default login uses `ModelBackend`, which does a **global** username lookup with no firm filter. Works today only because usernames happen to be unique across firms in testing — flagged as fragile until the custom auth backend replaces this.

---

## Day 6 — Debug Toolbar Fix

- Hit `NoReverseMatch: 'djdt' is not a registered namespace` on `/admin/`.
- Root cause: `debug_toolbar` was installed in `INSTALLED_APPS` but never wired into `config/urls.py`.
- Fixed by adding the toolbar's URL include gated behind `settings.DEBUG`, and confirmed `INTERNAL_IPS = ["127.0.0.1"]` was set.
- Admin panel loads cleanly with the toolbar rendering correctly.

---

## Day 7 — First Automated Test: Tenant Isolation Proof

- Installed/confirmed `pytest` + `pytest-django` (already in dev deps via `uv`).
- Added `pytest.ini` pointing `DJANGO_SETTINGS_MODULE` at `config.settings.development`.
- Wrote `test_firm_isolation_at_query_level` — proves `User.objects.filter(firm=firm_a)` correctly isolates rows by tenant.
- First real automated proof (not just manual shell checks) that the row-level isolation design works as intended.

---

## Day 8 — Expanding the Regression Suite

- Added `test_duplicate_username_allowed_across_firms` — confirms same username in different firms is valid.
- Added `test_duplicate_username_blocked_within_same_firm` — confirms the DB-level `UniqueConstraint(firm, username)` raises `IntegrityError` on same-firm duplicates.
- All 3 tests passing. This is the locked-in regression suite protecting the core tenant-isolation contract — if the `unique=False` override or the constraint is ever accidentally reverted, these tests catch it immediately.

---

## Day 9 — Custom Auth Backend

- Built `FirmBackend` (`apps/accounts/backends.py`) — authenticates via `(firm, username, password)` instead of Django's default global-username lookup.
- Fails closed on `MultipleObjectsReturned` rather than guessing which user was meant.
- Registered in `AUTHENTICATION_BACKENDS`, keeping `ModelBackend` as a fallback for admin login (trade-off: admin login still relies on global username uniqueness until a custom firm-aware login view is built).
- Noted as an open design decision: keep both backends short-term, or build a custom login form that collects `firm` explicitly and drop `ModelBackend` outside of admin.

---

## Day 10 — Backend Test Coverage + Coverage Tooling

- Wrote `test_backends.py` covering: successful auth, wrong password, wrong firm (the cross-tenant leak case), nonexistent user, and — most importantly — two identically-named users in different firms both authenticating independently and correctly.
- All 5 backend tests + 3 earlier isolation tests passing.
- Set up `coverage` config in `pyproject.toml` (`source = ["apps"]`, omitting migrations/tests) to measure real test coverage across `apps/accounts` and `apps/firms`.

---

## Day 11 — Document and Chunk Models (Schema Design Applied)

- Formalized the schema design doc: six entities total — `Firm`, `User`, `Document`, `Chunk`, `SearchQuery`, `Citation`. Locked decisions on PK type (UUIDv7), status representation (`VARCHAR` + `CheckConstraint`, not native enum), `firm_id` denormalization on `Chunk`/`SearchQuery`, embedding model (`bge-small-en-v1.5`, 384 dims, self-hosted via `sentence-transformers`), vector index type (HNSW over IVFFlat), and `ON DELETE` behavior per relationship.
- Created `apps/documents` app to hold `Document` and `Chunk` together — decided against one-app-per-entity; grouped by bounded context instead (`Chunk` has no independent meaning without `Document`, same logic applied later to `SearchQuery`/`Citation`).
- Wrote `Document` model: UUID PK, `firm` FK (`CASCADE`), `uploaded_by` FK to `User` (`PROTECT` — no user-deletion story in MVP yet), `status` as `TextChoices` (`uploaded`/`processing`/`ready`/`failed`), `page_count` and `file_size_bytes` with `CheckConstraint`s, composite index `(firm, status)`.
- Caught and fixed a field-name/index mismatch (`processing_status` vs `status`) before migrating — kept the model in sync with the schema doc rather than letting them drift.

---

## Day 12 — Chunk Model and pgvector Integration

- Wrote `Chunk` model: UUID PK, `document` FK (`CASCADE`), denormalized `firm` FK (`CASCADE`) — deliberate duplication so `WHERE firm_id = X` never requires a join through `Document`.
- Added `page_number`, `chunk_index`, `content`, `token_count` fields with `CheckConstraint`s. Learned the distinction between constraints Django's field types already enforce (`PositiveIntegerField` blocks negatives) vs constraints that need an explicit DB-level `CheckConstraint` regardless (`> 0` vs field-level `>= 0`), and kept redundant-looking constraints anyway as defense-in-depth against raw SQL/other clients bypassing Django validation.
- Added `embedding = VectorField(dimensions=384)` using `pgvector.django`.
- Hit and fixed a broken `CheckConstraint` attempt using a non-existent `content__length__gt` lookup — Django doesn't register `__length` as a lookup by default. Fixed by comparing directly against an empty string (`content__gt=""`), which Postgres evaluates correctly for "non-empty text" without needing the `Length()` function at all.
- Added `HnswIndex` on `embedding` (`vector_cosine_ops`) via `pgvector.django.HnswIndex` — required adding `django.contrib.postgres` to `INSTALLED_APPS` (`postgres.E005` otherwise).

---

## Day 13 — The pgvector Extension Saga

- First `migrate` attempt failed: `type "vector" does not exist` — the Python `pgvector` package was installed, but the Postgres *server* itself had no `vector` extension binary.
- Attempted `CREATE EXTENSION IF NOT EXISTS vector;` manually and via a Django migration (`CreateExtension("vector")`) — both failed with `extension "vector" is not available` / `Could not open extension control file`, because the running `postgres:17` Docker image doesn't ship pgvector at all.
- Root-caused to the Docker image choice: switched `docker-compose.yml` from `postgres:17` to `pgvector/pgvector:pg17` (official pgvector-maintained image, same Postgres 17, extension pre-built in).
- Since the existing Postgres data volume was initialized under the old image, did a full `docker compose down -v` + `up -d` to force a clean re-initialization under the new image, then re-ran `migrate` — succeeded end-to-end, including the `CreateExtension` step and the `Chunk` table with its `VectorField` and `HnswIndex`.
- Recreated test data lost in the volume wipe (`PixelLawFirm` + `areebahassan` admin) via the existing `createfirm`/`createfirmadmin` commands.
- Lesson logged: the extension needs to live in the Docker image, not just be installed via `pip` — client library and server extension are two separate things that both have to be present.

---

## Day 14 — SearchQuery and Citation Models

- Created `apps/search` app for the last two entities: `SearchQuery` and `Citation` — same "no independent meaning without its parent" logic as `Chunk`/`Document`.
- Wrote `SearchQuery`: denormalized `firm` FK (same reasoning as `Chunk`), `user` FK with `CASCADE` (contrasted deliberately against `Document.uploaded_by`'s `PROTECT` — a query log has no independent value once its owner is gone, and audit logging is explicitly out of scope). `result_type` stored explicitly as `TextChoices` (`found`/`not_found`) rather than derived from `Citation` existence, to keep the 90%-correct-citation proof metric a fast `GROUP BY` instead of a `LEFT JOIN + COUNT`.
- Wrote `Citation`: `search_query` + `chunk` FKs (`CASCADE`), `relevance_score` (`CheckConstraint` combining two `Q` objects into one range check, `0 ≤ x ≤ 1`), `rank` (`PositiveSmallIntegerField` + `CheckConstraint` since the field alone allows `0` but the schema requires `≥ 1`), two `UniqueConstraint`s (`search_query+chunk`, `search_query+rank`).
- All six entities from the schema design doc now exist as real Django models, migrated cleanly.

---

## Day 15 — Full Regression Suite + Coverage Baseline

- Wrote model-level tests for `Document`/`Chunk` (default status, both `CheckConstraint`s, `Chunk` positivity/non-empty constraints, `UniqueConstraint(document, chunk_index)`, and a firm-scoped query proving the denormalized `firm` field works as intended).
- Wrote model-level tests for `SearchQuery`/`Citation` (empty-text rejection, `CASCADE` on user/chunk deletion — directly proving the schema doc's `ON DELETE` decisions — both `UniqueConstraint`s, relevance-score range, rank minimum).
- Ran full suite: **25 passed** across `accounts`, `documents`, `firms`, `search`.
- Set up `coverage` properly (`pyproject.toml` config, `coverage html` for line-level inspection). First real baseline: **79% overall**. Identified genuine gaps worth closing — `backends.py` at 67% (missing the `MultipleObjectsReturned` fail-closed branch and `get_user()`), both management commands (`createfirm`, `createfirmadmin`) at 0% despite being manually verified via CLI throughout the project so far.
- Added `apps/firms/tests.py` (previously empty) — basic creation/`__str__`/UUID-type tests, closing the one app with zero coverage.
- Wrote edge-case backend tests: discovered the `UniqueConstraint(firm, username)` is enforced strongly enough that even `bulk_create` can't bypass it at the DB level — had to test the `MultipleObjectsReturned` fail-closed branch via mocking (`unittest.mock.patch.object`) instead of trying to force a real duplicate row, since the constraint made the "corrupted state" scenario genuinely unreachable in practice.
- Wrote management command tests (`call_command` + `CommandError` assertions) for both `createfirm` and `createfirmadmin`, covering: successful creation, nonexistent-firm rejection, same-firm duplicate rejection, and cross-firm duplicate-username success — turning three conversation's worth of manual CLI verification into a permanent, automated regression suite.

---

## Day 16 — Celery + Redis: Concepts, Docker Wiring, and Debugging

**Concepts covered before building:**
- Message broker — the queue between Django and a Celery worker (Redis, in this stack)
- Result backend — where Celery stores task status/results (same Redis instance, separate logical DB)
- `celery.py` — the project-level file that creates the Celery app instance and wires it to Django settings
- `CELERY_TASK_ALWAYS_EAGER` — makes `.delay()` run synchronously in tests, no broker/worker needed
- Docker networking — containers on the same Compose network resolve each other by service name, not `localhost`; a process running on the host (like Django currently does) instead needs `localhost` + the container's exposed port

**docker-compose.yml — added three new services:**
- `redis` (`redis:7-alpine`) — broker + result backend, port `6379` exposed to host
- `celery_worker` — built from a new project `Dockerfile` (`uv sync --frozen` based), running `celery -A config worker`
- `flower` — same build, running `celery -A config flower --port=5555`, dashboard on port `5555`

**Debugging chain worked through, in order:**

1. **`docker compose down`: "no configuration file provided"** → `docker-compose.yml` and the shell session were in different directories (`docker/` vs project root). Root cause: build context for `build: .` depends on *where compose is run from*, not where the compose file lives. Resolved by keeping `docker-compose.yml` and `Dockerfile` both at the project root and always running compose commands from there.

2. **`COPY pyproject.toml uv.lock ./` failed — file not found** → same root cause as above, confirmed once the directory issue was fixed.

3. **First successful build took ~18 minutes, build context was 5.33GB** → Docker was copying the entire project directory (`.venv/`, `.git/`, `htmlcov/`, `__pycache__/`) into the build context before building anything. Fixed with a `.dockerignore` at the project root excluding all of these. Rebuild time dropped to ~3 seconds.

4. **`celery: executable file not found in $PATH`** → `uv sync` installs dependencies into a project-local `.venv/` inside the container, which was never added to `PATH`. Fixed by prefixing every Celery command in `docker-compose.yml` with `uv run` (e.g. `uv run celery -A config worker --loglevel=info`), which locates the venv automatically without needing `PATH` changes.

5. **Persistent `"wv2" variable is not set` warning on every Compose command** → traced to `.env`'s `SECRET_KEY` containing a literal `$wv2` substring, which Compose's variable-interpolation syntax misread as a reference to an undefined variable named `wv2`. Also caught a stray `==` typo in the same line. Fix: escape literal `$` characters as `$$` in `.env` values that Compose reads.

6. **All four containers (`postgres`, `redis`, `celery_worker`, `flower`) came up `Up` — but `celery_worker` logs showed `Module 'config' has no attribute 'celery'`** → `config/celery.py` didn't exist yet; only the Docker/Compose wiring had been done, not the actual Celery app instance. This was the point where scope shifted from Docker configuration to writing the actual Celery integration.

7. **`ModuleNotFoundError: No module named 'celery'` when running `python manage.py shell` on the host** → `celery` was listed in `pyproject.toml` (added Day 1) but the host's local `.venv` had never been synced since. Docker's `celery_worker` image *did* have it, since `uv sync --frozen` runs fresh on every `docker build` — the host venv needed a manual `uv sync` to catch up. Confirmed the general lesson: adding a dependency to `pyproject.toml` doesn't propagate automatically to every environment using that file; each environment (host venv, each Docker image) needs its own sync.

**Outcome:** requested and received a clean, from-scratch, step-by-step Celery + Redis setup guide (`docs/private/celery_redis_setup_guide.md`) consolidating the correct build order — Redis running → `celery.py` created → settings wired → task written → worker started → task called and proven via `.delay()`/`.get()` → Flower confirmation → `ALWAYS_EAGER` for tests — deliberately sequenced so Django-on-host + Redis-in-Docker is proven working *before* attempting to containerize the worker itself, since debugging Celery logic and Docker networking simultaneously had been the source of most of today's confusion.

![alt text](image.png)


## Day 17 — Upload View, Storage Config, and Test Infrastructure Fixes

**Concepts covered before building:**
- MIME type validation vs extension checking — a renamed `.txt` file passes an extension check but fails a real content-based check
- `python-magic` — reads actual file header bytes (`libmagic`), not filename or the browser-supplied (spoofable) `content_type`
- `request.FILES` — Django's dict-like container for uploaded files, separate from `request.POST`
- `django-storages` — abstracts file storage behind Django's standard `Storage` API, so the same code writes to local disk in dev and Cloudflare R2 in production
- R2 vs S3 — R2 implements the S3-compatible API; only the endpoint URL differs, same `django-storages` backend works for both

**Upload view — built iteratively, with real bugs caught along the way:**
- First self-written draft had five real bugs: wrong import (`from apps import magic` instead of the top-level `magic` package), an undefined `uploaded_file` variable referenced after naming the actual variable `document`, a `magic_task.delay()` call referencing a task that didn't exist (should have been `process_document`), and — the subtle one — `ALLOWED_MIME_TYPES` defined as a plain string, making `not in` check substring membership rather than exact-value membership (worked by accident for the one test case, silently wrong for anything else).
- Second draft fixed all five; caught one more on review — `storage_path` was rebuilt from a raw f-string instead of using the actual value returned by `default_storage.save()`, which matters because Django auto-renames on filename collision and the rebuilt string wouldn't reflect that.
- Configured `django-storages`: `FileSystemStorage` for `development.py` (local `MEDIA_ROOT`), `S3Storage` pointed at an R2 endpoint for `production.py` — same view code works unchanged against either backend.
- `process_document` task initially just logged the `document_id` — the actual extraction wiring came later (Day 18).

**Testing — hit a real blocker, adjusted approach:**
- First manual test via `curl` failed with `403 CSRF verification failed` — Django's CSRF middleware correctly rejecting an unauthenticated, token-less request. Recognized this would also immediately hit `AttributeError` on `request.user.firm` (`AnonymousUser` has no `firm`) even if CSRF were bypassed, since no login flow exists yet.
- Switched to Django's test `Client` with `force_login()` instead of fighting `curl` + cookies + a login view that doesn't exist yet — the correct professional pattern for testing view logic in isolation. `Client()` doesn't enforce CSRF by default, and `force_login()` creates a real authenticated session for a real `User`/`Firm`.
- Wrote `test_views.py`: valid-PDF acceptance, fake-PDF rejection (renamed `.txt`), missing-file guard — all passing.

**`CELERY_TASK_ALWAYS_EAGER` setup — hit and fixed a real file-writing bug:**
- Created `config/settings/test.py`, pointed `pytest.ini` at it — immediately broke every test with `RuntimeError: Model class apps.firms.models.Firm doesn't declare an explicit app_label`.
- Root cause: `test.py` had only been partially written — `from .development import *` never actually landed in the file, leaving `INSTALLED_APPS` completely empty (`[]`) under the new settings module. Confirmed via direct `INSTALLED_APPS` comparison between `development` and `test` settings before guessing at a fix.
- Rewrote the file correctly; added a mock-based test (`patch("apps.documents.views.process_document.delay")`) proving the view actually triggers the Celery task with the correct `document_id` — patched at the import location in `views.py`, not the definition location in `tasks.py` (a common `unittest.mock` gotcha).

---

## Day 18 — Extraction Service, Exception Hierarchy, and Pipeline Proof

**Concepts covered before building:**
- PyMuPDF (`fitz`) — parses actual PDF object structure (pages, fonts, text streams), not raw bytes
- Page objects — `Document` behaves like a list of `Page` objects, each with `.get_text()`, preserving page numbers needed for citation
- Pure-Python-no-Django design — `extract_pages()` deliberately has zero Django imports, for fast plain-pytest testing and reuse outside the Celery task
- Custom exception classes — `ExtractionError(Exception)` over bare `ValueError`, so callers can catch extraction failures specifically without swallowing unrelated bugs
- Encrypted vs corrupted PDFs — genuinely different failure modes needing different user-facing messages
- Scanned PDFs — image-only, no text layer; `.get_text()` returns empty strings silently, no error by default
- Graceful degradation — failing in a controlled, informative way vs crashing or silently producing wrong/empty results
- Failure classification — silent (log only) vs visible (user-facing) vs critical (would alert a human); logging severity levels (`INFO`/`WARNING`/`ERROR`) vs `print()`, which has no severity, no routing, no way to filter by environment

**`services/extractor.py` — built and tested in isolation first:**
- `extract_pages(file_path: str) -> list[dict]`, returning `[{"page_number": N, "text": "..."}]`, one entry per non-empty page.
- First version: single `ExtractionError`, encrypted-PDF detection via `doc.needs_pass`, corrupted-file detection via a broad `except Exception` around `fitz.open()`.
- 6 tests written using `tmp_path` + `fitz` itself to generate real PDFs on disk (valid, corrupted-garbage-bytes, encrypted-via-`fitz.PDF_ENCRYPT_AES_256`, nonexistent path) — all passing, in ~1 second, confirming the zero-Django-dependency design actually delivers fast tests.

**Wired into the real pipeline — first end-to-end proof:**
- Updated `process_document` to actually call `extract_pages()`, using `default_storage.path()` to resolve the stored file to a local filesystem path (flagged as a known limitation: won't work once storage moves to R2, will need a stream-based read instead).
- Status handling: `PROCESSING` on start, `page_count` written on success, `FAILED` + `error_message` on `ExtractionError`. Deliberately left status as `PROCESSING` rather than `READY` after extraction alone — `READY` would be inaccurate until chunking/embedding also exist.
- Wrote `test_pipeline.py`: one HTTP upload call, relying on `CELERY_TASK_ALWAYS_EAGER` to run the task synchronously within the same request — proving the entire chain (view → MIME check → storage → `Document` row → Celery trigger → real PyMuPDF extraction → `page_count` written back) for real, no mocking. A second test proved the `FAILED` path using a file with a valid `%PDF-` header but a garbage body (passes MIME sniffing, fails PyMuPDF's real parse).
- Confirmed live via `pytest -s --log-cli-level=INFO` — watched real `INFO`/`ERROR` log lines and Celery's own tracer (`succeeded in 0.02s`) confirming genuine execution, not just green test output.

**Extended with a full exception hierarchy and severity-based logging:**
- Split `ExtractionError` into three subclasses: `EncryptedPDFError`, `CorruptedPDFError`, `EmptyPDFError` — all still catchable as the base class for callers that don't need the distinction.
- Added scanned-PDF detection: tracks `empty_page_count` during extraction; if *every* page comes back empty, raises `EmptyPDFError` rather than silently returning `[]`. Deliberately distinguished from "some pages empty" (normal — logged at `INFO`, not raised) via a dedicated test proving a document with one real page among blank ones does NOT raise.
- Added logging throughout at appropriate severities: `INFO` for routine events, `WARNING` for encrypted/empty/corrupted-open failures, `ERROR` in `tasks.py` specifically for the corrupted case (reasoning: could indicate a storage-side bug, not just a bad input file — documented in a dedicated `error_classification.md`).
- Wrote `error_classification.md` — a reference table for each exception type: classification (silent/visible/critical), log level, exact user-facing message, and reasoning. Also documented what WOULD warrant critical/Sentry-style alerting later (sustained spikes in corrupted-file errors, any non-`ExtractionError` exception escaping `extract_pages()`), left as a deliberate TODO since there's no production traffic yet to monitor.
- Updated `tasks.py` to catch each subclass specifically with a tailored user message, plus a catch-all for any future `ExtractionError` subclass not yet special-cased — fails gracefully rather than crashing even for failure modes not yet anticipated.

**Full suite run surfaced a real, previously-invisible bug:**
- Running the complete suite with live logging (`pytest -v -s --log-cli-level=INFO`) showed `test_upload_valid_pdf_creates_document` (from Day 17) triggering a `WARNING: All 0 page(s) ... returned empty text` — the original `VALID_PDF_BYTES` fixture was just a bare `%PDF-1.4` header with no real text objects, which passed MIME detection but was never genuinely extractable content.
- This had been silently "passing for the wrong reason" since Day 17 — the test only asserted upload success, not extraction success, so the gap was invisible until scanned-PDF detection was built and started correctly flagging it.
- Fixed by rebuilding the fixture with real `fitz`-generated text content (same helper pattern as `test_pipeline.py`), and strengthened the test to also assert `page_count == 1` after refresh — now genuinely proving extraction succeeds, not just that upload was accepted.
- Full suite: **21 passed** across `accounts`, `documents` (including the new `services/` extractor tests and `test_pipeline.py`), `firms`, `search`.

---

## Open TODOs Going Into Next Phase

- [ ] Generate and review the coverage report against the full Day 17–18 additions — expect `extractor.py` and `tasks.py` to be at or near 100% given how thoroughly each branch (happy path, encrypted, corrupted, empty) now has a dedicated test.
- [ ] `default_storage.path()` in `tasks.py` is local-storage-only — needs a stream-based rewrite before R2 goes live in production.
- [ ] Chunking is the next real pipeline stage: split each page's extracted text into overlapping, token-bounded pieces mapping onto `Chunk.chunk_index`/`Chunk.token_count`.
- [ ] Still open from Day 9: custom firm-aware login view, to replace `curl`/CSRF workarounds with a real auth flow and drop the `ModelBackend` fallback.
- [ ] `firm` FK on `User` still nullable — must become `NOT NULL` once firm onboarding is automated.
