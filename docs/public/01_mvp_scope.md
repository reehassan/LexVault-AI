# LexVault MVP — Scope Freeze Document

**Frozen by:** Areeba Hassan
**Freeze date:** July 7, 2026
**Ship date:** not shipped
**Status:** LOCKED. Any feature not listed under "In Scope" does not get built before ship, no matter how good the idea sounds mid-build.

---

## North Star Metric

There isn't a real north star metric here, because there's no live usage to point one at — this is a portfolio demo, not a product with users. Forcing a growth-style metric ("DAU," "retention") onto a project with three demo PDFs and no real firm using it is a category error. The honest substitute is a **proof metric**: a number that demonstrates the core technical claim actually holds.

**Metric:** Correct-citation rate on a fixed test set — at least 90% of a 20-question test set (spanning the 3 public-domain demo PDFs) returns an answer with the correct source document and page number, or correctly returns "Not found in vault" when no answer exists.


## User Stories (in-scope features)

0. **Login** — As a firm user, I want to log in with a seeded username/password, so that the system knows which firm's vault I'm scoped to. No self-registration: accounts are seeded directly (one or a few per firm) since there's no admin workflow to manage signup. No password reset, SSO, or MFA — a lost demo password gets reset by re-seeding the account, not by building a recovery flow.
1. **PDF upload** — As a firm user, I want to upload a PDF to my firm's vault, so that its contents become searchable.
2. **Processing status** — As a firm user, I want to see live status (`uploaded → processing → ready`, or `uploaded → processing → failed`) without reloading the page, so that I know when a document is searchable — or that it failed, with an error message, rather than sitting in `processing` indefinitely. *(Corrected July 13 — original story omitted the failed path that the schema's `status` CHECK constraint and `error_message` column already require.)*
3. **PDF extraction** — As the system, I need to extract text per page from an uploaded PDF, so that page numbers can be attached to retrieved content later.
4. **Chunking** — As the system, I need to split extracted text into overlapping token-bounded chunks (fixed-size, 300–400 tokens, 50 overlap — not auto-tuned), so that retrieval can operate at a granularity finer than a whole document, with boundaries predictable enough to measure against the citation-accuracy proof metric.
5. **Embedding** — As the system, I need to generate a vector embedding for each chunk, so that semantic similarity search is possible.
6. **Vector storage** — As the system, I need to store each chunk's embedding alongside its source document, page number, and firm, so retrieval can be scoped and cited correctly.
7. **Semantic search** — As a firm user, I want to ask a natural-language question, so that I get relevant passages back via cosine similarity retrieval, without needing to guess the document's exact wording.
7a. **Answer generation** *(new, July 13)* — As a firm user, I want the system to generate a synthesized answer from the retrieved passages using a local LLM, rather than just showing me raw matching text, so that the answer reads naturally — while every generated answer is still grounded in, and cited to, the retrieved chunks so I can verify it wasn't fabricated. This is the story that carries the hallucination risk the architecture doc explicitly names; it's mitigated by the Two-Gate filter and the citation/not-found stories below, not eliminated by them.
8. **Citation** — As a firm user, I want every answer to show the source document title and page number, so that I can verify it myself rather than trust it blindly.
9. **Not-found fallback** — As a firm user, I want an explicit "Not found in vault" response when no relevant content exists, so that I'm never given a fabricated answer.
10. **Document list** — As a firm user, I want to see all documents uploaded by my firm, so I know what's currently searchable.
11. **Document delete** — As a firm user, I want to remove a document from the vault, so outdated or incorrect files stop being searchable.
12. **Tenant isolation** — As a firm user, I want certainty that another firm can never retrieve my documents, so that privileged material stays privileged.
13. **Rate limiting** — As the system, I need to cap search requests per user/time window, so that a single user or bad actor can't drive unbounded API cost.

---

## Freeze Statement

This scope is locked as of July 7, 2026. The 14 user stories listed under
"In Scope" are the entire MVP. Nothing else gets built before ship —
no admin dashboard, no multi-file batch upload, no re-ranking model,
no conversation history, no user-facing settings, no password reset flow,
no analytics beyond the citation-accuracy proof metric.

If a feature seems necessary mid-build, it goes on a "Post-MVP" list, not
into the sprint. The only way scope changes is by editing this document
and re-dating the freeze — not by quietly adding a story mid-sprint because
it sounded reasonable in the moment. The July 13 correction to Story 2 and
the addition of Story 7a are both logged in-line above with dates, precisely
so scope changes stay visible instead of silent.

Ship criteria: all 14 stories functional, 90%+ correct-citation rate on the
20-question test set. Nothing else gates ship.