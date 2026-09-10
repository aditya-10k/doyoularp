# Free-Tier Production Deployment Guide

This guide covers deploying the DOYOULARP platform using 100% free software and hosting tiers without credit cards, without Docker Compose, and keeping memory compute strictly under 512MB RAM.

---

## Architecture Overview

1. **Database**: PostgreSQL on **Neon.tech** (Serverless free tier, 0.5 GB storage, zero cost, instant setup).
2. **Backend**: FastAPI Python service on **Render.com** (Free Web Service tier, 512MB RAM, automatic SSL).
3. **Frontend**: Next.js 14 on **Vercel** (Hobby free tier, edge CDN, automatic SSL).

---

## Step 1: Database Setup (Neon.tech)

1. Open [Neon.tech](https://neon.tech) and click **Sign Up** (authenticate with GitHub).
2. Click **Create Project**.
   - Project Name: `doyoularp-db`
   - Region: Select the region closest to your backend (e.g., `AWS US East (N. Virginia)` or `AWS Europe (Frankfurt)`).
3. Once created, look at the **Connection Details** dashboard panel:
   - Ensure the dropdown is set to **Postgres** (or **URI**).
   - Copy the connection string. It will look like:
     ```text
     postgresql://neondb_owner:password@ep-cool-snowflake-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
4. Save this connection string. You will provide it or set it as `DATABASE_URL` in the backend environment variables.

> Note: The backend includes automatic URL normalization in `backend/app/db/session.py` to automatically adapt `postgresql://` to `postgresql+asyncpg://` and map `sslmode=require` to `ssl=require`.

---

## Step 2: Backend Deployment (Render.com)

1. Open [Render.com](https://render.com) and log in with GitHub.
2. Click **New +** and select **Web Service**.
3. Select **Build and deploy from a Git repository** and connect your `doyoularp` repository.
4. Configure the Web Service settings:
   - **Name**: `doyoularp-backend`
   - **Region**: Same or nearest region to your database
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Select **Free** (512 MB RAM, 0.1 CPU)
5. Expand the **Environment Variables** section and paste the environment variables from the section below.
6. Click **Create Web Service**.
7. Render will build and deploy your backend, giving you a live public URL like:
   `https://doyoularp-backend.onrender.com`

---

## Step 3: Frontend Deployment (Vercel)

1. Open [Vercel.com](https://vercel.com) and log in with GitHub.
2. Click **Add New...** -> **Project**.
3. Import your `doyoularp` GitHub repository.
4. Configure Project Settings:
   - **Framework Preset**: Next.js
   - **Root Directory**: Click edit and select `frontend`
   - **Build Command**: `next build` (default)
   - **Output Directory**: `.next` (default)
5. Under **Environment Variables**, add:
   - Key: `NEXT_PUBLIC_API_URL`
   - Value: `https://doyoularp-backend.onrender.com` (replace with your Render backend URL)
6. Click **Deploy**.
7. In approximately 60 seconds, your frontend will be live on a `*.vercel.app` domain with automatic SSL.

---

## Step 4: Update CORS on Backend

After your Vercel frontend is deployed:
1. Copy your Vercel frontend domain (e.g., `https://doyoularp.vercel.app`).
2. Go to Render -> your `doyoularp-backend` Web Service -> **Environment**.
3. Set `FRONTEND_URL` to your Vercel domain:
   `FRONTEND_URL=https://doyoularp.vercel.app`
4. Render will automatically redeploy with the updated CORS policy.

---

## Production Backend Environment Variables (.env)

Below is the complete text to copy and paste into your hosting environment (e.g., Render Environment Variables or `.env`):

```env
APP_NAME=doyoularp
DEBUG=false
PORT=8000
HOST=0.0.0.0
FRONTEND_URL=http://localhost:3000

# Database Configuration (Neon PostgreSQL)
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-snowy-hill-b34gawb2.c-4.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require

# AI Provider: Groq
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=qwen/qwen3.8-27b

# External Data Sources
GITHUB_TOKEN=ghp_your_github_token_here

# Additional AI Providers (Fallback & Task Division)
OPENROUTER_API_KEY=sk-or-v1-your_openrouter_api_key_here
OPENROUTER_MODEL=nvidia/nemotron-3.5-lightning:free
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-flash-latest

# Roast Intensity: 0 (factual) to 4 (nuclear), default 3
ROAST_INTENSITY=3

# Limits & Memory Protection (Low-compute free tier)
MAX_PDF_SIZE_BYTES=10485760
REQUEST_TIMEOUT_SECONDS=15
MAX_CONCURRENT_GITHUB_REQS=5
```
