# LexVault — API Contract

**Author:** Areeba Hassan
**Status:** Draft — derived from `01_mvp_scope.md` and `02_arcitechture.md`. No endpoint exists here that isn't backing one of the 14 frozen user stories.
**Scope note:** Logout is added below even though Story 0 only specifies login. This is flagged as an assumption, not a scope addition — a session-based app with no way to end a session isn't a smaller version of the login story, it's an incomplete one. If you want it cut, cut it; it's one view.

---

## 1. Auth

**Mechanism:** Django sessions, DB-backed (per `02_arcitechture.md`).

- On successful login, the server sets a `sessionid` cookie (`HttpOnly`, `Secure` in production, `SameSite=Lax`).
- Every subsequent request is authenticated via that cookie — no `Authorization` header, no bearer token, no JWT.
- **CSRF:** Django's session auth requires a CSRF token on every unsafe method (`POST`, `DELETE`). The client must send `X-CSRFToken: <token>` on those requests, where `<token>` comes from the `csrftoken` cookie set on first page load. This is the one header every mutating request needs — miss it and every POST/DELETE below returns `403`.
- `firm_id` is never sent by the client. It's resolved server-side from `request.user` → `user.firm_id` on every request. If a client-sent `firm_id` ever appears in a request body, the server ignores it — trusting a client-supplied tenant ID is exactly the isolation bug the schema doc's denormalized `firm_id` is designed to prevent at the data layer; the API layer can't be the weak link above it.

**Unauthenticated request to any endpoint below (except login):** `401`, body `{"error": "authentication_required", "detail": "Login required."}`

---

## 2. Error Format

Every error response, regardless of endpoint, uses this shape:

```json
{
  "error": "machine_readable_code",
  "detail": "human-readable message safe to show in the UI"
}
```

Field-level validation errors add a `fields` object:

```json
{
  "error": "validation_error",
  "detail": "One or more fields are invalid.",
  "fields": {
    "file": ["File must be a PDF."]
  }
}
```

**Status codes used across this contract:** `200`, `201`, `204`, `400`, `401`, `403`, `404`, `413`, `422`, `429`, `500`.

---

## 3. `POST /api/login/`

Story 0.

**Auth required:** No.

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response `200`:**
```json
{
  "user_id": "uuid",
  "firm_id": "uuid",
  "username": "string"
}
```
Sets `sessionid` cookie.

**Response `401`:**
```json
{"error": "invalid_credentials", "detail": "Incorrect username or password."}
```
Same error for "user doesn't exist" and "wrong password" — a distinguishable error here leaks which usernames exist. No lockout/rate-limit on login itself; out of scope per Story 0 (no MFA, no recovery flow), and this is a seeded low-user-count demo, not a public signup surface.

---

## 4. `POST /api/logout/`

*(Assumption — see note at top of doc.)*

**Auth required:** Yes.

**Request:** empty body.

**Response `204`:** No content. Clears session cookie.

---

## 5. `POST /api/documents/`

Story 1 (upload).

**Auth required:** Yes.

**Request:** `multipart/form-data`
| Field | Type | Notes |
|---|---|---|
| `file` | file | PDF only |

