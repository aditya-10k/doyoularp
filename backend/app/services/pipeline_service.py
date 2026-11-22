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
from backend.app.agents.groq_client import GroqClient, GroqRateLimitError
from backend.app.agents.larp_calculator import calculate_larp_score
from backend.app.agents.roast_agent import RoastAgent
from backend.app.collectors.competitive_collector import CompetitiveCollector
from backend.app.collectors.github_collector import GitHubCollector
from backend.app.collectors.linkedin_collector import LinkedInCollector
from backend.app.collectors.web_collector import WebCollector
from backend.app.core.config import settings
from backend.app.utils.sanitizer import sanitize_null_bytes
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
        self.competitive_collector = CompetitiveCollector()
        self.linkedin_collector = LinkedInCollector()

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

    async def run_pipeline(
        self,
        analysis_id: str,
        filename: str,
        pdf_bytes: bytes,
        db: AsyncSession,
        user_api_key: Optional[str] = None,
        user_provider: Optional[str] = None,
        user_keys: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Full end-to-end processing pipeline across all 13 stages."""
        analysis = await db.get(Analysis, analysis_id)
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found.")
            return

        claim_extractor = self.claim_extractor
        evaluation_agent = self.evaluation_agent
        roast_agent = self.roast_agent

        if (user_keys and len(user_keys) > 0) or (user_api_key and user_api_key.strip()):
            logger.info("Configuring analysis with user-provided API keys...")
            custom_groq = GroqClient(
                user_api_key=user_api_key.strip() if user_api_key else None,
                user_provider=user_provider,
                user_keys=user_keys,
            )
            claim_extractor = ClaimExtractor(groq_client=custom_groq)
            evaluation_agent = EvaluationAgent(groq_client=custom_groq)
            roast_agent = RoastAgent(groq_client=custom_groq)

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
                filename=sanitize_null_bytes(filename),
                raw_text=sanitize_null_bytes(parsed_pdf.raw_text),
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
                    url=sanitize_null_bytes(item.get("url")),
                    status="pending",
                    meta=sanitize_null_bytes(item),
                )
                db.add(src)
                discovered_sources.append(src)
            await db.flush()

            # Check if GitHub link is present
            has_github = (
                any(s.type == "github" for s in discovered_sources)
                or ("github.com" in (parsed_pdf.raw_text or "").lower())
            )

            if not has_github:
                logger.info(
                    f"Analysis {analysis.id}: No GitHub link discovered in resume. "
                    "Proceeding with multi-source evidence extraction and claim evaluation."
                )

            # 3. Extracting Resume Claims
            analysis.stage = "extracting_claims"
            analysis.progress = 35
            await db.commit()

            extracted_claims = await claim_extractor.extract_claims(
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
                    claim_text=sanitize_null_bytes(claim_text),
                    category=sanitize_null_bytes(cat),
                    section=sanitize_null_bytes(sec),
                    source_text=sanitize_null_bytes(c.get("source_text", "")),
                    meta=sanitize_null_bytes({
                        "technologies": c.get("technologies", []),
                        "project_name": c.get("project_name"),
                        "attached_url": c.get("attached_url"),
                    }),
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

            # Autonomous Project Search: Discover candidate repositories matching project names without direct URLs
            if candidate_gh_user:
                for c_rec in claim_records:
                    meta_dict = c_rec.meta if isinstance(c_rec.meta, dict) else {}
                    p_name = meta_dict.get("project_name")
                    p_url = meta_dict.get("attached_url")
                    if p_name and not p_url:
                        clean_p = p_name.lower().strip()
                        already_found = any(clean_p in k for k in collected_repo_keys)
                        if not already_found:
                            searched_repo = await self.github_collector.search_user_project(candidate_gh_user, p_name)
                            if searched_repo:
                                r_key = f"{(searched_repo.get('owner') or candidate_gh_user).lower()}/{(searched_repo.get('name') or '').lower()}"
                                if r_key not in collected_repo_keys:
                                    collected_repo_keys.add(r_key)
                                    collected_repos_data.append(searched_repo)

            # Persist collected repositories and evidence records
            for r in collected_repos_data:
                repo_obj = Repository(
                    analysis_id=analysis.id,
                    candidate_id=analysis.candidate_id,
                    github_source_id=discovered_sources[0].id if discovered_sources else None,
                    name=sanitize_null_bytes(r.get("name")),
                    owner=sanitize_null_bytes(r.get("owner")),
                    url=sanitize_null_bytes(r.get("url")),
                    description=sanitize_null_bytes(r.get("description")),
                    stars=r.get("stars", 0),
                    forks=r.get("forks", 0),
                    meta=sanitize_null_bytes({"languages": r.get("languages", {})}),
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
                        title=sanitize_null_bytes(f"{r.get('name')} README"),
                        content=sanitize_null_bytes(f"Repository {r.get('name')} Documentation:\n\n{r.get('readme')}"),
                        url=sanitize_null_bytes(r.get("url")),
                        meta=sanitize_null_bytes({"repo": r.get("name")}),
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
                        title=sanitize_null_bytes(f"{r.get('name')} {m_name}"),
                        content=sanitize_null_bytes(f"Project: {r.get('name')}\nManifest: {m_name}\nVerification Summary: {summary_str}\n\n{m_content}"),
                        url=sanitize_null_bytes(r.get("url")),
                        meta=sanitize_null_bytes({"repo": r.get("name"), "manifest": m_name, "parsed": m_meta}),
                    )
                    db.add(manifest_ev)

                # Summary evidence of repository activity
                repo_summary_ev = Evidence(
                    analysis_id=analysis.id,
                    candidate_id=analysis.candidate_id,
                    source_id=discovered_sources[0].id if discovered_sources else None,
                    evidence_type="github_repo",
                    title=sanitize_null_bytes(f"Repository {r.get('name')}"),
                    content=sanitize_null_bytes(
                        f"Repo: {r.get('name')}. Description: {r.get('description')}. "
                        f"Languages: {list(r.get('languages', {}).keys())}. "
                        f"Publicly verified GitHub repository with candidate attribution."
                    ),
                    url=sanitize_null_bytes(r.get("url")),
                    meta=sanitize_null_bytes({
                        "repo": r.get("name"),
                        "candidate_commit_count": r.get("candidate_commit_count", 5),
                        "total_commit_count": r.get("total_commit_count", 5),
                    }),
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
                    title=sanitize_null_bytes("Candidate Verified Tech Stack Inventory"),
                    content=sanitize_null_bytes(inventory_content),
                    url=sanitize_null_bytes(discovered_sources[0].url if discovered_sources else None),
                    meta=sanitize_null_bytes({
                        "languages": list(all_languages),
                        "packages_sample": list(all_manifest_packages)[:50],
                        "services": list(all_infra_services),
                        "repo_count": verified_repo_count,
                        "tech_repo_counts": {k: len(v) for k, v in tech_repo_map.items()},
                        "tech_commits": tech_commits_map,
                    }),
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
                                title=sanitize_null_bytes(page_data.get("title") or "Project Page"),
                                content=sanitize_null_bytes(page_data.get("content")),
                                url=sanitize_null_bytes(src.url),
                                meta=sanitize_null_bytes({"headings": page_data.get("headings", [])}),
                            )
                            db.add(web_ev)
                        else:
                            src.status = page_data.get("status", "failed") if isinstance(page_data, dict) else "failed"

            await db.flush()

            # 5b. Collecting Competitive Programming & Professional Platform Evidence
            comp_sources = [
                s for s in discovered_sources
                if s.type in ("leetcode", "codeforces", "linkedin")
            ]
            for src in comp_sources:
                src_meta = src.meta if isinstance(src.meta, dict) else {}
                if src.type == "leetcode":
                    lc_info = src_meta.get("leetcode_info") or {}
                    username = lc_info.get("username")
                    if not username and src.url:
                        from backend.app.parsers.url_extractor import parse_leetcode_url
                        parsed_lc = parse_leetcode_url(src.url)
                        if parsed_lc:
                            username = parsed_lc.get("username")
                    if username:
                        lc_data = await self.competitive_collector.fetch_leetcode_evidence(username)
                        if lc_data and lc_data.get("status") == "collected":
                            src.status = "collected"
                            lc_ev = Evidence(
                                analysis_id=analysis.id,
                                candidate_id=analysis.candidate_id,
                                source_id=src.id,
                                evidence_type="leetcode_profile",
                                title=sanitize_null_bytes(f"LeetCode Profile ({username})"),
                                content=sanitize_null_bytes(lc_data.get("summary", "")),
                                url=sanitize_null_bytes(lc_data.get("url") or src.url),
                                meta=sanitize_null_bytes(lc_data),
                            )
                            db.add(lc_ev)
                        else:
                            src.status = lc_data.get("status", "failed") if isinstance(lc_data, dict) else "failed"

                elif src.type == "codeforces":
                    cf_info = src_meta.get("codeforces_info") or {}
                    handle = cf_info.get("handle")
                    if not handle and src.url:
                        from backend.app.parsers.url_extractor import parse_codeforces_url
                        parsed_cf = parse_codeforces_url(src.url)
                        if parsed_cf:
                            handle = parsed_cf.get("handle")
                    if handle:
                        cf_data = await self.competitive_collector.fetch_codeforces_evidence(handle)
                        if cf_data and cf_data.get("status") == "collected":
                            src.status = "collected"
                            cf_ev = Evidence(
                                analysis_id=analysis.id,
                                candidate_id=analysis.candidate_id,
                                source_id=src.id,
                                evidence_type="codeforces_profile",
                                title=sanitize_null_bytes(f"Codeforces Profile ({handle})"),
                                content=sanitize_null_bytes(cf_data.get("summary", "")),
                                url=sanitize_null_bytes(cf_data.get("url") or src.url),
                                meta=sanitize_null_bytes(cf_data),
                            )
                            db.add(cf_ev)
                        else:
                            src.status = cf_data.get("status", "failed") if isinstance(cf_data, dict) else "failed"

                elif src.type == "linkedin":
                    li_info = src_meta.get("linkedin_info") or {}
                    handle = li_info.get("handle")
                    if not handle and src.url:
                        from backend.app.parsers.url_extractor import parse_linkedin_url
                        parsed_li = parse_linkedin_url(src.url)
                        if parsed_li:
                            handle = parsed_li.get("handle")
                    if handle:
                        cand_name = parsed_pdf.candidate_info.get("name") if hasattr(parsed_pdf, "candidate_info") and isinstance(parsed_pdf.candidate_info, dict) else None
                        li_data = await self.linkedin_collector.verify_linkedin_profile(handle, candidate_name=cand_name)
                        if li_data and li_data.get("status") in ("collected", "unverified_no_serp_key"):
                            src.status = "collected" if li_data.get("status") == "collected" else "pending"
                            li_ev = Evidence(
                                analysis_id=analysis.id,
                                candidate_id=analysis.candidate_id,
                                source_id=src.id,
                                evidence_type="linkedin_profile",
                                title=sanitize_null_bytes(f"LinkedIn Profile ({handle})"),
                                content=sanitize_null_bytes(li_data.get("summary", "")),
                                url=sanitize_null_bytes(li_data.get("url") or src.url),
                                meta=sanitize_null_bytes(li_data),
                            )
                            db.add(li_ev)

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

            # Prevent duplicate embedding records if re-running or racing
            ev_ids = [ev.id for ev in all_evidence]
            existing_emb_ids = set()
            if ev_ids:
                emb_check_stmt = select(Embedding.evidence_id).where(Embedding.evidence_id.in_(ev_ids))
                emb_check_res = await db.execute(emb_check_stmt)
                existing_emb_ids = set(emb_check_res.scalars().all())

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

                # Persist embedding vector representation if not already persisted
                if ev.id not in existing_emb_ids:
                    vector = self.embedder.embed_text(f"{ev.title}\n{ev.content}")
                    emb_record = Embedding(evidence_id=ev.id, vector_data=vector)
                    db.add(emb_record)
                    existing_emb_ids.add(ev.id)

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
            eval_outcomes = await evaluation_agent.evaluate_claims_batch(claims_with_chunks)

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
                    reasoning=sanitize_null_bytes(eval_data.get("reasoning", "")),
                    verified_by=eval_data.get("verified_by") or ("system_1_cross_encoder" if "System 1" in eval_data.get("reasoning", "") else "system_2_deliberative"),
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
                    "source_text": claim.source_text,
                    "category": claim.category,
                    "verdict": eval_data.get("verdict"),
                    "reasoning": eval_data.get("reasoning"),
                    "confidence": eval_data.get("confidence", 0.5),
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

            candidate = await db.get(Candidate, analysis.candidate_id)
            alias_name = candidate.anonymous_alias if candidate else "Anonymous Candidate"

            # Ammunition extraction: competitive programming stats
            competitive_stats: Dict[str, Any] = {}
            for ev in all_evidence:
                if ev.evidence_type in ("competitive_programming_leetcode", "competitive_programming_codeforces"):
                    p_name = "leetcode" if "leetcode" in ev.evidence_type else "codeforces"
                    competitive_stats[p_name] = ev.meta or {"summary": ev.content}

            # Ammunition extraction: suspicious or toy dependencies
            suspicious_deps: List[str] = []
            for ev in all_evidence:
                if ev.evidence_type in ("github_manifest", "github_tech_stack") and ev.meta:
                    packages = ev.meta.get("packages_sample") or ev.meta.get("parsed", {}).get("dependencies", [])
                    if isinstance(packages, dict):
                        packages = list(packages.keys())
                    if isinstance(packages, list):
                        for pkg in packages[:30]:
                            if any(toy in pkg.lower() for toy in ["create-react-app", "react-scripts", "is-odd", "is-even", "left-pad", "fake", "mock", "test-app"]):
                                suspicious_deps.append(pkg)

            roast_data = await roast_agent.generate_roast(
                larp_score=larp_score,
                evaluations=eval_results_for_scoring,
                repos=collected_repos_data,
                intensity=settings.ROAST_INTENSITY,
                has_github=has_github_source,
                candidate_alias=alias_name,
                competitive_stats=competitive_stats if competitive_stats else None,
                suspicious_dependencies=suspicious_deps if suspicious_deps else None,
            )

            summary_payload = json.dumps({
                "verdict_summary": sanitize_null_bytes(roast_data.get("verdict_summary")),
                "funny_mismatch": sanitize_null_bytes(roast_data.get("funny_mismatch")),
                "weakest_claim": sanitize_null_bytes(roast_data.get("weakest_claim")),
                "roast_archetype": sanitize_null_bytes(roast_data.get("roast_archetype")),
            })

            # Check if leaderboard entry already exists
            stmt_existing = select(LeaderboardEntry).where(LeaderboardEntry.analysis_id == analysis.id)
            existing_res = await db.execute(stmt_existing)
            existing_entry = existing_res.scalar_one_or_none()

            raw_roast = roast_data.get("overall_roast", "No roast available.")
            clean_roast = sanitize_null_bytes(raw_roast)

            if existing_entry:
                existing_entry.larp_score = larp_score
                existing_entry.roast = clean_roast
                existing_entry.summary = summary_payload
            else:
                leaderboard_entry = LeaderboardEntry(
                    analysis_id=analysis.id,
                    anonymous_alias=sanitize_null_bytes(alias_name),
                    larp_score=larp_score,
                    roast=clean_roast,
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
            logger.error(f"Analysis {analysis_id} halted due to provider rate limit: {e}")
            await db.rollback()
            try:
                analysis = await db.get(Analysis, analysis_id)
                if analysis:
                    analysis.status = "failed"
                    analysis.stage = "failed"
                    analysis.error = "Analysis halted: LLM provider rate limit reached (Groq 429). All configured AI providers unavailable. Please retry in a few moments."
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
