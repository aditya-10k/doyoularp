from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class EvidenceResponse(BaseModel):
    id: str
    evidence_type: str
    title: str
    content: str
    url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime


class EvidenceListResponse(BaseModel):
    analysis_id: str
    total: int
    items: List[EvidenceResponse]
