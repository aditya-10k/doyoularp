# LARP Checker — Project Overview

## What We Are Building

LARP Checker is a resume evidence-verification app.

A user uploads a resume PDF. The system extracts the candidate's claims and public links, gathers evidence from GitHub, portfolios, project websites and other public sources, then judges how well the public evidence supports the resume.

The personality of the product is intentionally informal, crude, sarcastic and condescending.

If a resume is clearly larping, the system should roast it.

This is a roast/evidence product, not a polite HR compliance dashboard.

## Core Philosophy

We are not declaring:

> "This candidate is a liar."

We are saying:

> "This claim is not supported by the evidence we found."

The UI and generated roast can be brutal, but the underlying evidence engine must remain factual.

Never invent evidence.

Never turn missing evidence into proof of fraud.

## Product Personality

The product should feel like:

- internet-native
- blunt
- funny
- sarcastic
- slightly unhinged
- technically competent
- condescending toward obvious resume bullshit

Avoid:

- corporate HR language
- generic AI-assistant personality
- excessive disclaimers
- fake professionalism
- boring "Thank you for using our platform" copy

Example tone:

"Bro put 'distributed systems' on the resume and GitHub has three React todo apps."

"Congratulations. You have successfully described a CRUD app as a scalable microservices platform."

"Your resume says ML Engineer. Your GitHub says CSS enthusiast."

Do not make jokes about protected traits or other sensitive personal characteristics.

## Home Screen

The user-provided/generated reference image is the visual direction for the home screen.

Use it as a design reference:

- black/dark background
- monochrome stone-warrior imagery
- serif display typography
- high contrast
- brutalist/editorial layout
- sparse red accents
- subtle grain/noise
- oversized typography
- dry, satirical copy

Do not replace the supplied visual direction with a generic SaaS dashboard.

## No Authentication

MVP has no user accounts and no login.

A user can:

1. upload a resume
2. run an analysis
3. receive a result
4. access the leaderboard from the generated result

Because there is no authentication, leaderboard identity must be anonymous.

Use generated aliases/handles rather than exposing candidate names by default.

## Main Flow

PDF
→ parse text + hyperlinks
→ discover URLs
→ extract resume claims
→ gather external evidence
→ normalize evidence
→ store evidence
→ retrieve evidence relevant to claims
→ evaluate claims
→ generate roast
→ generate anonymous leaderboard entry
→ show result

## MVP Stack

Frontend:
- Next.js
- React
- TypeScript

Backend:
- Python
- FastAPI

Database:
- PostgreSQL
- Supabase
- pgvector

External sources:
- GitHub REST API
- public HTTP webpages
- LLM/embedding APIs

Deployment target:
- free-tier infrastructure

## Build Order

Phase 1:
PDF parsing + link extraction + GitHub collection

Phase 2:
Web/project collection + PostgreSQL evidence model

Phase 3:
Resume claim extraction

Phase 4:
Retrieval/RAG

Phase 5:
Evaluation agents + roast generation

Phase 6:
Leaderboard + frontend polish

Phase 7:
Deployment
