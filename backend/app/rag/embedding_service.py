import hashlib
import math
import re
from typing import List, Optional


class EmbeddingService:
    """
    Provider-agnostic embedding service.
    Generates unit-normalized dense embedding vectors.
    Includes a deterministic subword/n-gram hashing embedder that runs locally
    with zero dependencies, plus support for external inference APIs.
    """

    def __init__(self, dimension: int = 128, api_key: Optional[str] = None):
        self.dimension = dimension
        self.api_key = api_key

    def _hash_token(self, token: str) -> int:
        return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dimension

    def embed_text(self, text: str) -> List[float]:
        """
        Generates a deterministic, unit-normalized dense embedding vector
        using character n-grams and word tokens.
        """
        if not text:
            return [0.0] * self.dimension

        clean = text.lower()
        words = re.findall(r'\b\w+\b', clean)

        vector = [0.0] * self.dimension

        # Word tokens
        for word in words:
            idx = self._hash_token(word)
            vector[idx] += 1.0

            # Character 3-grams for subword similarity
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    ngram = word[i : i + 3]
                    ngram_idx = self._hash_token(ngram)
                    vector[ngram_idx] += 0.5

        # Normalize to unit length (L2 norm)
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0.0:
            vector = [v / norm for v in vector]

        return vector

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]
