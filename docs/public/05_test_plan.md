# LexVault — Proof Metric Test Plan

**Author:** Areeba Hassan
**Status:** Rubric locked. Actual 20 questions **not yet written** — they depend on the 3 demo PDFs, which aren't chosen yet. This doc defines the rules the questions must be written and scored against, so scoring can't be quietly adjusted after the system's behavior is already known.

**Why this doc exists:** `01_mvp_scope.md` defines the metric — 90% correct-citation rate on a 20-question set. It does not define what "correct" means at the edges (partial matches, near-miss pages, borderline not-found cases). Deciding that *after* running the test means the definition bends to fit whatever the system produced. This doc fixes the definition first.

---

## 1. Scoring Rule (locked)

**A question passes if and only if:**
- **Found-type question:** the top-ranked citation returned matches both the correct `document_id` **and** the correct `page_number` exactly.
- **Not-found-type question:** the system returns `result_type: "not_found"`.

**There is no partial credit.** Right document, wrong page = **fail**. This was decided explicitly (not left as a default) because a citation whose page number is wrong is not a citation someone can verify — Story 8 exists specifically so the user can check the source themselves, and a wrong page number defeats that even when the document is right. A metric that counts "close" as a pass would overstate what the system actually proves.

**One consequence worth stating up front:** this scoring rule is strict enough that a single systematic bug (e.g., an off-by-one in page numbering during extraction) could fail every found-type question at once, even if retrieval itself is working. That's intentional — it means the test will surface that bug loudly instead of averaging it away. If page-number-only failures show up across most/all found-type questions, treat it as a bug hunt, not a metric miss.

---

## 2. Question Set Composition (20 total)

| Category | Count | Purpose |
|---|---|---|
| Found — unambiguous | 8 | Direct factual questions with exactly one correct source passage. Baseline retrieval check. |
| Found — requires disambiguation | 4 | Questions where the 3 PDFs contain superficially similar content (e.g., a term defined in two documents) and only one page is the *correct* citation for this specific phrasing. Tests whether the Two-Gate filter and embedding model actually discriminate, not just retrieve *something* plausible. |
| Not-found — genuinely absent | 5 | Questions about topics that don't appear in any of the 3 PDFs at all. Tests the floor gate. |
| Not-found — adjacent/plausible-sounding | 3 | Questions that sound like they *should* be answerable (same domain, similar vocabulary to real content) but aren't actually covered. This is the harder not-found case and the one most likely to produce a hallucinated false-positive — it's the direct test of the "crowded space" problem the architecture doc names as IVFFlat/gap-filter's specific failure mode. |

**Distribution across documents:** each of the 3 PDFs should be the correct source for at least 4 of the found-type questions. A set where 7 of 8 unambiguous questions come from one PDF doesn't test retrieval across the vault — it mostly tests retrieval within one document.

---

## 3. Question Authoring Rules (apply once PDFs are chosen)

1. Each found-type question must have a single verifiably correct `(document_id, page_number)` pair, recorded before the system is run — not determined by reading what the system returns.
2. Questions should use different phrasing than the source text where possible (paraphrase the concept, don't quote the document's exact sentence) — otherwise the test measures keyword overlap, not semantic retrieval, which undercuts the reason bge-small + cosine similarity was chosen over keyword search in the first place.
3. Not-found questions must be plausible enough that a naive system (no gate filtering) would return *something* — an absurd, obviously-unrelated question (e.g., asking a legal-document vault about cooking recipes) doesn't test the gate, it tests whether cosine similarity has a floor at all. At least the 3 "adjacent" not-found questions must share vocabulary/domain with real document content.

---

## 4. Answer-Text Scope

The **citation** (document + page) is what's scored per §1. The generated answer text (Story 7a) is not separately pass/failed in this metric — it's a synthesis layer on top of already-verified citations, and grading prose quality is subjective in a way a locked rubric shouldn't try to arbitrate.

**Exception — hallucination check, not scored, but logged:** for every `found` result, read the generated answer against the cited chunk's actual content. If the answer states something the chunk doesn't support, log it as a **hallucination flag** even if the citation itself passed. This isn't part of the 90% threshold, but a system that cites correctly while still fabricating claims in the prose is a real failure mode Story 7a explicitly names as the risk this architecture takes on — it needs to be visible in results even though it isn't what the frozen metric measures.

---

## 5. Run Procedure

1. Seed the 3 firms with the 3 demo PDFs, wait for all to reach `status: ready` (verifies Story 2/3/4/5/6 work before testing search at all — a failed ingestion isn't a retrieval failure and shouldn't be scored as one).
2. Run all 20 questions through `POST /api/search/` sequentially, same firm/session, recording the full JSON response for each.
3. Score each against the pre-recorded correct answer key from §3 — not against judgment at scoring time.
4. Compute: `passes / 20`. Report the raw pass/fail table, not just the percentage — a 90% that fails two "adjacent not-found" questions tells you something different than a 90% that fails two random found-type questions.
5. Separately report the hallucination-flag count from §4 alongside the score, even though it doesn't gate pass/fail.

---

## 6. Results Table (template — fill in once questions exist)

| # | Category | Question | Correct doc/page | System result | Pass/Fail | Hallucination flag |
|---|---|---|---|---|---|---|
| 1 | Found — unambiguous | | | | | |
| ... | | | | | | |
| 20 | Not-found — adjacent | | | | | |

**Final score:** `__ / 20` (`__%`) — Pass threshold: ≥90% (18/20).

---

## 7. Open Items

- Actual 3 demo PDFs not yet selected — blocks writing real questions in §2/§3.
- File size / content type of the 3 PDFs should be checked against the 25MB cap in `04_api_contract.md` before they're finalized as demo documents.