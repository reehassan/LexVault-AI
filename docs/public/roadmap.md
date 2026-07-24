# LexVault Sprint Plan (Architecture-Aligned)

# Week 1 — SDLC Phases 0 to 3.5 (Design Only)

**Goal:** Finish every architectural decision before writing Django code.

**Deliverable by Day 6**

* Problem Brief
* Frozen Scope Document
* User Stories
* Low-Fidelity Wireframes
* URL Contract
* ERD
* Architecture Document
* Security Design
* Architecture Decision Records (ADRs)

**Rule:** No Django project is created until every design document is frozen.

---

# Day 1 — Phase 0 + Phase 1: Problem Definition & Simulated Validation

## Concepts to Learn

* What a problem statement is
* Difference between symptoms and root causes
* Product assumptions vs facts
* What a portfolio project should prove
* What a "riskiest assumption" means

## Build Steps

* Write the one-sentence problem statement.

  > "Knowledge workers waste time manually searching through internal documents because traditional keyword search cannot understand semantic meaning."

* Define the target users.

* Write the business value.

* Write the technical value the project demonstrates.

* List the biggest assumption that could invalidate the project.

* Simulate three user interviews using AI to challenge your assumptions.

* Revise and freeze the final Problem Brief.

---

# Day 2 — Phase 2: Scope Definition & Feature Freeze

## Concepts to Learn

* Functional vs non-functional requirements
* MVP thinking
* User stories
* Acceptance criteria
* In-scope vs out-of-scope features
* Why scope creep kills projects

## Build Steps

Write the complete Scope Document.

Include:

* North Star Metric
* Success Metrics
* Functional Requirements
* Non-functional Requirements
* User Stories
* Out-of-Scope Features
* Technical Constraints

Freeze the scope after review.

---

# Day 3 — Phase 2.5: User Flows & Wireframes

## Concepts to Learn

* User flows
* Happy path
* Alternative paths
* Low-fidelity wireframes
* UI components
* Screen decomposition

## Build Steps

Draw the complete user journey.

```
Login
↓

Dashboard
↓

Upload PDF
↓

Processing Status
↓

Ready
↓

Search

↓

Answer + Citation
```

Create wireframes for:

* Login
* Dashboard
* Upload
* Document List
* Search
* Search Results

Identify reusable UI components:

* Navbar
* Upload Card
* Status Badge
* Search Box
* Citation Card
* Toast Messages

---

# Day 4 — Phase 3: URL Design & Database Design

## Concepts to Learn

* REST fundamentals
* HTTP verbs
* Entity Relationship Diagrams
* Primary Keys
* Foreign Keys
* UUIDv7
* Constraints
* Indexes
* Cascade vs Protect

## Build Steps

### 1. Create the URL Contract

Document every endpoint before coding.

Example:

```
POST   /login
POST   /logout

GET    /dashboard

POST   /documents/upload
GET    /documents
DELETE /documents/{id}

POST   /search

GET    /events/document-status
```

---

### 2. Design the ERD

Use the actual production schema.

Entities

* Firm
* User
* Document
* Chunk
* SearchQuery
* Citation

For every table define:

* UUIDv7 primary key
* Data types
* Nullable fields
* Foreign keys
* Unique constraints
* Indexes

Include architectural decisions:

* Shared-schema multi-tenancy
* Mandatory `firm_id`
* Denormalized `firm_id` on `Chunk`
* Denormalized `firm_id` on `SearchQuery`

Do **not** design schema-per-tenant.

---

# Day 5 — Phase 3: Architecture Design

## Concepts to Learn

* Layered architecture
* Background workers
* Vector databases
* Semantic search pipeline
* Storage abstraction
* Architecture Decision Records (ADR)
* Trade-off analysis

## Build Steps

Draw the complete architecture diagram.

```
Browser

↓

Nginx

↓

Django

↓

Celery + Redis

↓

PyMuPDF

↓

Chunker

↓

bge-small-en-v1.5

↓

pgvector (HNSW)

↓

Two-Gate Filter

↓

llama3.2:1b (Ollama)

↓

Answer
```

Document every architectural decision and why alternatives were rejected.

Write ADRs for:

* UUIDv7
* Shared Schema
* Django Sessions
* Redis-backed Sessions
* PyMuPDF
* pgvector HNSW
* bge-small-en-v1.5
* llama3.2:1b
* Two-Gate Filtering
* SSE
* Celery
* Local Storage
* DRF Throttling
* HTMX
* Oracle Cloud

