from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AnalysisCreate(BaseModel):
    alias: Optional[str] = Field(None, description="Optional custom anonymous alias")


class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    candidate_alias: str
    status: str  # created, running, completed, failed
    stage: str
    progress: int  # 0 to 100
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ResumeUploadResponse(BaseModel):
    analysis_id: str
    filename: str
    page_count: int
    extracted_urls_count: int
    message: str
