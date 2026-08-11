# LexVault-AI

A self-hosted, multi-tenant AI knowledge vault that lets teams — currently scoped around legal firms — ask natural-language questions about their own documents. Instead of searching by filename or keyword, the system retrieves semantically relevant document sections via vector search and generates answers grounded only in that retrieved content.

## Status

**In active development** — currently on the search endpoint, building on top of a working ingestion and retrieval pipeline (71 passing tests, 96% coverage).

## Why self-hosted

Most RAG demos wrap OpenAI's API and call it a day. LexVault runs its own embedding model and its own LLM, end to end, on infrastructure you control:

- **Embeddings**: `bge-small-en-v1.5`, 384-dimension vectors, run locally via sentence-transformers
- **Generation**: Llama 3.2 (1B) via Ollama — no third-party inference API in the loop
- **Vector search**: PostgreSQL + pgvector with HNSW indexing

This matters for the target use case: legal and other regulated teams often can't send client documents to a third-party API in the first place.

## Architecture

- **Multi-tenancy**: shared-schema, row-level isolation via `firm_id` scoping — not schema-per-tenant, to keep operational overhead low at this scale
- **Primary keys**: UUIDv7 across the board, for time-ordered IDs without exposing sequential integers
- **Citation system**: answers are only as good as their grounding — every claim traces back to an exact document ID and page number, no partial credit. Target: 90%+ citation accuracy over 50+ held-out questions
- **Rate limiting**: 10 requests/minute on search endpoints
- **Async processing**: Celery + Redis for the ingestion pipeline (chunking, embedding)

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Django |
| Database | PostgreSQL + pgvector |
| Embeddings | bge-small-en-v1.5 (384-dim) |
| LLM | Llama 3.2 1B via Ollama |
| Async | Celery, Redis |
| IDs | UUIDv7 |

## Engineering approach

Built API-contract-first: a written API contract and test plan exist before implementation, not after. Development is logged day-by-day, including the wrong turns — dependency resolution issues, dropped pipeline code recovered from git history, architectural drift caught and corrected. See `docs/public/` for the dev log.

## Roadmap

- [x] Ingestion pipeline (chunking, embedding, storage)
- [x] Citation scoring + test suite
- [ ] Search endpoint (in progress)
- [ ] Query-side asymmetric encoding (bge-small-en-v1.5 requires an instruction prefix on queries — separate from document encoding — not yet reflected in the spec)
- [ ] Full RAG answer generation with citation enforcement

## License

Apache-2.0 — see [LICENSE](./LICENSE).