Every ADR should contain:

* Decision
* Alternatives
* Reason
* Trade-offs

---

# Day 6 — Phase 3.5: Security Design

## Concepts to Learn

* Authentication vs Authorization
* Tenant Isolation
* Session Security
* Input Validation
* File Upload Security
* Rate Limiting
* Principle of Least Privilege
* Data Protection

## Build Steps

Write the Security Design Document.

Define authentication.

* Django Sessions
* Redis-backed session storage
* Session cookie settings

Define tenant isolation.

Every database query **must** be scoped by `firm_id`.

Special attention:

* Document queries
* Chunk retrieval
* Search history
* Vector search

Document file upload security.

* MIME validation
* File size limits
* PDF-only uploads
* Filename sanitization

Document search security.

* DRF Throttling
* Query validation
* SSE endpoint protection

List every user input.

* Login
* Upload
* Search
* Delete Document

Explain how each input is validated.

Finally, complete the Security Checklist.

* Authentication
* Authorization
* Tenant Isolation
* File Validation
* Session Security
* Rate Limiting
* Secure Headers
* HTTPS
* Error Handling

Freeze every design document.

**Week 1 Exit Criteria**

Before writing any Django code, you should have completed:

* Problem Brief
* Scope Document
* User Stories
* Wireframes
* URL Contract
* ERD
* Architecture Diagram
* ADRs
* Security Design

Once these documents are frozen, the project moves to implementation in **Week 2**.

# Week 2 — Project Setup, Shared-Schema Multi-Tenancy & Core Models

**Goal:** Build the project foundation—configure Django, implement the shared-schema multi-tenant architecture, create the core database models, and enable pgvector.

**Deliverable by Day 12**

* Django project configured
* Docker development environment
* PostgreSQL + pgvector running
* Redis configured
* Custom User model
* Shared-schema tenant isolation
* Authentication working with Django Sessions
* Core models migrated
* pgvector extension enabled
* UUIDv7 primary keys
* Tenant isolation tests passing

---

# Day 7 — Project Setup & Custom User Model

## Concepts to Learn

* Project structure
* Settings splitting (`base.py`, `dev.py`, `prod.py`)
* Environment variables
* Docker development workflow
* Why the custom User model must be created before the first migration
* UUIDv7 primary keys
* `AbstractUser`
* `AUTH_USER_MODEL`

## Build Steps

Create the Django project.

Configure:

* Git repository
* `.gitignore`
* `.env`
* `.env.example`
* Docker Compose
* PostgreSQL
* Redis

Create settings modules:

```
config/settings/
    base.py
    dev.py
    prod.py
```

Create the custom User model.

Implement:

* UUIDv7 primary key
* `firm` ForeignKey
* username
* email
* timestamps

Configure:

```
AUTH_USER_MODEL
```

Run the initial migrations.

Verify authentication still works.

---

# Day 8 — Shared-Schema Multi-Tenant Foundation

## Concepts to Learn

* Shared-schema multi-tenancy
* Why `firm_id` exists on every business entity
* Tenant isolation at the application layer
* Foreign keys
* Query filtering
* Why schema-per-tenant was rejected

## Build Steps

Create the Firm model.

Implement:

* UUIDv7 primary key
* name
* created_at

Update the User model.

Every user belongs to exactly one Firm.

Create the custom authentication backend.

The backend should:

* authenticate username/password
* resolve duplicate usernames across firms
* attach the correct user to the session

Implement middleware/helpers for tenant access.

Every authenticated request should easily access:

```
request.user.firm
```

Document the tenant isolation rule:

> Every query that returns tenant-owned data must include a `firm_id` filter.

Write the first tenant isolation tests.

Examples:

* Firm A users cannot see Firm B documents.
* Duplicate usernames across firms authenticate correctly.
* Session stores the authenticated user's firm.

---

# Day 9 — Authentication & Session Management

## Concepts to Learn

* Django Sessions
* Redis-backed sessions
* Session cookies
* Authentication vs Authorization
* Login flow
* Logout flow
* LoginRequiredMixin

## Build Steps

Configure Redis-backed sessions.

Implement:

* Login view
* Logout view
* Session creation
* Session destruction

Configure session settings.

Review:

* cookie security
* expiration
* CSRF protection

Create login template.

Verify:

```
POST /login
↓

authenticate()

↓

Session created

↓

Dashboard
```

Write authentication tests.

Test:

* valid login
* invalid password
* inactive user
* logout
* session persistence

---

# Day 10 — Core Models

