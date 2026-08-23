from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, dot))  # Clamped to [0.0, 1.0] for non-negative weights


class VectorStore(ABC):
    @abstractmethod
    async def add_vector(self, item_id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        analysis_id: Optional[str] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        pass


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store with cosine similarity ranking.
    Fast, zero external dependencies, perfect for testing and single-instance analysis runs.
    """

    def __init__(self):
        # Dict mapping item_id -> {"vector": List[float], "metadata": Dict[str, Any]}
        self.storage: Dict[str, Dict[str, Any]] = {}

    async def add_vector(self, item_id: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        self.storage[item_id] = {
            "vector": vector,
            "metadata": metadata,
        }

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        analysis_id: Optional[str] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        scored: List[Tuple[str, float, Dict[str, Any]]] = []

        for item_id, item in self.storage.items():
            meta = item["metadata"]
            if analysis_id and meta.get("analysis_id") != analysis_id:
                continue

            sim = cosine_similarity(query_vector, item["vector"])
            scored.append((item_id, sim, meta))

        # Sort descending by score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def clear_analysis(self, analysis_id: str) -> int:
        """Removes transient vectors for an analysis to maintain low memory usage on free hosting."""
        to_delete = [
            item_id for item_id, item in self.storage.items()
            if item.get("metadata", {}).get("analysis_id") == analysis_id
        ]
        for item_id in to_delete:
            del self.storage[item_id]
        return len(to_delete)
