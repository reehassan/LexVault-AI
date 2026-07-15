# ADR-005 — Chunking Strategy for Document Embeddings

## Status

Accepted

---

## Context

After extracting text from uploaded PDF documents, the text must be divided into smaller pieces ("chunks") before generating embeddings and storing them in PostgreSQL with pgvector.

Embedding an entire document produces vectors that are too broad and significantly reduces retrieval precision. The retrieval pipeline therefore requires a chunking strategy that balances context preservation, retrieval quality, implementation complexity, and reproducibility.

The project uses **Sentence Transformers** for local embedding generation rather than the OpenAI Embeddings API. Because different embedding models use different tokenizers, chunk sizes must be measured using the tokenizer belonging to the embedding model itself instead of a generic tokenizer.

The project goal is to achieve approximately **90% correct citations across 20 evaluation questions on three known PDF documents**, rather than optimizing for arbitrary real-world documents.

---

## Decision

Use **fixed-size overlapping token windows**.

Configuration:

* Chunk size: **500 tokens**
* Overlap: **50 tokens**
* Tokenizer: **The tokenizer provided by the embedding model**
* Chunking method: **Sliding window**
* Page attribution: **Record the page where the chunk begins**

The chunking service will remain a **pure Python module** with no Django or database dependencies.

Its responsibility is only:

```
Extracted Pages
        ↓
Token-Based Chunks
```

It will not:

* generate embeddings
* write database records
* import Django models
* know which embedding model is being used

Instead, the tokenizer is passed into the chunker by the caller.

---

## Rationale

### Fixed-size windows

Advantages:

* Simple implementation.
* Predictable chunk boundaries.
* Easy to debug incorrect retrieval.
* Identical behavior across every document.
* No document-specific heuristics.

Disadvantages:

* May split sentences.
* May split paragraphs.
* Chunks are not always semantically complete.

These disadvantages are acceptable for the MVP because the evaluation corpus is small and known in advance.

---

### 50-token overlap

Without overlap, important context can be lost when information lies across two chunk boundaries.

Example:

```
Chunk A

"...the agreement becomes legally"

Chunk B

"binding after both parties sign..."
```

Neither chunk contains the complete thought.

Adding overlap ensures that boundary information appears in two consecutive chunks, improving retrieval quality.

---

### 500-token chunk size

Small chunks provide high retrieval precision but often lose surrounding context.

Very large chunks preserve context but dilute the embedding by mixing unrelated topics.

A size of approximately **500 tokens** represents a practical compromise between precision and context while remaining computationally inexpensive for local embedding models.

---

### Page attribution

Chunks may span multiple PDF pages because chunk boundaries are determined by token counts rather than page breaks.

Instead of recording the page where a chunk ends, the system stores **the page where the chunk begins**.

Reasons:

* Easier for users to locate cited information.
* Deterministic behaviour.
* Common convention for document references.

---

### Pure Python design

The chunking service deliberately contains **no Django imports**.

Reasons:

* Fast unit tests.
* Reusable outside Django.
* Independent of the ORM.
* Independent of Celery.
* Independent of storage backends.
* Easy to replace or reuse in another project.

Its only responsibility is converting text into chunks.

---

### Tokenizer ownership

The chunker does **not** create or load the embedding model.

Instead, the caller provides the tokenizer.

Reasons:

* Avoids coupling the chunker to one embedding model.
* Makes switching embedding models trivial.
* Improves testability by allowing mock tokenizers.
* Follows dependency injection principles.

---

## Alternatives Considered

### Option 1 — Semantic chunking

Split on paragraph or sentence boundaries.

Advantages:

* Better semantic coherence.
* Higher retrieval quality on complex documents.
* More natural chunks.

Disadvantages:

* More implementation complexity.
* Requires additional heuristics or NLP processing.
* Introduces another tunable component.
* Makes retrieval bugs harder to reproduce because chunk boundaries are no longer deterministic.

Decision:

Rejected for the MVP.

---

### Option 2 — Whole-document embeddings

Generate one embedding per document.

Advantages:

* Extremely simple implementation.

Disadvantages:

* Poor retrieval precision.
* Large documents become semantically diluted.
* Citations become less accurate.

Decision:

Rejected.

---

### Option 3 — Non-overlapping chunks

Advantages:

* Simpler implementation.
* Fewer vectors.

Disadvantages:

* Information crossing chunk boundaries is frequently lost.
* Lower retrieval accuracy.

Decision:

Rejected.

---

## Consequences

Positive:

* Deterministic chunk boundaries.
* Simple implementation.
* Easy debugging.
* Fast execution.
* Reproducible retrieval behaviour.
* Easy unit testing.

Negative:

* Sentences may be split.
* Paragraphs may be split.
* Retrieval quality is lower than semantic chunking on messy real-world documents.

---

## Future Improvements

Possible future upgrades include:

* Semantic chunking.
* Heading-aware chunking.
* Paragraph-aware chunking.
* Adaptive chunk sizes.
* OCR-aware chunking for scanned PDFs.
* Hybrid semantic and token-based chunking.
* Metadata-aware chunking (titles, headings, tables).

These improvements are intentionally deferred until retrieval quality becomes a demonstrated limitation.

---

## Decision Summary

The project adopts **fixed-size overlapping token windows (500 tokens with 50-token overlap)** using the tokenizer supplied by the embedding model. This approach provides deterministic behaviour, sufficient retrieval quality for the MVP, straightforward debugging, and a clean separation of concerns while leaving semantic chunking as the primary future enhancement.