## Concepts to Learn

* Model relationships
* One-to-many relationships
* UUID Foreign Keys
* TextChoices
* Constraints
* Indexes
* Cascade vs Protect

## Build Steps

Create the following models.

## Document

Include:

* UUIDv7
* firm
* uploaded_by
* filename
* storage_path
* page_count
* file_size
* processing_status
* timestamps

---

## Chunk

Include:

* UUIDv7
* document
* firm (denormalized)
* page_number
* chunk_index
* chunk_text
* embedding (added tomorrow)
* timestamps

Create constraints.

Example:

* unique(document, chunk_index)

Create indexes.

Index:

* firm
* document
* processing_status

Run migrations.

Write model tests.

---

# Day 11 — Search History & Citation Models

## Concepts to Learn

* Audit logging
* Search history
* Why Citation is its own table
* Database normalization
* Query analytics

## Build Steps

Create:

## SearchQuery

Fields:

* UUIDv7
* firm
* user
* query
* response_time
* result_type
* created_at

Create:

## Citation

Fields:

* UUIDv7
* search_query
* chunk
* similarity_score
* rank

Relationships:

```
SearchQuery

↓

Citation

↓

Chunk
```

Run migrations.

Write tests.

Verify:

One search can reference multiple chunks.

---

# Day 12 — pgvector Setup & Chunk Embeddings

## Concepts to Learn

* pgvector
* PostgreSQL extensions
* Vector embeddings
* 384-dimensional vectors
* HNSW indexes
* Cosine similarity

## Build Steps

Install:

* pgvector
* django-pgvector

Create migration.

Enable:

```
CREATE EXTENSION vector;
```

Update Chunk model.

Add:

```
VectorField(dimensions=384)
```

Create HNSW index.

Configure cosine similarity.

Verify:

* migrations succeed
* vectors store correctly
* HNSW index created
* cosine queries execute

Write tests.

Test:

* Vector field accepts 384 dimensions.
* Wrong dimensions raise an error.
* HNSW index exists.
* pgvector extension installed.

---

# Week 2 Exit Criteria

Before starting Week 3, the following should be complete:

* Django project configured
* Docker environment running
* PostgreSQL + pgvector running
* Redis configured
* UUIDv7 primary keys
* Shared-schema multi-tenancy
* Firm model
* Custom User model
* Django Session authentication
* Redis-backed sessions
* Custom authentication backend
* Document model
* Chunk model
* SearchQuery model
* Citation model
* pgvector enabled
* HNSW index created
* Tenant isolation tests passing
* Authentication tests passing
* Model tests passing

Week 3 begins the ingestion pipeline: PDF upload, Celery, PyMuPDF extraction, and chunk generation.

# Week 3 — File Upload & Ingestion Pipeline

**Goal:** Build the complete ingestion pipeline that accepts a PDF, stores it, processes it asynchronously, extracts text, chunks it, and updates document status.

**Deliverable by Day 18**

* Celery + Redis running
* File upload working
* Local file storage configured
* PDF extraction service completed
* Chunking service completed
* Processing pipeline tested
* Document status updates working

---

# Day 13 — Celery & Redis Setup

## Concepts to Learn

* Why background processing is necessary
* Celery architecture
* Redis as broker
* Redis as result backend
* Celery workers
* Flower monitoring
* Docker networking

## Build Steps

Configure Docker Compose.

Services:

* PostgreSQL
* Redis
* Django
* Celery Worker
* Flower

Configure Celery.

Create:

```text
config/celery.py
```

Configure:

* Broker URL
* Result backend
* Task discovery

Create a test task.

```python
add(x, y)
```

Run the worker.

Verify:

* Worker connects to Redis
* Task executes
* Flower displays task history

Configure test settings.

Enable:

```text
CELERY_TASK_ALWAYS_EAGER = True
```

---

# Day 14 — PDF Upload & Document Creation

## Concepts to Learn

* Django FileField
* django-storages
* Local filesystem driver
* MIME validation
* File upload security
* python-magic

## Build Steps

Configure django-storages.

Storage backend:

* Local filesystem

Do **not** configure:

* S3
* Cloudflare R2
* MinIO

Create the upload endpoint.

```text
POST /documents/upload
```

Validate:

* PDF MIME type
* File size
* Authenticated user

Create the Document record.

Store:

* firm_id
* uploaded_by
* filename
* storage_path
* processing_status = uploaded

After saving:

Queue

```text
process_document.delay(document_id)
```

Return upload success.

Write tests.

Test:

