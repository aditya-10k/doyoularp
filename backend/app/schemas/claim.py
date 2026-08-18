from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class EvaluationResponse(BaseModel):
    id: str
    verdict: str  # SUPPORTED, PARTIALLY_SUPPORTED, UNVERIFIED, CONTRADICTED
    confidence: float
    reasoning: str
    evidence_ids: List[str] = []


class ClaimResponse(BaseModel):
    id: str
    claim_text: str
    category: str
    section: Optional[str] = None
    source_text: str
    page_number: int
    meta: Optional[Dict[str, Any]] = None
    evaluation: Optional[EvaluationResponse] = None


class ClaimsListResponse(BaseModel):
    analysis_id: str
    total: int
    claims: List[ClaimResponse]
