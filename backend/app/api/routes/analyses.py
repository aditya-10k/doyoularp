import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.core.security import validate_pdf_upload
from backend.app.db.session import async_session_maker, get_db
from backend.app.models.models import (
    Analysis,
    Candidate,
    Claim,
    Evaluation,
    Evidence,
    LeaderboardEntry,
    Resume,
    Source,
)
from backend.app.schemas.analysis import (
    AnalysisCreate,
    AnalysisStatusResponse,
    ResumeUploadResponse,
)
from backend.app.schemas.claim import (
    ClaimResponse,
    ClaimsListResponse,
    EvaluationResponse,
)
from backend.app.schemas.evidence import EvidenceListResponse, EvidenceResponse
from backend.app.schemas.result import (
    LeaderboardEntryItem,
    LeaderboardResponse,
    ResultResponse,
    SourceSummary,
)
from backend.app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/analyses", tags=["Analyses"])
pipeline_service = PipelineService()


async def _run_pipeline_background(analysis_id: str, filename: str, pdf_bytes: bytes) -> None:
    async with async_session_maker() as db:
        await pipeline_service.run_pipeline(analysis_id, filename, pdf_bytes, db)


@router.post("", response_model=AnalysisStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    payload: Optional[AnalysisCreate] = None,
    db: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    """Creates a new analysis session and assigns an anonymous alias."""
    alias = payload.alias if payload else None
    analysis = await pipeline_service.create_analysis(db, alias)
    candidate = await db.get(Candidate, analysis.candidate_id)

    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        candidate_alias=candidate.anonymous_alias if candidate else "Anonymous",
        status=analysis.status,
        stage=analysis.stage,
        progress=analysis.progress,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        error=analysis.error,
    )