* Valid PDF
* Invalid MIME type
* Oversized file
* Unauthenticated upload

---

# Day 15 — PDF Extraction Service

## Concepts to Learn

* PyMuPDF
* PDF pages
* Text extraction
* Page mapping
* Exception handling
* Pure service design

## Build Steps

Create:

```text
services/extractor.py
```

Write:

```python
extract_pages(path)
```

Return:

```python
[
    {
        "page":1,
        "text":"..."
    }
]
```

Handle:

* Empty pages
* Corrupted PDFs
* Encrypted PDFs

Raise custom exceptions.

Create:

* ExtractionError
* CorruptedPDFError
* EncryptedPDFError
* EmptyPDFError

Write unit tests.

No Django imports.

No database access.

---

# Day 16 — Chunking Service

## Concepts to Learn

* Tokenization
* Sliding window chunking
* Token overlap
* Why overlap improves retrieval
* Fixed-size chunking
* Token limits

## Build Steps

Create:

```text
services/chunker.py
```

Implement:

```python
chunk_pages()
```

Chunk strategy:

* 300–400 tokens
* 50 token overlap

Return:

```python
[
    {
        "chunk_index":0,
        "page_number":1,
        "chunk_text":"...",
        "token_count":356
    }
]
```

Requirements:

* Preserve page attribution
* Sequential chunk numbering
* Deterministic output

Write ADR.

Explain:

Why fixed-size chunking was chosen over semantic chunking.

Write unit tests.

Test:

* Small PDFs
* Large PDFs
* Blank pages
* Long pages
* Single-page PDFs

---

# Day 17 — Celery Pipeline Assembly

## Concepts to Learn

* Pipeline orchestration
* Task lifecycle
* transaction.atomic()
* bulk_create()
* Database consistency
* Status transitions

## Build Steps

Implement:

```text
process_document()
```

Pipeline:

```text
Document

↓

processing

↓

Extract Pages

↓

Chunk Text

↓

Store Chunks

↓

ready
```

Inside one task:

1. Load Document

2. Update status

```text
processing
```

3. Extract text

4. Chunk text

5. Store Chunk records

6. Update

* page count
* status
* timestamps

On failure:

Set

```text
failed
```

Use:

```python
transaction.atomic()
```

Ensure partial writes cannot occur.

Write integration tests.

Verify:

* Chunks created
* Status changes
* Rollback on failure

---

# Day 18 — Ingestion Pipeline Testing & Status Tracking

## Concepts to Learn

* Integration testing
* End-to-end pipeline
* Processing lifecycle
* Status management
* Logging
* Error recovery

## Build Steps

Test complete ingestion.

Upload PDF.

Verify lifecycle.

```text
uploaded

↓

processing

↓

ready
```

Verify failures.

```text
uploaded

↓

processing

↓

failed
```

Check:

* Chunk count
* Page count
* Firm isolation
* File storage path
* Processing time

Add logging.

Log:

* Upload
* Extraction
* Chunking
* Database writes
* Failures

Write pipeline integration tests.

Test:

* Normal PDF
* Corrupted PDF
* Encrypted PDF
* Empty PDF

Verify every document remains scoped to its own `firm_id`.

---

# Week 3 Exit Criteria

Before starting Week 4, you should have:

* Celery running
* Redis running
* Flower monitoring tasks
* Upload endpoint complete
* Local filesystem storage configured
* django-storages configured
* PDF validation complete
* PyMuPDF extraction service
* Chunking service
* 300–400 token chunks
* 50-token overlap
* Chunk records stored
* Document status updates
* Transaction-safe pipeline
* Integration tests passing
* Tenant isolation maintained throughout ingestion

Week 4 will add semantic embeddings using **bge-small-en-v1.5**, store vectors in **pgvector**, and complete the end-to-end retrieval pipeline.

# Week 4 — Embeddings & Semantic Retrieval Pipeline

**Goal:** Transform extracted chunks into searchable vector embeddings, implement semantic retrieval, and verify that tenant-isolated vector search works correctly.

**Deliverable by Day 24**

* Local embedding service complete
* bge-small-en-v1.5 integrated
* 384-dimensional vectors stored
* HNSW index verified
* End-to-end ingestion pipeline complete
* Semantic retrieval working
* Tenant isolation enforced during vector search

---

# Day 19 — Local Embedding Service

## Concepts to Learn

* What sentence embeddings are
* Dense vectors
* Why semantic search works
* Sentence Transformers
* Local inference
* CPU inference
* Embedding dimensions

