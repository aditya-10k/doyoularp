import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.agents.claim_extractor import ClaimExtractor, is_excluded_claim
from backend.app.agents.evaluation_agent import EvaluationAgent
from backend.app.agents.groq_client import GroqRateLimitError
from backend.app.agents.larp_calculator import calculate_larp_score
from backend.app.agents.roast_agent import RoastAgent
from backend.app.collectors.github_collector import GitHubCollector
from backend.app.collectors.web_collector import WebCollector
from backend.app.core.config import settings
from backend.app.models.models import (
    Analysis,
    Candidate,
    Claim,
    Commit,
    Contributor,
    Embedding,
    Evaluation,
    Evidence,
    LeaderboardEntry,
    Repository,
    RepositoryLanguage,
    Resume,
    Source,
)
from backend.app.parsers.pdf_parser import parse_pdf_bytes
from backend.app.rag.embedding_service import EmbeddingService
from backend.app.rag.evidence_retriever import EvidenceRetriever
from backend.app.rag.vector_store import InMemoryVectorStore

logger = logging.getLogger(__name__)

ANONYMOUS_ALIASES = [
    "Microservice Messiah",
    "K8s Alchemist",
    "Full-Stack Illusionist",
    "Docker Druid",
    "Distributed Shaman",
    "Regex Sorcerer",
    "Senior Todo Architect",
    "CSS Warlock",
    "Prompt Whisperer",
    "Cloud Conductor",
    "Big-O Fantasist",
    "GraphQL Prophet",
]

DEROGATORY_VERSIONS_LIST = [
    "Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you.",
    "Submitting a software resume without GitHub is like applying to be an airline pilot by showing a picture of a bird.",
    "You spent more time selecting fonts on this PDF than writing actual code. Cancel the interviews and go become an influencer.",
    "If your code is operating in stealth mode, your job search should be operating in stealth mode as well.",
    "What was the master strategy? Hope the interviewer doesn't know what a version control system is?",
]

DEROGATORY_NO_GITHUB_ROASTS = [
    (
        "No GitHub link found anywhere in this resume. Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you.\n\n"
        "You had the audacity to submit a technical engineering resume loaded with project claims, architectural buzzwords, and claimed proficiencies, yet you could not produce a single public GitHub link, repository, or commit receipt. "
        "In an industry where the only real proof of competence is running code, you decided that your word alone was worth six figures.\n\n"
        "There are no commit timestamps. There are no pull requests. There are no Docker containers. There is only a PDF document constructed from pure LinkedIn fiction and wishful thinking. "
        "If you want to be taken seriously as an engineer, publish your code. Until then, you are simply roleplaying in a developer costume."
    ),
    (
        "No GitHub link found in this resume. Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you.\n\n"
        "Submitting a software engineering resume without a GitHub profile is the technical equivalent of applying to be an airline pilot by showing a picture of a bird. "
        "You expect hiring managers to take your claims of 'spearheading distributed architectures' and 'optimizing mission-critical databases' on blind faith while you hide in the witness protection program of software development.\n\n"
        "Zero repositories. Zero commit history. Zero public code provenance. You brought a beautifully typeset piece of fiction to a technical audit. "
        "Either publish the receipts or pivot to lifestyle content creation full-time."
    ),
    (
        "No GitHub link found. Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you.\n\n"
        "You spent more time selecting fonts, aligning margins, and agonizing over bullet point spacing on this PDF than you have ever spent writing production code. "
        "You claim proficiency in entire technology stacks, yet you couldn't even manage to paste a single GitHub URL onto the page. "
        "What was the master strategy here? Hope the interviewer doesn't know what a version control system is?\n\n"
        "In a field defined strictly by what you build and ship, you brought pure vaporware. "
        "Cancel the upcoming interviews, close your code editor, and re-evaluate your life choices."
    ),
    (
        "No GitHub link found. Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you.\n\n"
        "You threw around terms like 'scalable microservices', 'event-driven pipelines', and 'full-stack engineering', yet you failed to provide even the most elementary proof of existence. "
        "A developer without a GitHub presence in 2026 is indistinguishable from an AI chatbot hallucinating a career into a resume generator.\n\n"
        "You have zero public code, zero receipts, and zero grounds to claim software competence. "
        "If your code is operating in stealth mode, your job search should be operating in stealth mode as well."
    ),
    (
        "No GitHub link found anywhere on this document. Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you.\n\n"
        "Did you genuinely believe that reciting three years of tech Twitter buzzwords on a PDF would substitute for actual public repositories? "
        "You are asking someone to hire an engineer who apparently writes code exclusively on confidential napkins or in alternate dimensions.\n\n"
        "There is nothing to audit because there is nothing here. No code, no commits, no proof. "
        "Take this resume, throw it in the recycling bin, and go learn git."
    ),
]