@router.post("/{analysis_id}/resume", response_model=ResumeUploadResponse)
async def upload_resume(
    analysis_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> ResumeUploadResponse:
    """Uploads resume PDF and kicks off the asynchronous 13-stage analysis pipeline."""
    validate_pdf_upload(file)

    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    if analysis.status in ("running", "completed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Analysis is already {analysis.status}")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > settings.MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size ({settings.MAX_PDF_SIZE_BYTES // (1024*1024)}MB)",
        )

    # Queue background task for analysis
    background_tasks.add_task(
        _run_pipeline_background,
        analysis_id=analysis.id,
        filename=file.filename or "resume.pdf",
        pdf_bytes=pdf_bytes,
    )

    return ResumeUploadResponse(
        analysis_id=analysis.id,
        filename=file.filename or "resume.pdf",
        page_count=1,
        extracted_urls_count=0,
        message="Resume received. Analysis pipeline launched in background.",
    )


@router.get("/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnalysisStatusResponse:
    """Returns current analysis status, execution stage, and progress percentage."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    candidate = await db.get(Candidate, analysis.candidate_id)

    return AnalysisStatusResponse(
        analysis_id=analysis.id,
        candidate_alias=candidate.anonymous_alias if candidate else "Anonymous",
        status=analysis.status,
        stage=analysis.stage,
        progress=analysis.progress,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        error=analysis.error,
    )


@router.get("/{analysis_id}/stream")
async def stream_analysis_events(analysis_id: str, request: Request):
    """
    Streams analysis progress and status updates via Server-Sent Events (SSE).
    Replaces repeated polling with a persistent real-time event stream.
    """
    async def event_generator():
        last_progress = -1
        last_stage = None
        last_status = None

        for _ in range(750):  # Up to 5 minutes
            if await request.is_disconnected():
                break

            async with async_session_maker() as db:
                analysis = await db.get(Analysis, analysis_id)
                if not analysis:
                    err_payload = json.dumps({"error": "Analysis not found"})
                    yield f"event: failed\ndata: {err_payload}\n\n"
                    break

                candidate = await db.get(Candidate, analysis.candidate_id)
                alias = candidate.anonymous_alias if candidate else "Anonymous"

                # Send initial state or any progress change
                if (
                    analysis.progress != last_progress
                    or analysis.stage != last_stage
                    or analysis.status != last_status
                ):
                    last_progress = analysis.progress
                    last_stage = analysis.stage
                    last_status = analysis.status

                    data = {
                        "analysis_id": analysis.id,
                        "candidate_alias": alias,
                        "status": analysis.status,
                        "stage": analysis.stage,
                        "progress": analysis.progress,
                        "created_at": analysis.created_at.isoformat() if analysis.created_at else "",
                        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
                        "error": analysis.error,
                    }
                    yield f"event: progress\ndata: {json.dumps(data)}\n\n"

                if analysis.status == "completed":
                    yield f"event: completed\ndata: {json.dumps({'status': 'completed', 'analysis_id': analysis.id})}\n\n"
                    break
                elif analysis.status == "failed":
                    yield f"event: failed\ndata: {json.dumps({'status': 'failed', 'error': analysis.error})}\n\n"
                    break

            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{analysis_id}/claims", response_model=ClaimsListResponse)
async def get_analysis_claims(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClaimsListResponse:
    """Returns all extracted atomic claims and their evidence-backed evaluations."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    stmt = (
        select(Claim)
        .where(Claim.analysis_id == analysis_id)
        .options(
            selectinload(Claim.evaluation).selectinload(Evaluation.evidence_records),
        )
    )
    result = await db.execute(stmt)
    claims = list(result.scalars().all())

    claim_responses = []
    for c in claims:
        eval_resp = None
        if c.evaluation:
            eval_resp = EvaluationResponse(
                id=c.evaluation.id,
                verdict=c.evaluation.verdict,
                confidence=c.evaluation.confidence,
                reasoning=c.evaluation.reasoning,
                evidence_ids=[e.id for e in c.evaluation.evidence_records],
            )

        claim_responses.append(
            ClaimResponse(
                id=c.id,
                claim_text=c.claim_text,
                category=c.category,
                section=c.section,
                source_text=c.source_text,
                page_number=c.page_number,
                meta=c.meta,
                evaluation=eval_resp,
            )
        )

    return ClaimsListResponse(
        analysis_id=analysis_id,
        total=len(claim_responses),
        claims=claim_responses,
    )


@router.get("/{analysis_id}/evidence", response_model=EvidenceListResponse)
async def get_analysis_evidence(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> EvidenceListResponse:
    """Returns all external evidence collected for this candidate."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    stmt = select(Evidence).where(Evidence.analysis_id == analysis_id).order_by(desc(Evidence.created_at))
    result = await db.execute(stmt)
    evidence_items = list(result.scalars().all())

    items = [
        EvidenceResponse(
            id=e.id,
            evidence_type=e.evidence_type,
            title=e.title,
            content=e.content,
            url=e.url,
            meta=e.meta,
            created_at=e.created_at,
        )
        for e in evidence_items
    ]

    return EvidenceListResponse(
        analysis_id=analysis_id,
        total=len(items),
        items=items,
    )


@router.get("/{analysis_id}/result", response_model=ResultResponse)
async def get_analysis_result(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> ResultResponse:
    """Returns the full finished analysis result, LARP score, roast, and claim breakdown."""
    analysis = await db.get(Analysis, analysis_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")

    if analysis.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis is not completed yet (current status: {analysis.status}, stage: {analysis.stage})",
        )

    stmt_entry = select(LeaderboardEntry).where(LeaderboardEntry.analysis_id == analysis_id)
    entry_res = await db.execute(stmt_entry)
    entry = entry_res.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result entry not found")

    # Sources
    stmt_src = select(Source).where(Source.analysis_id == analysis_id)
    src_res = await db.execute(stmt_src)
    sources = [
        SourceSummary(type=s.type, url=s.url, status=s.status)
        for s in src_res.scalars().all()
    ]

    # Claims breakdown
    stmt_claims = (
        select(Claim)
        .where(Claim.analysis_id == analysis_id)
        .options(
            selectinload(Claim.evaluation).selectinload(Evaluation.evidence_records),
        )
    )
    claims_res = await db.execute(stmt_claims)
    claims = list(claims_res.scalars().all())

    claims_breakdown = []
    strongest_claim = None
    weakest_claim = None

    for c in claims:
        eval_resp = None
        if c.evaluation:
            eval_resp = EvaluationResponse(
                id=c.evaluation.id,
                verdict=c.evaluation.verdict,
                confidence=c.evaluation.confidence,
                reasoning=c.evaluation.reasoning,
                evidence_ids=[e.id for e in c.evaluation.evidence_records],
            )
            if c.evaluation.verdict == "SUPPORTED" and not strongest_claim:
                strongest_claim = c.claim_text
            elif c.evaluation.verdict in ("CONTRADICTED", "UNVERIFIED") and not weakest_claim:
                weakest_claim = c.claim_text

        claims_breakdown.append(
            ClaimResponse(
                id=c.id,
                claim_text=c.claim_text,
                category=c.category,
                section=c.section,
                source_text=c.source_text,
                page_number=c.page_number,
                meta=c.meta,
                evaluation=eval_resp,
            )
        )

    verdict_summary = entry.summary or "Evaluation complete."
    funny_mismatch = None
    derogatory_versions = None
    if entry.summary and entry.summary.startswith("{"):
        try:
            parsed_sum = json.loads(entry.summary)
            if isinstance(parsed_sum, dict):
                verdict_summary = parsed_sum.get("verdict_summary") or verdict_summary
                funny_mismatch = parsed_sum.get("funny_mismatch")
                derogatory_versions = parsed_sum.get("derogatory_versions")
                if parsed_sum.get("weakest_claim") and not weakest_claim:
                    weakest_claim = parsed_sum.get("weakest_claim")
        except Exception:
            pass

    return ResultResponse(
        analysis_id=analysis.id,
        anonymous_alias=entry.anonymous_alias,
        larp_score=entry.larp_score,
        roast=entry.roast,
        verdict_summary=verdict_summary,
        strongest_claim=strongest_claim,
        weakest_claim=weakest_claim,
        funny_mismatch=funny_mismatch,
        derogatory_versions=derogatory_versions,
        claims_count=len(claims_breakdown),
        claims_breakdown=claims_breakdown,
        sources=sources,
        leaderboard_token=entry.token,
        completed_at=analysis.completed_at,
    )


async def _fetch_leaderboard_response(
    db: AsyncSession,
    analysis_id: Optional[str] = None,
) -> LeaderboardResponse:
    """Queries top leaderboard entries ordered by highest LARP score (most delusional first)."""
    stmt = select(LeaderboardEntry).order_by(desc(LeaderboardEntry.larp_score)).limit(50)
    res = await db.execute(stmt)
    entries = list(res.scalars().all())

    user_entry_item = None
    leaderboard_items = []
    for rank, e in enumerate(entries, start=1):
        item = LeaderboardEntryItem(
            rank=rank,
            anonymous_alias=e.anonymous_alias,
            larp_score=e.larp_score,
            roast=e.roast,
            created_at=e.created_at,
        )
        leaderboard_items.append(item)
        if analysis_id and analysis_id != "global" and str(e.analysis_id) == str(analysis_id):
            user_entry_item = item

    if analysis_id and analysis_id != "global" and not user_entry_item:
        user_stmt = select(LeaderboardEntry).where(LeaderboardEntry.analysis_id == str(analysis_id))
        user_res = await db.execute(user_stmt)
        user_e = user_res.scalar_one_or_none()
        if user_e:
            rank_stmt = select(func.count(LeaderboardEntry.id)).where(LeaderboardEntry.larp_score > user_e.larp_score)
            rank_res = await db.execute(rank_stmt)
            user_rank = (rank_res.scalar() or 0) + 1
            user_entry_item = LeaderboardEntryItem(
                rank=user_rank,
                anonymous_alias=user_e.anonymous_alias,
                larp_score=user_e.larp_score,
                roast=user_e.roast,
                created_at=user_e.created_at,
            )

    return LeaderboardResponse(
        total=len(leaderboard_items),
        user_entry=user_entry_item,
        leaderboard=leaderboard_items,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_global_leaderboard(
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    """Returns top ranked global leaderboard entries."""
    return await _fetch_leaderboard_response(db, None)


@router.get("/{analysis_id}/leaderboard", response_model=LeaderboardResponse)
async def get_analysis_leaderboard(
    analysis_id: str,
    db: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    """Returns leaderboard context, highlighting user entry if completed, or global if not."""
    return await _fetch_leaderboard_response(db, analysis_id)
