# FastAPI Backend

## Framework

Python + FastAPI.

## Suggested Structure

backend/
  app/
    main.py
    api/
      routes/
    agents/
    collectors/
    parsers/
    services/
    models/
    schemas/
    db/
    core/
    utils/
  tests/

## Responsibilities

### API Routes

Only handle:
- request validation
- authentication if introduced later
- calling services
- response serialization

Do not place complex business logic inside routes.

### Services

Coordinate the application.

Examples:

AnalysisService
ResumeService
EvidenceService
LeaderboardService

### Collectors

External data acquisition.

GitHubCollector
WebCollector

### Parsers

Transform external/raw data.

ResumeParser
GitHubParser
HTMLParser

### Agents

Reason over structured information.

## API

POST /api/v1/analyses

Creates analysis.

POST /api/v1/analyses/{analysis_id}/resume

Uploads resume PDF.

GET /api/v1/analyses/{analysis_id}

Returns status.

GET /api/v1/analyses/{analysis_id}/claims

Returns claims and evaluations.

GET /api/v1/analyses/{analysis_id}/evidence

Returns evidence.

GET /api/v1/analyses/{analysis_id}/result

Returns completed result.

GET /api/v1/analyses/{analysis_id}/leaderboard

Returns leaderboard context for the generated result.

## Example Analysis Status

{
  "analysis_id": "...",
  "status": "running",
  "stage": "github_collection",
  "progress": 45
}

Stages:

created
parsing_resume
extracting_links
extracting_claims
collecting_github
collecting_web
normalizing_evidence
retrieving_evidence
evaluating_claims
generating_roast
finalizing
completed
failed

## Environment Variables

DATABASE_URL
GITHUB_TOKEN
LLM_API_KEY
EMBEDDING_API_KEY
FRONTEND_URL

Never hardcode credentials.

## Error Handling

External failures should be isolated.

A failed GitHub repository must not kill the entire candidate analysis.

Return useful error metadata.

## Rate Limiting

Protect public endpoints.

At minimum:
- upload rate limit
- analysis creation rate limit
- result endpoint protection

This matters because the MVP has no auth.

## Background Jobs

Use a lightweight background job approach initially.

If the free deployment environment cannot reliably run long background tasks, introduce a persistent job mechanism rather than holding the request open.

Do not prematurely introduce Redis/Celery unless the deployment actually requires it.
