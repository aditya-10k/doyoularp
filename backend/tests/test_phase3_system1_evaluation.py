import pytest
from unittest.mock import MagicMock, patch

from backend.app.agents.system1_verifier import System1Verifier
from backend.app.agents.evaluation_agent import EvaluationAgent
from backend.app.rag.evidence_retriever import RetrievedEvidenceChunk
from backend.app.models.models import Claim


def test_system1_disabled_flag():
    """Verify System1Verifier is disabled when enable_system1 is False."""
    v = System1Verifier(enable_system1=False)
    assert v.is_available is False
    assert v.predict_pair("premise", "hypothesis") is None
    assert v.triage_claim("claim", []) is None


def test_system1_triage_entailment():
    """Verify high entailment probability (>0.90) assigns instant SUPPORTED."""
    v = System1Verifier(enable_system1=True)
    v._init_attempted = True
    v._is_ready = True  # Mock ready state

    chunk = RetrievedEvidenceChunk(
        evidence_id="ev_fastapi",
        score=0.92,
        title="main.py",
        content="from fastapi import FastAPI\napp = FastAPI()\n@app.get('/api/users')\ndef get_users(): return []",
        url="https://github.com/user/project",
        evidence_type="github_repo",
    )

    with patch.object(v, "predict_batch") as mock_pred:
        mock_pred.return_value = [
            {"entailment": 0.95, "contradiction": 0.01, "neutral": 0.04}
        ]

        result = v.triage_claim("Built high performance REST API in FastAPI", [chunk])
        assert result is not None
        assert result["verdict"] == "SUPPORTED"
        assert result["confidence"] >= 0.90
        assert result["evidence_ids"] == ["ev_fastapi"]
        assert result["verified_by"] == "system_1_cross_encoder"
        assert "main.py" in result["reasoning"]


def test_system1_triage_contradiction():
    """Verify high contradiction probability (>0.88) assigns instant CONTRADICTED when allow_contradiction=True."""
    v = System1Verifier(enable_system1=True, allow_contradiction=True)
    v._init_attempted = True
    v._is_ready = True

    chunk = RetrievedEvidenceChunk(
        evidence_id="ev_static",
        score=0.91,
        title="index.html",
        content="<!DOCTYPE html><html><body><h1>My Portfolio</h1></body></html>",
        url="https://github.com/user/portfolio",
        evidence_type="github_repo",
    )

    with patch.object(v, "predict_batch") as mock_pred:
        mock_pred.return_value = [
            {"entailment": 0.01, "contradiction": 0.93, "neutral": 0.06}
        ]

        result = v.triage_claim("Architected distributed real-time Kafka event stream", [chunk])
        assert result is not None
        assert result["verdict"] == "CONTRADICTED"
        assert result["confidence"] >= 0.88
        assert result["evidence_ids"] == ["ev_static"]
        assert result["verified_by"] == "system_1_cross_encoder"


def test_system1_triage_inconclusive_returns_none():
    """Verify ambiguous probabilities do not trigger auto-verdict and return None for LLM escalation."""
    v = System1Verifier(enable_system1=True)
    v._init_attempted = True
    v._is_ready = True

    chunk = RetrievedEvidenceChunk(
        evidence_id="ev_partial",
        score=0.75,
        title="README.md",
        content="Project overview with some documentation.",
        url="https://github.com/user/proj",
        evidence_type="github_repo",
    )

    with patch.object(v, "predict_batch") as mock_pred:
        # Ambiguous scores (below 0.90 entailment and below 0.88 contradiction)
        mock_pred.return_value = [
            {"entailment": 0.65, "contradiction": 0.15, "neutral": 0.20}
        ]

        result = v.triage_claim("Optimized database queries for 10x throughput", [chunk])
        assert result is None  # Escalates to System 2 LLM


@pytest.mark.asyncio
async def test_evaluation_agent_uses_system1_triage_batch():
    """Verify EvaluationAgent batches non-skill claims through System 1 and avoids LLM calls on high confidence."""
    mock_s1 = MagicMock(spec=System1Verifier)
    mock_s1.is_available = True

    mock_groq = MagicMock()
    mock_groq.is_configured = True

    agent = EvaluationAgent(groq_client=mock_groq, system1_verifier=mock_s1)

    chunk = RetrievedEvidenceChunk(
        evidence_id="ev_1",
        score=0.95,
        title="repo",
        content="verified code content",
        url="https://github.com/test/repo",
        evidence_type="github_repo",
    )

    claim1 = Claim(
        id="c1",
        claim_text="Developed FastAPI endpoints",
        category="project",
        section="projects",
        source_text="FastAPI backend",
    )

    # Mock System 1 resolving claim1 with high entailment
    mock_s1.triage_claim.return_value = {
        "verdict": "SUPPORTED",
        "confidence": 0.94,
        "reasoning": "System 1 corroborated",
        "evidence_ids": ["ev_1"],
        "verified_by": "system_1_cross_encoder",
    }

    outcomes = await agent.evaluate_claims_batch([(claim1, [chunk])])

    assert len(outcomes) == 1
    c_out, eval_data = outcomes[0]
    assert c_out.id == "c1"
    assert eval_data["verdict"] == "SUPPORTED"
    assert eval_data["verified_by"] == "system_1_cross_encoder"

    # Groq was never called because System 1 resolved the claim in 0ms!
    mock_groq.chat_completion.assert_not_called()
