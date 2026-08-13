# Initial Vibe-Coding Prompt

Read every file in `/docs` before writing code.

You are building LARP Checker exactly as described in those documents.

The product personality is intentionally informal, crude, sarcastic and condescending toward obvious resume larp.

The underlying evidence engine must remain factual.

Do NOT implement the entire application in one pass.

## Phase 1 Only

Implement:

1. FastAPI backend setup
2. Project structure
3. PDF upload
4. PDF text extraction
5. Embedded PDF hyperlink extraction
6. Visible URL extraction
7. URL normalization
8. URL classification
9. GitHub profile/repository URL detection
10. GitHub collector
11. PostgreSQL models for:
   - candidates
   - analyses
   - resumes
   - sources
   - repositories
   - commits
   - repository_languages
   - contributors
12. Basic analysis status endpoint
13. Tests for:
   - PDF link extraction
   - URL normalization
   - GitHub URL detection
   - GitHub response parsing

## Do NOT implement yet

- RAG internals
- embeddings
- vector retrieval
- evaluation agents
- roast agent
- LinkedIn scraping
- browser automation
- leaderboard UI
- authentication
- complex queue infrastructure

Create clean interfaces/placeholders for future components where needed.

## GitHub

Use the GitHub REST API.

Use a server-side GitHub token through environment variables.

Never expose the token to the frontend.

Implement:
- pagination
- bounded concurrency
- retries
- sensible caching
- rate-limit handling

Do not download entire repositories.

Prioritize README, dependency manifests, config files and metadata.

## PDF

The parser MUST inspect embedded hyperlink annotations.

A resume showing only the word "GitHub" may still contain an embedded GitHub URL.

## Security

Validate uploaded files.

Implement reasonable PDF size limits.

When web fetching is added later, SSRF protections will be mandatory.

## Output

When Phase 1 is complete, report:

1. What you built
2. Project structure
3. How PDF hyperlink extraction works
4. How GitHub collection works
5. Database schema
6. Environment variables required
7. How to run locally
8. Tests written and their results
9. Known limitations
10. What Phase 2 should implement

Then stop.
