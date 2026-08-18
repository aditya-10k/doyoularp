from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from backend.app.schemas.claim import ClaimResponse


class SourceSummary(BaseModel):
    type: str
    url: str
    status: str


class ResultResponse(BaseModel):
    analysis_id: str
    anonymous_alias: str
    larp_score: float
    roast: str
    verdict_summary: str
    strongest_claim: Optional[str] = None
    weakest_claim: Optional[str] = None
    funny_mismatch: Optional[str] = None
    claims_count: int
    claims_breakdown: List[ClaimResponse]
    sources: List[SourceSummary]
    leaderboard_token: str
    completed_at: Optional[datetime] = None


class LeaderboardEntryItem(BaseModel):
    rank: int
    anonymous_alias: str
    larp_score: float
    roast: str
    created_at: datetime


class LeaderboardResponse(BaseModel):
    total: int
    user_entry: Optional[LeaderboardEntryItem] = None
    leaderboard: List[LeaderboardEntryItem]