## Build Steps

Install:

* sentence-transformers

Download:

```text
bge-small-en-v1.5
```

Create:

```text
services/embedder.py
```

Implement:

```python
embed_chunks(chunks)
```

Return:

```python
List[List[float]]
```

Requirements:

* Load model once
* Reuse model instance
* CPU inference
* Batch embedding generation

Verify:

Each embedding contains exactly

```text
384
```

floating-point values.

Write unit tests.

Test:

* Single chunk
* Multiple chunks
* Empty input
* Invalid input

---

# Day 20 — Embedding Pipeline Integration

## Concepts to Learn

* Batch processing
* Memory efficiency
* Bulk database operations
* Vector persistence
* Database transactions

## Build Steps

Extend the ingestion pipeline.

New workflow:

```text
Extract

↓

Chunk

↓

Generate Embeddings

↓

Store Chunks + Vectors

↓

Ready
```

Modify

```text
process_document()
```

Pipeline:

1. Extract pages

2. Generate chunks

3. Generate embeddings

4. Attach embedding to every Chunk

5. Bulk insert Chunk records

Store:

* chunk_text
* page_number
* chunk_index
* firm_id
* embedding

Use

```python
bulk_create()
```

inside

```python
transaction.atomic()
```

Write integration tests.

Verify:

* Every chunk has an embedding.
* Every embedding has 384 dimensions.
* No partial writes occur.

---

# Day 21 — Vector Search Service

## Concepts to Learn

* Cosine similarity
* Approximate Nearest Neighbor (ANN)
* HNSW search
* Top-k retrieval
* Why tenant filtering happens before retrieval
* pgvector ORM functions

## Build Steps

Create:

```text
services/search.py
```

Implement:

```python
retrieve_chunks(
    query_embedding,
    firm_id,
    top_k=5
)
```

Workflow:

```text
Question

↓

Embedding

↓

Filter by firm_id

↓

Cosine similarity

↓

Top K chunks
```

Requirements:

* Filter by `firm_id`
* Order by cosine similarity
* Return top 5 chunks
* Include similarity scores

Write unit tests.

Test:

* Firm A never retrieves Firm B chunks.
* Results ordered by similarity.
* Empty vault returns no results.

---

# Day 22 — HNSW Index Verification & Performance

## Concepts to Learn

* Query planning
* EXPLAIN ANALYZE
* Sequential scan
* Index scan
* HNSW performance
* Query optimization

## Build Steps

Verify the HNSW index.

Run:

```sql
EXPLAIN ANALYZE
```

Compare:

Without index

↓

With HNSW index

Confirm PostgreSQL uses the HNSW index.

Measure:

* Retrieval latency
* Insert time
* Search performance

Document observations.

Write performance notes for the project documentation.

---

# Day 23 — Pipeline Integration Testing

## Concepts to Learn

* Integration testing
* End-to-end processing
* Factory-based testing
* Mocking local services
* Database assertions

## Build Steps

Write complete pipeline tests.

Workflow:

```text
Upload PDF

↓

Extract

↓

Chunk

↓

Embed

↓

Store

↓

Retrieve
```

Verify:

* Document status becomes **ready**
* Chunk count is correct
* Every chunk has an embedding
* Embedding dimension is 384
* Retrieval returns relevant chunks

Test tenant isolation.

Create:

* Firm A
* Firm B

Upload different PDFs.

Search as Firm A.

Assert:

Only Firm A chunks are returned.

---

# Day 24 — Pipeline Validation & Developer Documentation

## Concepts to Learn

* Developer documentation
* Architecture verification
* Debug logging
* Observability

## Build Steps

Run complete ingestion tests using multiple PDFs.

Verify:

* Upload succeeds.
* Processing completes.
* Chunks created.
* Embeddings generated.
* Vectors searchable.

Review logs.

Confirm every stage logs correctly:

* Upload received
* Extraction started
* Chunking complete
* Embedding complete
* Database write complete
* Processing finished

Update:

```text
devlog.md
```

Record:

* Problems encountered
* Design decisions
* Lessons learned
* Performance observations

Review the architecture document.

Confirm implementation matches:

* Shared-schema multi-tenancy
* UUIDv7
* Local embeddings
* 384-dimensional vectors
* pgvector
* HNSW
* Celery
* Redis
* Local storage

No architectural drift should exist before beginning the search system.

---

# Week 4 Exit Criteria

Before starting Week 5, you should have:

