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

## Open TODOs Going Into Next Phase

- [ ] Confirm final coverage numbers after the backend edge-case and management-command tests land — target closing the `backends.py` gap specifically, since it's the auth security layer.
- [ ] Build custom firm-aware login view/form; decide whether to drop `ModelBackend` fallback once it exists (still open from Day 9).
- [ ] `firm` FK on `User` still nullable — must become `NOT NULL` once firm onboarding is automated.
- [ ] All six schema entities now exist — next real milestone is the ingestion pipeline: PyMuPDF extraction → chunking → `bge-small-en-v1.5` embedding, populating `Document`/`Chunk` with real data instead of test fixtures.
- [ ] `apps/ingestion` directory already scaffolded (empty) — decide whether pipeline logic lives there or inside `apps/documents`; revisit once the pipeline's first file starts exceeding ~300–400 lines.