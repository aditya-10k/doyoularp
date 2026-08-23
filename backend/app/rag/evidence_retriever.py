import re
from typing import Any, Dict, List
from backend.app.rag.embedding_service import EmbeddingService
from backend.app.rag.vector_store import VectorStore


class RetrievedEvidenceChunk:
    def __init__(
        self,
        evidence_id: str,
        score: float,
        title: str,
        content: str,
        url: str,
        evidence_type: str,
        meta: Dict[str, Any],
    ):
        self.evidence_id = evidence_id
        self.score = score
        self.title = title
        self.content = content
        self.url = url
        self.evidence_type = evidence_type
        self.meta = meta

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "score": round(self.score, 4),
            "title": self.title,
            "content": self.content[:300] + "..." if len(self.content) > 300 else self.content,
            "url": self.url,
            "evidence_type": self.evidence_type,
        }


class EvidenceRetriever:
    """
    Hybrid semantic + keyword evidence retriever.
    Combines dense vector search with entity/technology boosting and candidate provenance.
    """

    def __init__(self, embedder: EmbeddingService, vector_store: VectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    async def index_evidence(
        self,
        evidence_id: str,
        analysis_id: str,
        title: str,
        content: str,
        url: str,
        evidence_type: str,
        meta: Dict[str, Any],
    ) -> None:
        """Indexes an evidence item into the vector store."""
        searchable_text = f"{title}\n{content}"
        vector = self.embedder.embed_text(searchable_text)

        payload = {
            "analysis_id": analysis_id,
            "title": title,
            "content": content,
            "url": url,
            "evidence_type": evidence_type,
            "meta": meta,
        }
        await self.vector_store.add_vector(evidence_id, vector, payload)

    async def retrieve_for_claim(
        self,
        claim_text: str,
        analysis_id: str,
        top_k: int = 5,
        claim_meta: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedEvidenceChunk]:
        """
        Retrieves top relevant evidence chunks for a given claim.
        Prioritizes:
        1. Directly attached repository link (if present)
        2. Matching project name/repo
        3. Tech stack inventory across other repositories
        """
        query_vector = self.embedder.embed_text(claim_text)
        results = await self.vector_store.search(query_vector, top_k=50, analysis_id=analysis_id)

        attached_url = ""
        project_name = ""
        if isinstance(claim_meta, dict):
            attached_url = (claim_meta.get("attached_url") or "").lower().strip()
            project_name = (claim_meta.get("project_name") or "").lower().strip()

        # Extract repo name from attached_url if it's a github link
        attached_repo_name = ""
        if "github.com" in attached_url:
            parts = [p for p in attached_url.replace(".git", "").split("/") if p]
            if len(parts) >= 2:
                attached_repo_name = parts[-1].lower()

        # Filter substantive tokens (ignoring generic resume fluff)
        fluff = {
            "proficient", "experienced", "with", "used", "using", "built", "developed",
            "implemented", "in", "and", "the", "for", "from", "app", "application",
            "project", "system", "service", "skills", "skill", "technologies"
        }
        all_tokens = re.findall(r'\b[a-zA-Z0-9_\-\.+#]{2,}\b', claim_text.lower())
        substantive_tokens = [tok for tok in all_tokens if tok not in fluff]

        rescored: List[RetrievedEvidenceChunk] = []

        for item_id, base_score, meta in results:
            content_str = (meta.get("content") or "").lower()
            title_str = (meta.get("title") or "").lower()
            chunk_url = (meta.get("url") or "").lower()
            repo_name = (meta.get("meta", {}).get("repo") or "").lower()
            evidence_type = meta.get("evidence_type", "")
            combined = f"{title_str} {repo_name} {content_str}"

            boost = 0.0
            adjusted_base = base_score
            matched_substantive = []

            # 1. Direct repo link attached: highest priority boost (+0.90)
            if attached_repo_name and (attached_repo_name in repo_name or attached_repo_name in title_str):
                boost += 0.90
            elif attached_url and (attached_url in chunk_url or chunk_url in attached_url):
                boost += 0.90

            # 2. Project name matching (+0.60)
            if project_name:
                p_words = [w for w in re.findall(r'[a-zA-Z0-9]{3,}', project_name) if w not in ("platform", "system", "app", "application")]
                if any(pw in repo_name or pw in title_str for pw in p_words):
                    boost += 0.60

            # 3. Cross-repo Candidate Tech Stack Inventory boost (+0.35)
            if evidence_type == "github_tech_stack":
                boost += 0.35

            if substantive_tokens:
                for tok in substantive_tokens:
                    if tok in combined:
                        matched_substantive.append(tok)
                    elif len(tok) >= 4:
                        stem = tok[:4]
                        if stem in title_str or stem in repo_name or stem in combined:
                            matched_substantive.append(tok)
                            if stem in title_str or stem in repo_name:
                                boost += 0.40

                match_ratio = len(matched_substantive) / len(substantive_tokens)
                if match_ratio > 0:
                    boost += match_ratio * 0.45
                elif not (attached_repo_name and attached_repo_name in repo_name) and evidence_type != "github_tech_stack":
                    # Penalize unrelated chunks when claim has specific technical tokens
                    adjusted_base *= 0.25

            # Authorship boost: candidate-authored repos/commits get preference
            if meta.get("meta", {}).get("candidate_commit_count", 0) > 0:
                boost += 0.05

            final_score = min(1.0, max(0.0, adjusted_base + boost))

            rescored.append(
                RetrievedEvidenceChunk(
                    evidence_id=item_id,
                    score=final_score,
                    title=meta.get("title", ""),
                    content=meta.get("content", ""),
                    url=meta.get("url", ""),
                    evidence_type=meta.get("evidence_type", ""),
                    meta=meta.get("meta", {}),
                )
            )

        # Re-sort by adjusted score
        rescored.sort(key=lambda x: x.score, reverse=True)
        return rescored[:top_k]