* Local embedding service complete
* bge-small-en-v1.5 integrated
* 384-dimensional embeddings
* Chunk embeddings stored in PostgreSQL
* HNSW index verified
* Semantic retrieval service complete
* Top-k search working
* Tenant-isolated vector search
* End-to-end ingestion pipeline complete
* Integration tests passing
* Performance verified
* Documentation updated

Week 5 will implement the user-facing search experience, including the **Two-Gate Adaptive Context Selection**, **llama3.2:1b via Ollama**, **SSE live status updates**, and the complete HTMX interface.

# Week 5 — Search System, Two-Gate Filtering & HTMX Interface

**Goal:** Build the complete search experience—from query embedding to answer generation—using tenant-isolated semantic retrieval, the Two-Gate Adaptive Context Selection algorithm, a local LLM, Server-Sent Events (SSE), and an HTMX frontend.

**Deliverable by Day 30**

* Semantic search endpoint
* Two-Gate relevance filtering
* Local LLM integration (llama3.2:1b)
* Search history logging
* Citation tracking
* SSE document status updates
* HTMX interface complete
* End-to-end search working

---

# Day 25 — Search Endpoint & Vector Retrieval

## Concepts to Learn

* Semantic search
* Query embeddings
* Cosine similarity
* Top-k retrieval
* Tenant isolation during search
* Search pipeline

## Build Steps

Create:

```text
services/search.py
```

Implement:

```python
search_documents(question, firm_id)
```

Pipeline:

```text
User Question

↓

Generate Query Embedding

↓

Filter by firm_id

↓

Cosine Similarity Search

↓

Top 5 Chunks
```

Requirements

* Embed the user's question using **bge-small-en-v1.5**
* Retrieve only chunks belonging to the authenticated user's firm
* Return similarity scores
* Return document title
* Return page number

Create the search endpoint.

```text
POST /search
```

Write tests.

Verify:

* Empty query rejected
* Search succeeds
* Empty vault returns no chunks
* Firm A never retrieves Firm B chunks

---

# Day 26 — Two-Gate Adaptive Context Selection

## Concepts to Learn

* Relevance thresholds
* Similarity scores
* False positives
* Precision vs Recall
* Context reduction
* Adaptive filtering

## Build Steps

Create:

```text
services/filter.py
```

Implement:

```python
apply_two_gate_filter()
```

Pipeline:

```text
Top K Chunks

↓

Gate 1

Minimum Similarity Floor

↓

Gate 2

Relative Gap Filter

↓

Relevant Context
```

Implement both gates.

### Gate 1

Reject chunks below the minimum similarity threshold.

### Gate 2

Remove redundant chunks using the relative similarity gap.

Requirements

* Both gates must pass
* Return surviving chunks
* Return "Not found in vault" if nothing survives

Write comprehensive tests.

Test:

* Perfect match
* Multiple relevant chunks
* All low scores
* Crowded low-score space
* Single surviving chunk
* No surviving chunks

Document why this approach was chosen over:

* Fixed threshold only
* Relative gap only

---

# Day 27 — Local LLM Answer Generation

## Concepts to Learn

* Retrieval-Augmented Generation (RAG)
* Prompt engineering
* Context grounding
* Hallucinations
* Local inference
* Ollama API

## Build Steps

Install:

* Ollama

Download:

```text
llama3.2:1b
```

Create:

```text
services/generator.py
```

Implement:

```python
generate_answer(
    question,
    chunks
)
```

Prompt requirements:

* Only answer using supplied context
* Never invent information
* Return "Not found in vault" when instructed
* Cite supporting documents

Pipeline:

```text
Question

↓

Relevant Chunks

↓

llama3.2:1b

↓

Answer
```

Write tests.

Verify:

* Correct answer generation
* Proper citations
* Not-found response
* Empty context handling

---

# Day 28 — Search Logging & Citation Tracking

## Concepts to Learn

* Audit trails
* Search analytics
* Database normalization
* Citation storage
* Performance measurement

## Build Steps

Extend the search endpoint.

Complete workflow:

```text
Question

↓

Embedding

↓

Vector Search

↓

Two-Gate Filter

↓

LLM

↓

Save SearchQuery

↓

Save Citation Records
```

Store SearchQuery:

* User
* Firm
* Query
* Response time
* Result type

Store Citation:

* Chunk
* Rank
* Similarity score

Measure:

* Embedding time
* Retrieval time
* Generation time
* Total latency

Write integration tests.

Verify:

* SearchQuery created
* Citation records created
* Response time recorded
* Multiple citations supported

