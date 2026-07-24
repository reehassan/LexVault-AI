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