class PipelineService:
    def __init__(
        self,
        embedder: Optional[EmbeddingService] = None,
        vector_store: Optional[InMemoryVectorStore] = None,
    ):
        self.embedder = embedder or EmbeddingService()
        self.vector_store = vector_store or InMemoryVectorStore()
        self.retriever = EvidenceRetriever(self.embedder, self.vector_store)
        self.claim_extractor = ClaimExtractor()
        self.evaluation_agent = EvaluationAgent()
        self.roast_agent = RoastAgent()
        self.github_collector = GitHubCollector()
        self.web_collector = WebCollector()

    def generate_alias(self, custom_alias: Optional[str] = None) -> str:
        if custom_alias and custom_alias.strip():
            return custom_alias.strip()
        prefix = random.choice(ANONYMOUS_ALIASES)
        suffix = random.randint(100, 999)
        return f"{prefix} #{suffix}"

    async def create_analysis(self, db: AsyncSession, alias: Optional[str] = None) -> Analysis:
        candidate_alias = self.generate_alias(alias)
        candidate = Candidate(anonymous_alias=candidate_alias)
        db.add(candidate)
        await db.flush()

        analysis = Analysis(
            candidate_id=candidate.id,
            status="created",
            stage="created",
            progress=0,
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis

    async def run_pipeline(self, analysis_id: str, filename: str, pdf_bytes: bytes, db: AsyncSession) -> None:
        """Full end-to-end processing pipeline across all 13 stages."""
        analysis = await db.get(Analysis, analysis_id)
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found.")
            return

        try:
            # 1. Parsing Resume
            analysis.status = "running"
            analysis.stage = "parsing_resume"
            analysis.progress = 10
            await db.commit()

            parsed_pdf = parse_pdf_bytes(pdf_bytes)

            resume = Resume(
                candidate_id=analysis.candidate_id,
                analysis_id=analysis.id,
                filename=filename,
                raw_text=parsed_pdf.raw_text,
                page_count=parsed_pdf.page_count,
            )
            db.add(resume)
            await db.flush()

            # 2. Extracting Links & Registering Sources
            analysis.stage = "extracting_links"
            analysis.progress = 20
            await db.commit()

            discovered_sources: List[Source] = []
            for item in parsed_pdf.discovered_urls:
                src = Source(
                    candidate_id=analysis.candidate_id,
                    analysis_id=analysis.id,
                    type=item.get("category", "other"),
                    url=item.get("url"),
                    status="pending",
                    meta=item,
                )
                db.add(src)
                discovered_sources.append(src)
            await db.flush()

            # Fast abort if no GitHub link is found: do not go through the entire pipeline
            has_github = (
                any(s.type == "github" for s in discovered_sources)
                or ("github.com" in (parsed_pdf.raw_text or "").lower())
            )

            if not has_github:
                logger.info(
                    f"Analysis {analysis.id}: No GitHub link discovered in resume. "
                    "Aborting pipeline immediately with maximum LARP verdict."
                )

                selected_roast = random.choice(DEROGATORY_NO_GITHUB_ROASTS)
                verdict_summary = (
                    "FATAL PHANTOM DETECTED: Zero GitHub link or code provenance found in resume. "
                    "Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you. 100% unverified buzzword fiction."
                )
                funny_mismatch = "No GitHub link found: Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you."
                weakest_claim = "Zero GitHub profile or repository links provided in resume"

                # Add an explicit contradicted claim so the evidence inspection UI details the violation
                claim_obj = Claim(
                    analysis_id=analysis.id,
                    resume_id=resume.id,
                    claim_text="Verifiable public GitHub repository code provenance",
                    category="provenance",
                    section="links",
                    source_text="Candidate provided zero GitHub profile or repository URLs across the entire resume.",
                    meta={"technologies": [], "project_name": "GitHub Provenance"},
                )
                db.add(claim_obj)
                await db.flush()

                eval_record = Evaluation(
                    claim_id=claim_obj.id,
                    verdict="CONTRADICTED",
                    confidence=1.0,
                    reasoning="Technical engineering resume submitted without linking a GitHub profile or public code repositories. Provenance completely contradicted.",
                )
                db.add(eval_record)

                candidate = await db.get(Candidate, analysis.candidate_id)
                alias_name = candidate.anonymous_alias if candidate else "Anonymous Candidate"

                summary_payload = json.dumps({
                    "verdict_summary": verdict_summary,
                    "funny_mismatch": funny_mismatch,
                    "weakest_claim": weakest_claim,
                    "derogatory_versions": DEROGATORY_VERSIONS_LIST,
                })

                stmt_existing = select(LeaderboardEntry).where(LeaderboardEntry.analysis_id == analysis.id)
                existing_res = await db.execute(stmt_existing)
                existing_entry = existing_res.scalar_one_or_none()

                if existing_entry:
                    existing_entry.larp_score = 100.0
                    existing_entry.roast = selected_roast
                    existing_entry.summary = summary_payload
                else:
                    leaderboard_entry = LeaderboardEntry(
                        analysis_id=analysis.id,
                        anonymous_alias=alias_name,
                        larp_score=100.0,
                        roast=selected_roast,
                        summary=summary_payload,
                        token=str(uuid.uuid4()).replace("-", ""),
                    )
                    db.add(leaderboard_entry)

                analysis.status = "completed"
                analysis.stage = "completed"
                analysis.progress = 100
                analysis.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # 3. Extracting Resume Claims
            analysis.stage = "extracting_claims"
            analysis.progress = 35
            await db.commit()

            extracted_claims = await self.claim_extractor.extract_claims(
                parsed_pdf.raw_text,
                discovered_urls=[s.url for s in discovered_sources if s.url]
            )
            claim_records: List[Claim] = []
            for c in extracted_claims:
                claim_text = c.get("claim_text", "")
                cat = c.get("category", "project")
                sec = c.get("section", "experience")

                # Strictly exclude candidate name, phone number, and education claims
                if is_excluded_claim(claim_text, cat, sec):
                    continue

                claim_obj = Claim(
                    analysis_id=analysis.id,
                    resume_id=resume.id,
                    claim_text=claim_text,
                    category=cat,
                    section=sec,
                    source_text=c.get("source_text", ""),
                    meta={
                        "technologies": c.get("technologies", []),
                        "project_name": c.get("project_name"),
                        "attached_url": c.get("attached_url"),
                    },
                )
                db.add(claim_obj)
                claim_records.append(claim_obj)
            await db.flush()

            # 4. Collecting GitHub Evidence
            analysis.stage = "collecting_github"
            analysis.progress = 50
            await db.commit()

            collected_repos_data: List[Dict[str, Any]] = []
            processed_usernames: Set[str] = set()
            collected_repo_keys: Set[str] = set()

            # Detect candidate primary GitHub username
            candidate_gh_user: Optional[str] = None
            for src in discovered_sources:
                if src.type == "github":
                    gh_info = src.meta.get("github_info") if src.meta else None
                    if gh_info and gh_info.get("type") == "github_profile":
                        candidate_gh_user = gh_info.get("username")
                        break
            if not candidate_gh_user:
                for src in discovered_sources:
                    if src.type == "github":
                        gh_info = src.meta.get("github_info") if src.meta else None
                        if gh_info and gh_info.get("username"):
                            candidate_gh_user = gh_info.get("username")
                            break

            for src in discovered_sources:
                if src.type == "github":
                    gh_info = src.meta.get("github_info") if src.meta else None
                    username = gh_info.get("username") if gh_info else None
                    repo_hint = gh_info.get("repo") if gh_info else None

                    # If specific repository is linked, collect that exact repo with authorship check
                    if username and repo_hint:
                        clean_repo = repo_hint.replace(".git", "").strip()
                        repo_key = f"{username.lower()}/{clean_repo.lower()}"
                        if repo_key not in collected_repo_keys:
                            single_r = await self.github_collector.collect_single_repo(
                                username, clean_repo, candidate_username=candidate_gh_user
                            )
                            if single_r:
                                collected_repo_keys.add(repo_key)
                                collected_repos_data.append(single_r)
                                src.status = "collected"

                    # ONLY crawl all repos for candidate's own primary profile, NOT collaborator profiles
                    if username and username not in processed_usernames:
                        processed_usernames.add(username)
                        if not candidate_gh_user or username.lower() == candidate_gh_user.lower():
                            gh_data = await self.github_collector.collect_candidate_github(username)
                            if gh_data and gh_data.get("repos"):
                                src.status = "collected"
                                for r in gh_data.get("repos", []):
                                    r_key = f"{(r.get('owner') or username).lower()}/{(r.get('name') or '').lower()}"
                                    if r_key not in collected_repo_keys:
                                        collected_repo_keys.add(r_key)
                                        collected_repos_data.append(r)

            # Persist collected repositories and evidence records
            for r in collected_repos_data:
                repo_obj = Repository(
                    analysis_id=analysis.id,
                    candidate_id=analysis.candidate_id,
                    github_source_id=discovered_sources[0].id if discovered_sources else None,
                    name=r.get("name"),
                    owner=r.get("owner"),
                    url=r.get("url"),
                    description=r.get("description"),
                    stars=r.get("stars", 0),
                    forks=r.get("forks", 0),
                    meta={"languages": r.get("languages", {})},
                )
                db.add(repo_obj)
                await db.flush()

                # Create Evidence record for README
                if r.get("readme"):
                    readme_ev = Evidence(
                        analysis_id=analysis.id,
                        candidate_id=analysis.candidate_id,
                        source_id=discovered_sources[0].id if discovered_sources else None,
                        evidence_type="readme",
                        title=f"{r.get('name')} README",
                        content=f"Repository {r.get('name')} Documentation:\n\n{r.get('readme')}",
                        url=r.get("url"),
                        meta={"repo": r.get("name")},
                    )
                    db.add(readme_ev)

                # Create Evidence records for Manifests with extracted dependencies
                for m_name, m_info in r.get("manifests", {}).items():
                    if isinstance(m_info, dict):
                        m_content = m_info.get("content", "")
                        m_meta = m_info.get("meta", {})
                        summary_str = m_meta.get("summary", "")
                    else:
                        m_content = str(m_info)
                        m_meta = {}
                        summary_str = ""

                    manifest_ev = Evidence(
                        analysis_id=analysis.id,
                        candidate_id=analysis.candidate_id,
                        source_id=discovered_sources[0].id if discovered_sources else None,
                        evidence_type="github_manifest",
                        title=f"{r.get('name')} {m_name}",
                        content=f"Project: {r.get('name')}\nManifest: {m_name}\nVerification Summary: {summary_str}\n\n{m_content}",
                        url=r.get("url"),
                        meta={"repo": r.get("name"), "manifest": m_name, "parsed": m_meta},
                    )
                    db.add(manifest_ev)

                # Summary evidence of repository activity
                repo_summary_ev = Evidence(
                    analysis_id=analysis.id,
                    candidate_id=analysis.candidate_id,
                    source_id=discovered_sources[0].id if discovered_sources else None,
                    evidence_type="github_repo",
                    title=f"Repository {r.get('name')}",
                    content=(
                        f"Repo: {r.get('name')}. Description: {r.get('description')}. "
                        f"Languages: {list(r.get('languages', {}).keys())}. "
                        f"Publicly verified GitHub repository with candidate attribution."
                    ),
                    url=r.get("url"),
                    meta={
                        "repo": r.get("name"),
                        "candidate_commit_count": r.get("candidate_commit_count", 5),
                        "total_commit_count": r.get("total_commit_count", 5),
                    },
                )
                db.add(repo_summary_ev)
            # Aggregate candidate-wide verified tech stack inventory
            if collected_repos_data:
                all_languages: Set[str] = set()
                all_manifest_packages: Set[str] = set()
                all_infra_services: Set[str] = set()
                repo_tech_breakdown = []
                tech_repo_map: Dict[str, Set[str]] = {}
                tech_commits_map: Dict[str, int] = {}
                verified_repo_count = 0

                for r in collected_repos_data:
                    # STRICT PROVENANCE: Only count repos owned by candidate OR where candidate authored commits!
                    r_owner = (r.get("owner") or "").lower()
                    cand_user = (candidate_gh_user or "").lower()
                    cand_commits = r.get("candidate_commit_count", 0)
                    if cand_user and r_owner != cand_user and cand_commits == 0:
                        continue

                    verified_repo_count += 1
                    r_name = r.get("name", "repo")
                    langs = [k for k in r.get("languages", {}).keys() if k]
                    all_languages.update(langs)
                    r_techs = list(langs)

                    for l_item in langs:
                        l_clean = l_item.lower()
                        tech_repo_map.setdefault(l_clean, set()).add(r_name)
                        tech_commits_map[l_clean] = tech_commits_map.get(l_clean, 0) + max(1, cand_commits)

                    manifests = r.get("manifests", {})
                    for m_path, m_val in manifests.items():
                        if isinstance(m_val, dict):
                            meta = m_val.get("meta", {})
                            deps = meta.get("dependencies", [])
                            if isinstance(deps, list):
                                all_manifest_packages.update(deps[:50])
                                r_techs.extend(deps[:8])
                                for d in deps[:50]:
                                    d_clean = str(d).lower()
                                    tech_repo_map.setdefault(d_clean, set()).add(r_name)
                                    tech_commits_map[d_clean] = tech_commits_map.get(d_clean, 0) + max(1, cand_commits)

                            services = meta.get("detected_services", [])
                            if isinstance(services, list):
                                all_infra_services.update(services)
                                r_techs.extend(services)
                                for s in services:
                                    s_clean = str(s).lower()
                                    tech_repo_map.setdefault(s_clean, set()).add(r_name)

                            base_imgs = meta.get("base_images", [])
                            if isinstance(base_imgs, list):
                                all_infra_services.update(base_imgs)
                                r_techs.extend(base_imgs)
                            comp_services = meta.get("services", [])
                            if isinstance(comp_services, list):
                                all_infra_services.update(comp_services)
                                r_techs.extend(comp_services)

                    repo_tech_breakdown.append(f"- {r_name} ({cand_commits} candidate commits): {', '.join(filter(None, r_techs[:15]))}")

                # Build explicit occurrence breakdown
                frequent_tech = [
                    f"{k} ({len(v)} repos, {tech_commits_map.get(k, 0)} commits)"
                    for k, v in tech_repo_map.items() if len(v) >= 2 or tech_commits_map.get(k, 0) >= 10
                ]
                single_match_tech = [
                    f"{k} (1 repo: {next(iter(v))})"
                    for k, v in tech_repo_map.items() if len(v) == 1 and tech_commits_map.get(k, 0) < 10
                ]

                inventory_content = (
                    f"Consolidated Candidate Tech Stack Inventory across {verified_repo_count} verified repositories:\n"
                    f"Verified Languages: {', '.join(sorted(all_languages)) or 'None detected'}\n"
                    f"Multi-Project / Proficient Technologies (>=2 repos or >=10 commits): {', '.join(sorted(frequent_tech)[:40]) or 'None'}\n"
                    f"Single-Match / Incidental Technologies (1 repo only): {', '.join(sorted(single_match_tech)[:40]) or 'None'}\n\n"
                    f"Repository Breakdown:\n" + "\n".join(repo_tech_breakdown)
                )

                tech_stack_ev = Evidence(
                    analysis_id=analysis.id,
                    candidate_id=analysis.candidate_id,
                    source_id=discovered_sources[0].id if discovered_sources else None,
                    evidence_type="github_tech_stack",
                    title="Candidate Verified Tech Stack Inventory",
                    content=inventory_content,
                    url=discovered_sources[0].url if discovered_sources else None,
                    meta={
                        "languages": list(all_languages),
                        "packages_sample": list(all_manifest_packages)[:50],
                        "services": list(all_infra_services),
                        "repo_count": verified_repo_count,
                        "tech_repo_counts": {k: len(v) for k, v in tech_repo_map.items()},
                        "tech_commits": tech_commits_map,
                    },
                )
                db.add(tech_stack_ev)

            await db.flush()

            # 5. Collecting Webpage Evidence
            analysis.stage = "collecting_web"
            analysis.progress = 65
            await db.commit()

            web_sources = [
                s for s in discovered_sources
                if s.type in ("portfolio", "project", "other", "webpage") and not (s.url or "").startswith("mailto:")
            ]

            if web_sources:
                async def fetch_web_item(s: Source):
                    data = await self.web_collector.fetch_page(s.url)
                    return s, data

                web_results = await asyncio.gather(*(fetch_web_item(s) for s in web_sources), return_exceptions=True)
                for item in web_results:
                    if isinstance(item, tuple):
                        src, page_data = item
                        if page_data and page_data.get("status") == "collected" and page_data.get("content"):
                            src.status = "collected"
                            web_ev = Evidence(
                                analysis_id=analysis.id,
                                candidate_id=analysis.candidate_id,
                                source_id=src.id,
                                evidence_type="web_page",
                                title=page_data.get("title") or "Project Page",
                                content=page_data.get("content"),
                                url=src.url,
                                meta={"headings": page_data.get("headings", [])},
                            )
                            db.add(web_ev)
                        else:
                            src.status = page_data.get("status", "failed") if isinstance(page_data, dict) else "failed"

            await db.flush()

            # 6. Normalizing Evidence & RAG Indexing
            analysis.stage = "normalizing_evidence"
            analysis.progress = 75
            await db.commit()

            # Load all evidence records for this analysis
            stmt = select(Evidence).where(Evidence.analysis_id == analysis.id)
            ev_result = await db.execute(stmt)
            all_evidence = list(ev_result.scalars().all())

            analysis.stage = "retrieving_evidence"
            analysis.progress = 80
            await db.commit()

            for ev in all_evidence:
                await self.retriever.index_evidence(
                    evidence_id=ev.id,
                    analysis_id=analysis.id,
                    title=ev.title,
                    content=ev.content,
                    url=ev.url or "",
                    evidence_type=ev.evidence_type,
                    meta=ev.meta or {},
                )

                # Persist embedding vector representation
                vector = self.embedder.embed_text(f"{ev.title}\n{ev.content}")
                emb_record = Embedding(evidence_id=ev.id, vector_data=vector)
                db.add(emb_record)

            await db.flush()

            # 7. Evaluating Claims with RAG
            analysis.stage = "evaluating_claims"
            analysis.progress = 85
            await db.commit()

            # Retrieve evidence chunks for each claim locally (fast in-memory)
            claims_with_chunks = []
            for c in claim_records:
                chunks = await self.retriever.retrieve_for_claim(
                    claim_text=c.claim_text,
                    analysis_id=analysis.id,
                    top_k=4,
                    claim_meta=c.meta,
                )
                claims_with_chunks.append((c, chunks))

            analysis.progress = 90
            await db.commit()

            # Fast batch evaluation: skills evaluated deterministically in 0ms, projects in at most 1 single call
            eval_outcomes = await self.evaluation_agent.evaluate_claims_batch(claims_with_chunks)

            eval_results_for_scoring: List[Dict[str, Any]] = []

            for item in eval_outcomes:
                if isinstance(item, Exception):
                    logger.error(f"Error evaluating claim: {item}")
                    continue
                claim, eval_data = item

                eval_record = Evaluation(
                    claim_id=claim.id,
                    verdict=eval_data.get("verdict", "UNVERIFIED"),
                    confidence=eval_data.get("confidence", 0.5),
                    reasoning=eval_data.get("reasoning", ""),
                )
                db.add(eval_record)
                await db.flush()

                # Associate referenced evidence directly in the join table
                for ev_id in eval_data.get("evidence_ids", []):
                    ev_match = next((e for e in all_evidence if e.id == ev_id), None)
                    if ev_match:
                        from backend.app.models.models import evaluation_evidence
                        await db.execute(
                            evaluation_evidence.insert().values(
                                evaluation_id=eval_record.id,
                                evidence_id=ev_match.id,
                            )
                        )

                eval_results_for_scoring.append({
                    "claim_text": claim.claim_text,
                    "verdict": eval_data.get("verdict"),
                    "reasoning": eval_data.get("reasoning"),
                })

            await db.flush()

            # 8. Calculating LARP Score & Generating Roast
            analysis.stage = "generating_roast"
            analysis.progress = 95
            await db.commit()

            has_github_source = any(s.type == "github" for s in discovered_sources)

            score_data = calculate_larp_score(
                eval_results_for_scoring,
                collected_repos_data,
                has_github=has_github_source,
            )
            larp_score = score_data["larp_score"]

            roast_data = await self.roast_agent.generate_roast(
                larp_score=larp_score,
                evaluations=eval_results_for_scoring,
                repos=collected_repos_data,
                intensity=settings.ROAST_INTENSITY,
                has_github=has_github_source,
            )

            candidate = await db.get(Candidate, analysis.candidate_id)
            alias_name = candidate.anonymous_alias if candidate else "Anonymous Candidate"

            summary_payload = json.dumps({
                "verdict_summary": roast_data.get("verdict_summary"),
                "funny_mismatch": roast_data.get("funny_mismatch"),
                "weakest_claim": roast_data.get("weakest_claim"),
            })

            # Check if leaderboard entry already exists
            stmt_existing = select(LeaderboardEntry).where(LeaderboardEntry.analysis_id == analysis.id)
            existing_res = await db.execute(stmt_existing)
            existing_entry = existing_res.scalar_one_or_none()

            if existing_entry:
                existing_entry.larp_score = larp_score
                existing_entry.roast = roast_data.get("overall_roast", "No roast available.")
                existing_entry.summary = summary_payload
            else:
                leaderboard_entry = LeaderboardEntry(
                    analysis_id=analysis.id,
                    anonymous_alias=alias_name,
                    larp_score=larp_score,
                    roast=roast_data.get("overall_roast", "No roast available."),
                    summary=summary_payload,
                    token=str(uuid.uuid4()).replace("-", ""),
                )
                db.add(leaderboard_entry)

            # 9. Mark Complete
            analysis.status = "completed"
            analysis.stage = "completed"
            analysis.progress = 100
            analysis.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Free memory: prune transient in-memory vectors for this analysis
            if hasattr(self.vector_store, "clear_analysis"):
                self.vector_store.clear_analysis(analysis.id)

            logger.info(f"Analysis {analysis.id} completed successfully. LARP Score: {larp_score}")

        except GroqRateLimitError as e:
            logger.error(f"Analysis {analysis_id} halted due to Groq rate limit: {e}")
            await db.rollback()
            try:
                analysis = await db.get(Analysis, analysis_id)
                if analysis:
                    analysis.status = "failed"
                    analysis.stage = "failed"
                    analysis.error = "Analysis halted: LLM provider rate limit reached (Groq 429). Please wait a few minutes before retrying."
                    await db.commit()
            except Exception:
                pass
        except Exception as e:
            logger.exception(f"Analysis {analysis_id} failed with error: {e}")
            await db.rollback()
            try:
                analysis = await db.get(Analysis, analysis_id)
                if analysis:
                    analysis.status = "failed"
                    analysis.stage = "failed"
                    analysis.error = str(e)
                    await db.commit()
            except Exception:
                pass