---

# Day 29 — HTMX Search Interface & SSE Status Updates

## Concepts to Learn

* HTMX
* Partial page rendering
* Server-Sent Events (SSE)
* StreamingHttpResponse
* Progressive UI updates

## Build Steps

Create the dashboard.

Sections:

* Upload
* Documents
* Search
* Search Results

Implement HTMX.

Use:

* hx-post
* hx-target
* hx-swap
* hx-indicator

Create search results partial.

Display:

* Generated answer
* Document title
* Page number
* Similarity-based citations

Implement SSE.

Create endpoint.

```text
GET /events/document-status
```

Use:

```python
StreamingHttpResponse
```

Stream:

```text
uploaded

↓

processing

↓

ready

↓

failed
```

Requirements

* No polling
* No WebSockets
* No Django Channels

Test:

* Upload PDF
* Observe live status updates
* Confirm search works without page refresh

---

# Day 30 — Complete User Workflow & End-to-End Testing

## Concepts to Learn

* User acceptance testing
* End-to-end validation
* Production workflows
* Error handling
* Performance verification

## Build Steps

Validate the complete application.

Workflow:

```text
Login

↓

Upload PDF

↓

Live Processing Updates (SSE)

↓

Ready

↓

Search Question

↓

Vector Search

↓

Two-Gate Filter

↓

llama3.2:1b

↓

Answer + Citation
```

Test scenarios.

Successful search.

Verify:

* Correct answer
* Correct citation
* Correct document
* Correct page number

Test failures.

Verify:

* Empty vault
* No relevant information
* Invalid query
* Deleted document
* Unauthorized access

Measure:

* Processing time
* Search latency
* Generation latency

Review every endpoint.

Confirm:

* Authentication required
* Tenant isolation enforced
* DRF throttling enabled
* Validation complete

---

# Week 5 Exit Criteria

Before starting Week 6, you should have:

* Search endpoint complete
* Query embedding working
* Tenant-isolated vector retrieval
* Two-Gate Adaptive Context Selection implemented
* Local LLM (llama3.2:1b) integrated
* SearchQuery logging
* Citation tracking
* HTMX search interface
* SSE live status updates
* End-to-end RAG pipeline working
* Comprehensive integration tests passing

Week 6 focuses on production readiness: automated testing, CI/CD, Docker deployment, Oracle Cloud deployment, monitoring, documentation, and the final portfolio demo.

# Week 6 — Testing, Deployment & Project Completion

**Goal:** Make LexVault production-ready by completing automated testing, containerization, deployment, monitoring, documentation, and the final portfolio presentation.

**Deliverable by Day 36**

* Comprehensive automated test suite
* GitHub Actions CI pipeline
* Dockerized application
* Oracle Cloud deployment
* HTTPS enabled
* Monitoring configured
* Complete documentation
* Demo video recorded
* Portfolio-ready project

---

# Day 31 — Comprehensive Testing

## Concepts to Learn

* Unit testing
* Integration testing
* End-to-end testing
* Test coverage
* Factory Boy
* Security testing

## Build Steps

Review every feature implemented during the previous five weeks.

Write unit tests for:

* Authentication
* Models
* Services
* Utility functions
* Validation

Write integration tests for:

* Upload pipeline
* Search pipeline
* Authentication flow
* SSE endpoint
* HTMX views

Write security tests.

Verify:

* Tenant isolation
* Session authentication
* Unauthorized access
* File upload validation
* Search authorization

Write business logic tests.

Test:

* Two-Gate filtering
* Vector retrieval
* Local embedding generation
* Ollama answer generation

Generate a coverage report.

Aim for:

* High coverage on business logic
* 100% coverage for tenant isolation and security-critical code

---

# Day 32 — Continuous Integration

## Concepts to Learn

* Continuous Integration (CI)
* GitHub Actions
* Workflow automation
* Automated testing
* Build pipelines

## Build Steps

Create:

```text
.github/workflows/ci.yml
```

Pipeline stages:

```text
Checkout Code

↓

Install Dependencies

↓

Start PostgreSQL

↓

Start Redis

↓

Run Migrations

↓

Run Pytest

↓

Generate Coverage
```

Configure GitHub Actions services:

* PostgreSQL (with pgvector)
* Redis

Verify:

* Every push runs tests
* Pull requests run tests
* Failed tests block merges

Add branch protection for the main branch.

---

# Day 33 — Docker Production Environment

## Concepts to Learn