**Validation, in order checked:**
1. File present → else `400 validation_error`
2. Content-Type / extension is PDF → else `422 unsupported_file_type`
3. File size — cap not stated in any prior doc. Setting **25 MB** here as a demo-appropriate ceiling (large enough for real contract/legal PDFs, small enough that a bad upload can't stall Celery for minutes). Flag this if you want a different number. → else `413 file_too_large`

**Response `201`:**
```json
{
  "document_id": "uuid",
  "filename": "string",
  "status": "uploaded",
  "created_at": "iso8601"
}
```
Document row is created with `status='uploaded'` synchronously; the Celery task chain (extract → chunk → embed → store) is enqueued and returns immediately. This response does not wait for processing — that's what the status story is for.

**Response `422` (bad file):**
```json
{"error": "unsupported_file_type", "detail": "Only PDF files are supported."}
```

**Response `413`:**
```json
{"error": "file_too_large", "detail": "File exceeds the 25MB limit."}
```

---

## 6. `GET /api/documents/{document_id}/status/`

Story 2. **SSE endpoint** — `Content-Type: text/event-stream`, not JSON request/response.

**Auth required:** Yes. Server verifies `document.firm_id == request.user.firm_id` before opening the stream — `404`, not `403`, on a firm mismatch (see §9, tenant-isolation error policy).

**Stream events**, one per stage transition:
```
event: status
data: {"document_id": "uuid", "status": "uploaded"}

event: status
data: {"document_id": "uuid", "status": "processing"}

event: status
data: {"document_id": "uuid", "status": "ready", "page_count": 12}
```

**Failure path** (the one the original story omitted, corrected July 13):
```
event: status
data: {"document_id": "uuid", "status": "failed", "error_message": "Could not extract text: file is password-protected."}
```
Stream closes after `ready` or `failed` — both are terminal states, no further events follow.

**Response `404`** (wrong firm or nonexistent document, before the stream opens):
```json
{"error": "not_found", "detail": "Document not found."}
```

---

## 7. `GET /api/documents/`

Story 10.

**Auth required:** Yes.

**Query params:**
| Param | Type | Default | Notes |
|---|---|---|---|
| `status` | string | none | Optional filter, one of `uploaded/processing/ready/failed` — matches `idx_document_firm_status` |

**Response `200`:**
```json
{
  "documents": [
    {
      "document_id": "uuid",
      "filename": "string",
      "status": "ready",
      "page_count": 12,
      "created_at": "iso8601"
    }
  ]
}
```
Firm-scoped server-side; no `firm_id` filter accepted from the client (see §1). No pagination — at demo scale (a handful of PDFs per firm) it's dead weight; add it the day a firm's document count makes a flat list unusable, not before.

---

## 8. `DELETE /api/documents/{document_id}/`

Story 11.

**Auth required:** Yes.

**Response `204`:** No content. Cascades to `chunk` and downstream `citation` rows per the schema's `ON DELETE CASCADE`.

**Response `404`:** Same firm-mismatch-hides-as-404 policy as §6.

---

## 9. `POST /api/search/`

Stories 7, 7a, 8, 9, 12, 13.

**Auth required:** Yes.

**Request:**
```json
{
  "query": "string"
}
```
**Validation:** non-empty, matches `search_query.query_text` CHECK (`length > 0`) → else `400 validation_error`.

**Response `200` — chunks passed the Two-Gate filter:**
```json
{
  "search_query_id": "uuid",
  "result_type": "found",
  "answer": "Generated answer text, grounded in cited chunks.",
  "citations": [
    {
      "document_id": "uuid",
      "document_title": "string",
      "page_number": 4,
      "relevance_score": 0.83,
      "rank": 1
    }
  ]
}
```

**Response `200` — nothing survived both gates:**
```json
{
  "search_query_id": "uuid",
  "result_type": "not_found",
  "answer": null,
  "citations": []
}
```
This is a `200`, not a `404` — "not found in vault" is a correct, expected answer shape per Story 9, not an error.

**Response `429` — rate limited:**
```json
{"error": "rate_limited", "detail": "Search rate limit exceeded. Try again in 12 seconds."}
```
**Limit: 10 requests/minute per user**, enforced via DRF throttling per `02_arcitechture.md`. Reasoning: at demo scale (up to 5 concurrent firm users, each interactively typing questions), 10/min per user comfortably covers real usage while still making the rate-limiting story (13) demonstrable and testable — not so high it never triggers, not so low it blocks a normal demo session.

---

## 10. Cross-Cutting: Tenant Isolation Error Policy

Every endpoint that takes a resource ID (`document_id` in §6, §8) enforces `firm_id` match server-side. **On mismatch, the response is `404`, never `403`.**

Returning `403` on a cross-firm request confirms the resource *exists*, just isn't yours — that's an enumeration leak, and it's exactly the failure mode Story 12 exists to prevent. `404` makes "not mine" and "doesn't exist" indistinguishable from the outside, which is the correct behavior for a multi-tenant boundary.

---

## 11. Open Items

- File size cap (25MB) is not sourced from any prior doc — it's a default set here. Confirm or override.
- No endpoint here for viewing an individual `search_query`'s history — not in the 14 stories, not added.
- Logout endpoint (§4) is an assumption, flagged above — confirm or cut.