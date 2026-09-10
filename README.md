# doyoularp

Resume evidence-verification engine that performs evidence-backed sanity checks on software engineering resumes, cross-examines public GitHub receipts, extracts atomic claims, and calculates a deterministic LARP score with brutally honest roasts.

---

## Overview

doyoularp processes PDF resumes through a 13-stage verification pipeline:
1. **PDF Parsing**: Extracts text structure, layout, and embedded links.
2. **Link Extraction & Source Registration**: Discovers GitHub repositories, live demo URLs, and project links.
3. **Claim Decomposition**: Uses LLM agents to convert bullet points into atomic, testable engineering claims while strictly filtering out names, contact info, and education details.
4. **GitHub & Web Harvesting**: Fetches commit histories, repository statistics, dependency manifests, and language distribution via GitHub API with rate-limit protections.
5. **SSRF Protection**: Validates external links with private IP filtering and loopback defenses.
6. **Local Vector Search & Retrieval**: Indexes evidence chunks using lightweight n-gram hashing (<1MB RAM, 0 GPU) and retrieves relevant receipts.
7. **Strict Evaluation Hierarchy**: Cross-references claims against harvested code and dependencies to assign verdicts (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNVERIFIED`, `CONTRADICTED`).
8. **Deterministic LARP Score**: Computes an objective 0-100 score based on verification ratios, phantom claims, and actual repository commit activity.
9. **Slander & Roast Generation**: Formulates an evidence-grounded roast citing missing receipts and technical discrepancies.
10. **Global Leaderboard**: Tracks anonymous scores across all analyzed resumes.

---

## Architecture

- **Backend**: FastAPI (Python 3), SQLAlchemy 2.0 (async), asyncpg, Groq LLM (Qwen 2.5), OpenRouter, Google Gemini.
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, Lucide Icons, Framer Motion.
- **Database**: PostgreSQL (Neon.tech serverless) / SQLite for local testing.

---

## Getting Started

### Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows: venv\Scripts\activate | Unix: source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to interact with the application.

---

## Production Deployment

Refer to [DEPLOYMENT.md](DEPLOYMENT.md) for full zero-cost deployment instructions on Render, Vercel, and Neon.