* Multi-container applications
* Docker Compose
* Gunicorn
* Nginx
* Health checks
* Persistent volumes

## Build Steps

Finalize:

```text
Dockerfile
```

Create production-ready:

```text
docker-compose.yml
```

Services:

* nginx
* django
* postgresql
* redis
* celery-worker
* flower

Configure:

* Gunicorn
* Static files
* Media files
* Health checks
* Environment variables

Verify:

```text
docker compose up
```

works without manual intervention.

Test:

* Upload
* Search
* Celery
* SSE
* Ollama integration

inside Docker.

---

# Day 34 — Oracle Cloud Deployment

## Concepts to Learn

* Oracle Cloud Compute
* SSH authentication
* Reverse proxy
* HTTPS
* SSL certificates
* Production deployment

## Build Steps

Provision:

Oracle Cloud Ubuntu VPS

Configure:

* SSH keys
* Firewall
* Docker
* Docker Compose
* Git

Deploy application.

Configure:

* Nginx
* Gunicorn
* PostgreSQL
* Redis
* Celery
* Ollama

Enable HTTPS using Let's Encrypt.

Verify:

* Login
* Upload
* Search
* SSE
* Document management

all work correctly on the live server.

Create database backup procedure.

Verify restoration works.

---

# Day 35 — Monitoring & Production Validation

## Concepts to Learn

* Application monitoring
* Error tracking
* Health monitoring
* Backup strategy
* Production verification

## Build Steps

Configure:

### Sentry

Monitor:

* Django errors
* Celery exceptions
* Unhandled exceptions

Configure:

### UptimeRobot

Monitor:

* Homepage
* Login
* Search endpoint

Run:

```text
python manage.py check --deploy
```

Resolve every warning.

Perform production validation.

Upload several PDFs.

Verify:

* Extraction
* Chunking
* Embeddings
* Vector search
* Two-Gate filtering
* Answer generation
* Citations

Measure:

* Upload time
* Processing time
* Search latency
* Generation latency

Review logs.

Confirm no unexpected errors remain.

---

# Day 36 — Documentation & Portfolio Presentation

## Concepts to Learn

* Technical documentation
* Architecture Decision Records (ADR)
* Portfolio storytelling
* Software demonstrations

## Build Steps

Complete the project README.

Include:

* Project overview
* Features
* Technology stack
* Architecture
* Installation
* Environment variables
* Running locally
* Running tests
* Docker deployment
* Oracle Cloud deployment
* Project structure
* Future improvements

Complete Architecture Decision Records.

Document:

* UUIDv7 over BIGSERIAL
* Shared-schema multi-tenancy
* Django Sessions over JWT
* Redis-backed sessions
* PyMuPDF over alternatives
* Fixed-size chunking
* bge-small-en-v1.5 embeddings
* pgvector + HNSW
* Two-Gate Adaptive Context Selection
* Ollama + llama3.2:1b
* SSE over polling/WebSockets
* Celery + Redis
* Local filesystem storage
* DRF throttling
* HTMX frontend
* Oracle Cloud deployment

Create:

```text
docs/
```

Include:

* Architecture diagrams
* ERD
* Sequence diagrams
* API documentation
* ADRs

Record a demo video.

Demonstrate:

```text
User Login

↓

Upload PDF

↓

Live Status Updates (SSE)

↓

Processing Complete

↓

Ask Question

↓

Semantic Search

↓

Two-Gate Filtering

↓

Local LLM

↓

Answer with Citation
```

Publish the project.

Verify:

* GitHub repository complete
* README polished
* Documentation complete
* Live deployment accessible
* Demo video linked

Reflect on the project.

Write the final development log.

Discuss:

* Challenges encountered
* Architecture decisions
* Performance observations
* Lessons learned
* Future improvements

---

# Week 6 Exit Criteria

By the end of Week 6, LexVault should be a complete, production-ready portfolio project with:

* Comprehensive automated tests
* Secure authentication
* Shared-schema multi-tenancy
* Tenant isolation verified
* Dockerized deployment
* GitHub Actions CI
* PostgreSQL + pgvector
* Redis + Celery
* Local embedding model (bge-small-en-v1.5)
* Local LLM (llama3.2:1b via Ollama)
* Two-Gate Adaptive Context Selection
* SSE live status updates
* HTMX frontend
* Oracle Cloud deployment
* HTTPS enabled
* Monitoring with Sentry and UptimeRobot
* Complete technical documentation
* ADRs
* Demo video
* Public GitHub repository ready for recruiters and technical interviews

**Project Complete.**
