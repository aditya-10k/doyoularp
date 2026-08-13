# System Architecture

## High-Level

Browser
  ↓
Next.js frontend
  ↓ HTTP
FastAPI backend
  ↓
Analysis pipeline
  ├── PDF parser
  ├── URL extractor
  ├── Resume claim extractor
  ├── GitHub collector
  ├── Web collector
  ├── Evidence normalizer
  ├── Retrieval layer
  ├── Evaluation agents
  └── Roast generator
  ↓
PostgreSQL + pgvector

## Core Principle

FastAPI is the orchestrator.

Do not turn FastAPI into a giant compute server.

Heavy inference should use external inference APIs where possible.

Do not download and run large embedding/LLM models inside the free backend container.

## Deterministic vs Agentic

Use deterministic code for:

- PDF parsing
- hyperlink extraction
- URL classification
- GitHub API calls
- HTTP fetching
- HTML parsing
- database writes
- data normalization
- score calculations that have explicit formulas

Use LLMs/agents for:

- semantic claim extraction
- deciding relevant evidence
- nuanced claim evaluation
- writing the roast
- summarizing evidence

## Agent Architecture

Optional supervisor:

Supervisor Agent
  ├── Claim Agent
  ├── Evidence Reasoning Agent
  ├── Evaluation Agent
  └── Roast Agent

Agents should receive structured evidence rather than raw internet access whenever possible.

## Analysis Pipeline

1. Create analysis
2. Upload PDF
3. Parse PDF
4. Extract hyperlinks
5. Extract visible URLs
6. Normalize URLs
7. Identify sources
8. Extract resume claims
9. Collect GitHub evidence
10. Collect public webpage evidence
11. Normalize evidence
12. Store evidence
13. Generate/retrieve embeddings
14. Retrieve relevant evidence per claim
15. Evaluate claims
16. Calculate LARP score
17. Generate roast
18. Create anonymous leaderboard entry
19. Mark analysis complete

## Async Processing

The upload endpoint must return quickly.

Long analysis should run in background processing.

Frontend can poll:

GET /api/v1/analyses/{analysis_id}

or use SSE/WebSocket later.

## Free-Tier Constraint

The backend should be lightweight.

Avoid:

- GPU workloads
- local LLM hosting
- local embedding models
- always-on browser automation
- unnecessary microservices

Prefer:

- external inference
- PostgreSQL/pgvector
- cached external data
- batched operations
- asynchronous work

## Security

No auth in MVP.

Still enforce:

- PDF size limits
- MIME/type validation
- request size limits
- URL allow/deny validation
- SSRF protection
- timeouts
- redirect limits
- rate limits where practical

Public URL fetching must NOT allow arbitrary access to private/internal network addresses.

Never expose API keys to the frontend.
