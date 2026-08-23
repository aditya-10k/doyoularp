import pytest
from backend.app.rag.embedding_service import EmbeddingService
from backend.app.rag.evidence_retriever import EvidenceRetriever
from backend.app.rag.vector_store import InMemoryVectorStore, cosine_similarity


@pytest.mark.asyncio
async def test_embedding_service_properties():
    embedder = EmbeddingService(dimension=128)
    vec1 = embedder.embed_text("FastAPI backend with PostgreSQL database")
    vec2 = embedder.embed_text("High performance Python FastAPI REST API with SQL database")
    vec3 = embedder.embed_text("Cooking recipes for chocolate chip cookies and baking cakes")

    assert len(vec1) == 128
    assert len(vec2) == 128
    assert len(vec3) == 128

    sim_related = cosine_similarity(vec1, vec2)
    sim_unrelated = cosine_similarity(vec1, vec3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.4


@pytest.mark.asyncio
async def test_evidence_retriever_hybrid_search():
    embedder = EmbeddingService(dimension=128)
    vector_store = InMemoryVectorStore()
    retriever = EvidenceRetriever(embedder, vector_store)

    # Index 3 evidence items
    await retriever.index_evidence(
        evidence_id="ev_flutter",
        analysis_id="test_analysis_1",
        title="travel-app",
        content="Cross-platform travel booking application written in Flutter and Dart with Firebase auth.",
        url="https://github.com/user/travel-app",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 42, "total_commit_count": 50},
    )

    await retriever.index_evidence(
        evidence_id="ev_react",
        analysis_id="test_analysis_1",
        title="todo-list",
        content="Simple frontend todo list made with React and Tailwind CSS.",
        url="https://github.com/user/todo-list",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 5, "total_commit_count": 5},
    )

    await retriever.index_evidence(
        evidence_id="ev_k8s",
        analysis_id="test_analysis_1",
        title="infra-helm",
        content="Kubernetes Helm charts and Terraform configs for multi-region cloud deployment.",
        url="https://github.com/user/infra-helm",
        evidence_type="github_repo",
        meta={"candidate_commit_count": 0, "total_commit_count": 200},
    )

    # Search for Flutter claim
    results = await retriever.retrieve_for_claim(
        claim_text="Built a mobile travel app using Flutter",
        analysis_id="test_analysis_1",
        top_k=2,
    )

    assert len(results) > 0
    assert results[0].evidence_id == "ev_flutter"
    assert results[0].score > 0.6
