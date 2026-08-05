# LexVault Vector Search Performance

## Overview

This document benchmarks PostgreSQL pgvector HNSW search performance.

## Environment

Database:
PostgreSQL + pgvector

Index:
HNSW

Index name:
idx_chunk_embedding

Distance metric:
Cosine similarity

Embedding dimensions:
384

Embedding model:
bge-small-en-v1.5


## Dataset

Initial dataset:

391 chunks


Benchmark dataset:

100391 chunks


---

# Small Dataset Results

Dataset:
391 chunks


Query Plan:

Seq Scan


Execution Time:

7.805 ms


Observation:

PostgreSQL ignored the HNSW index because the dataset was small.

Sequential scanning all rows was cheaper than traversing the HNSW graph.


---

# Large Dataset Results

Dataset:

100391 chunks


## Vector Search

Query:

ORDER BY embedding <=> query_vector
LIMIT 5


Query Plan:

Index Scan using idx_chunk_embedding


Execution Time:

22.211 ms


Observation:

PostgreSQL selected the HNSW index because the dataset size justified index traversal.


---

# Multi-Tenant Vector Search

Query:

WHERE firm_id = tenant_id
ORDER BY embedding <=> query_vector
LIMIT 5


Query Plan:

Index Scan using idx_chunk_embedding


Execution Time:

3.400 ms


Observation:

The HNSW index was used while maintaining tenant filtering.


---

# Conclusion

PostgreSQL query planning is cost-based.

An index existing does not guarantee usage.

For small datasets:
- Sequential scans are faster.

For large vector datasets:
- HNSW provides efficient approximate nearest neighbor search.

LexVault uses HNSW vector indexing with tenant filtering to support scalable RAG retrieval.