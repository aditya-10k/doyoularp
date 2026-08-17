import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.session import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Association table for Evaluation <-> Evidence
evaluation_evidence = Table(
    "evaluation_evidence",
    Base.metadata,
    Column("evaluation_id", String(36), ForeignKey("evaluations.id", ondelete="CASCADE"), primary_key=True),
    Column("evidence_id", String(36), ForeignKey("evidence.id", ondelete="CASCADE"), primary_key=True),
)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    anonymous_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    analyses: Mapped[List["Analysis"]] = relationship("Analysis", back_populates="candidate", cascade="all, delete-orphan")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(50), default="created")  # created, running, completed, failed
    stage: Mapped[str] = mapped_column(String(50), default="created")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="analyses", lazy="selectin")
    resumes: Mapped[List["Resume"]] = relationship("Resume", back_populates="analysis", cascade="all, delete-orphan")
    sources: Mapped[List["Source"]] = relationship("Source", back_populates="analysis", cascade="all, delete-orphan")
    claims: Mapped[List["Claim"]] = relationship("Claim", back_populates="analysis", cascade="all, delete-orphan")
    evidence_items: Mapped[List["Evidence"]] = relationship("Evidence", back_populates="analysis", cascade="all, delete-orphan")
    repositories: Mapped[List["Repository"]] = relationship("Repository", back_populates="analysis", cascade="all, delete-orphan")
    leaderboard_entry: Mapped[Optional["LeaderboardEntry"]] = relationship("LeaderboardEntry", back_populates="analysis", uselist=False, cascade="all, delete-orphan", lazy="selectin")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="resumes")
    claims: Mapped[List["Claim"]] = relationship("Claim", back_populates="resume", cascade="all, delete-orphan")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # github, linkedin, portfolio, project, app_store, play_store, other
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, collected, failed, inaccessible
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="sources")
    evidence_items: Mapped[List["Evidence"]] = relationship("Evidence", back_populates="source", cascade="all, delete-orphan")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"))
    resume_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")  # project, skill, achievement, experience, education
    section: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="claims")
    resume: Mapped[Optional["Resume"]] = relationship("Resume", back_populates="claims")
    evaluation: Mapped[Optional["Evaluation"]] = relationship("Evaluation", back_populates="claim", uselist=False, cascade="all, delete-orphan", lazy="selectin")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)  # github_repo, github_commit, github_manifest, web_page, readme
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="evidence_items")
    source: Mapped[Optional["Source"]] = relationship("Source", back_populates="evidence_items")
    embedding: Mapped[Optional["Embedding"]] = relationship("Embedding", back_populates="evidence", uselist=False, cascade="all, delete-orphan")
    evaluations: Mapped[List["Evaluation"]] = relationship("Evaluation", secondary=evaluation_evidence, back_populates="evidence_records", lazy="selectin")


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"))
    candidate_id: Mapped[str] = mapped_column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"))
    github_source_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="repositories")
    commits: Mapped[List["Commit"]] = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
    languages: Mapped[List["RepositoryLanguage"]] = relationship("RepositoryLanguage", back_populates="repository", cascade="all, delete-orphan")
    contributors: Mapped[List["Contributor"]] = relationship("Contributor", back_populates="repository", cascade="all, delete-orphan")


class Commit(Base):
    __tablename__ = "commits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"))
    sha: Mapped[str] = mapped_column(String(100), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    committed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="commits")


class RepositoryLanguage(Base):
    __tablename__ = "repository_languages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"))
    language: Mapped[str] = mapped_column(String(100), nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, default=0)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="languages")


class Contributor(Base):
    __tablename__ = "contributors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"))
    username: Mapped[str] = mapped_column(String(200), nullable=False)
    contributions: Mapped[int] = mapped_column(Integer, default=0)

    repository: Mapped["Repository"] = relationship("Repository", back_populates="contributors")


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    evidence_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence.id", ondelete="CASCADE"), unique=True)
    vector_data: Mapped[List[float]] = mapped_column(JSON, nullable=False)  # Stores embedding vector
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    evidence: Mapped["Evidence"] = relationship("Evidence", back_populates="embedding")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), unique=True)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)  # SUPPORTED, PARTIALLY_SUPPORTED, UNVERIFIED, CONTRADICTED
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    claim: Mapped["Claim"] = relationship("Claim", back_populates="evaluation")
    evidence_records: Mapped[List["Evidence"]] = relationship("Evidence", secondary=evaluation_evidence, back_populates="evaluations", lazy="selectin")


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)
    anonymous_alias: Mapped[str] = mapped_column(String(100), nullable=False)
    larp_score: Mapped[float] = mapped_column(Float, nullable=False)
    roast: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, default=generate_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="leaderboard_entry")
