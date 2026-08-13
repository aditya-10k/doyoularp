# Development Rules

## Rule 1 — Read the docs first

Before coding, read every file in /docs.

Do not invent a different architecture because another stack feels easier.

## Rule 2 — Build in phases

Do not implement the whole product in one giant pass.

## Rule 3 — No fake production behavior

Do not make mock data look real.

If something is mocked, clearly label it.

## Rule 4 — No hardcoded secrets

Use environment variables.

## Rule 5 — Deterministic first

Use normal functions/services for deterministic operations.

Do not create an agent to:
- call GitHub
- parse PDFs
- extract URLs
- fetch webpages
- write database rows

## Rule 6 — Evidence always has provenance

Every evidence item must have:
- source
- URL when applicable
- extraction timestamp

## Rule 7 — Evaluation always has evidence

An evaluation without evidence cannot be confidently positive.

## Rule 8 — Missing ≠ false

If evidence is unavailable:
UNVERIFIED

Only use CONTRADICTED when evidence actually conflicts.

## Rule 9 — Don't scrape LinkedIn in MVP

Do not build a LinkedIn scraper.

## Rule 10 — Don't use browser automation in MVP

Use normal HTTP fetching first.

## Rule 11 — Don't run local large models

Free-tier deployment is a hard requirement.

Use external inference where necessary.

## Rule 12 — Don't overengineer infrastructure

Do not introduce Redis, Celery, Kubernetes, queues, microservices, etc. unless the actual workload requires them.

## Rule 13 — Security matters even without auth

Protect against:
- SSRF
- malicious PDFs
- oversized uploads
- abusive API usage
- leaked secrets

## Rule 14 — No public candidate PII

Leaderboard uses anonymous aliases.

## Rule 15 — Roast the resume, not the person

The system can be cruel about:
- inflated claims
- weak projects
- contradictory evidence
- obvious buzzword stuffing

It must not attack:
- race
- religion
- gender
- sexuality
- disability
- health
- appearance
- other protected/sensitive traits

## Rule 16 — Roast intensity

Default to brutal but evidence-based.

Do not manufacture a roast just because the user expects one.

If the resume is genuinely solid, say so.

Example:
"Annoyingly, this one checks out."

## Rule 17 — Tests

At minimum test:

- PDF text extraction
- PDF hyperlink extraction
- URL normalization
- GitHub URL classification
- GitHub API parsing
- contributor handling
- evidence normalization
- claim schema validation
- verdict logic

## Rule 18 — Stop after milestones

After each phase:
- run tests
- explain what changed
- explain how to run it
- list known limitations

Then wait for the next instruction.

## Rule 19 — Keep APIs provider-agnostic

Wrap:
- LLM
- embeddings
- GitHub
- web fetching

behind interfaces where reasonable.

## Rule 20 — Don't hide complexity

When an implementation involves a non-obvious decision, document it.

The goal is to build something the project owner can understand and extend, not a black box.
