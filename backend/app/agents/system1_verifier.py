import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.app.core.config import settings
from backend.app.rag.evidence_retriever import RetrievedEvidenceChunk

logger = logging.getLogger(__name__)

# MNLI / DeBERTa standard NLI label indexing
LABEL_CONTRADICTION = 0
LABEL_ENTAILMENT = 1
LABEL_NEUTRAL = 2


class System1Verifier:
    """
    Lightweight, fast System 1 Cross-Encoder verifier using ONNX Runtime.
    Runs locally on CPU in ~8-15ms with microscopic memory overhead (~35MB RAM).
    Outputs exact NLI probabilities [Contradiction, Entailment, Neutral].
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        tokenizer_path: Optional[str] = None,
        entailment_threshold: Optional[float] = None,
        contradiction_threshold: Optional[float] = None,
        enable_system1: Optional[bool] = None,
        allow_contradiction: Optional[bool] = None,
    ):
        self.enabled = enable_system1 if enable_system1 is not None else settings.ENABLE_SYSTEM1
        self.allow_contradiction = (
            allow_contradiction
            if allow_contradiction is not None
            else getattr(settings, "SYSTEM1_ALLOW_CONTRADICTION", False)
        )
        self.model_path = model_path or settings.SYSTEM1_MODEL_PATH
        self.tokenizer_path = tokenizer_path
        self.entailment_threshold = entailment_threshold or settings.SYSTEM1_ENTAILMENT_THRESHOLD
        self.contradiction_threshold = contradiction_threshold or settings.SYSTEM1_CONTRADICTION_THRESHOLD

        self._session = None
        self._tokenizer = None
        self._init_attempted = False
        self._is_ready = False

    @property
    def is_available(self) -> bool:
        """Returns True if System 1 is enabled and the ONNX model is loaded/ready."""
        if not self.enabled:
            return False
        if not self._init_attempted and not self._is_ready:
            self._lazy_init()
        return self._is_ready

    def _lazy_init(self) -> None:
        """Attempts lazy initialization of ONNX Runtime session and Tokenizer."""
        self._init_attempted = True
        if not self.enabled:
            return

        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError as e:
            logger.info(f"System 1 dependencies (onnxruntime/tokenizers) not fully loaded: {e}. Falling back to System 2.")
            self._is_ready = False
            return

        resolved_model = self.model_path
        resolved_tok = self.tokenizer_path

        # 1. Check local models directory
        default_dir = Path(__file__).resolve().parent.parent / "models" / "weights"
        if not resolved_model:
            candidate_onnx = default_dir / "nli_deberta_v3_small_int8.onnx"
            if candidate_onnx.exists():
                resolved_model = str(candidate_onnx)

        if not resolved_tok:
            candidate_tok = default_dir / "tokenizer.json"
            if candidate_tok.exists():
                resolved_tok = str(candidate_tok)

        # 2. If not on local disk, attempt download from Hugging Face Hub if online
        if not resolved_model or not resolved_tok or not os.path.exists(resolved_model):
            try:
                from huggingface_hub import hf_hub_download
                repo_id = settings.SYSTEM1_MODEL_NAME
                logger.info(f"Checking System 1 model assets from {repo_id}...")

                if not resolved_tok or not os.path.exists(resolved_tok):
                    resolved_tok = hf_hub_download(repo_id=repo_id, filename="tokenizer.json", etag_timeout=3)

                if not resolved_model or not os.path.exists(resolved_model):
                    resolved_model = hf_hub_download(repo_id=repo_id, filename="onnx/model_int8.onnx", etag_timeout=3)
            except Exception as e:
                logger.info(
                    f"System 1 model assets not cached on disk and hub download unavailable ({e}). "
                    "Claim evaluation will safely route to System 2."
                )
                self._is_ready = False
                return

        # 3. Load ONNX Runtime session with CPU optimizations
        try:
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 2
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                resolved_model,
                sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )
            self._tokenizer = Tokenizer.from_file(resolved_tok)
            self._is_ready = True
            logger.info(f"System 1 NLI Cross-Encoder successfully initialized with ONNX model: {resolved_model}")
        except Exception as e:
            logger.warning(f"Failed to initialize System 1 ONNX session: {e}. Falling back to System 2.")
            self._is_ready = False

    def predict_pair(self, premise: str, hypothesis: str) -> Optional[Dict[str, float]]:
        """
        Runs NLI inference on a (premise, hypothesis) pair.
        Returns: {"contradiction": float, "entailment": float, "neutral": float} or None if unavailable.
        """
        if not self.is_available:
            return None

        batch_res = self.predict_batch([(premise, hypothesis)])
        return batch_res[0] if batch_res else None

    def predict_batch(self, pairs: List[Tuple[str, str]]) -> List[Optional[Dict[str, float]]]:
        """
        Runs vectorized batch NLI inference over list of (premise, hypothesis) pairs.
        """
        if not self.is_available or not pairs:
            return [None] * len(pairs)

        try:
            encodings = [
                self._tokenizer.encode(premise, hypothesis)
                for premise, hypothesis in pairs
            ]

            max_len = min(max(len(e.ids) for e in encodings), 512)

            batch_size = len(pairs)
            input_ids = np.zeros((batch_size, max_len), dtype=np.int64)
            attention_mask = np.zeros((batch_size, max_len), dtype=np.int64)

            for i, enc in enumerate(encodings):
                length = min(len(enc.ids), max_len)
                input_ids[i, :length] = enc.ids[:length]
                attention_mask[i, :length] = 1

            # Prepare inputs according to model inputs
            model_inputs = {inp.name for inp in self._session.get_inputs()}
            feed_dict = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            if "token_type_ids" in model_inputs:
                feed_dict["token_type_ids"] = np.zeros_like(input_ids)

            ort_outputs = self._session.run(None, feed_dict)
            logits = ort_outputs[0]  # shape: (batch_size, 3)

            # Apply numerically stable Softmax
            exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
            probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

            results: List[Optional[Dict[str, float]]] = []
            for row in probs:
                results.append({
                    "contradiction": float(row[LABEL_CONTRADICTION]),
                    "entailment": float(row[LABEL_ENTAILMENT]),
                    "neutral": float(row[LABEL_NEUTRAL]),
                })
            return results
        except Exception as e:
            logger.warning(f"System 1 batch inference failed: {e}")
            return [None] * len(pairs)

    def triage_claim(
        self,
        claim_text: str,
        retrieved_chunks: List[RetrievedEvidenceChunk],
        claim_meta: Optional[Dict[str, Any]] = None,
        allow_contradiction: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Triages a claim against retrieved RAG chunks in ~10ms (0 LLM tokens):
        1. Fast Anchor Reflex: Direct attached URL or project name match with verified candidate artifacts.
        2. Fast NLI Cross-Encoder: Semantic entailment check with local ONNX model.
        - If clear match or high entailment -> Instant SUPPORTED/PARTIALLY_SUPPORTED
        - If ambiguous / closed-source / uncorroborated -> Returns None (escalates to System 2)
        """
        if not self.is_available or not retrieved_chunks:
            return None

        candidate_chunks = [c for c in retrieved_chunks[:3] if c.content and c.content.strip()]
        if not candidate_chunks:
            return None

        # 0. Deterministic Attribution Theft Guard:
        # If candidate claims to have built/created a repo where they authored 0 commits,
        # flag as CONTRADICTED immediately to prevent attribution fraud.
        claim_lower = claim_text.lower()
        if any(w in claim_lower for w in ["built", "created", "architected", "developed", "engineered", "authored", "implemented", "wrote"]):
            for chunk in candidate_chunks:
                cm = chunk.meta if isinstance(chunk.meta, dict) else {}
                cand_c = cm.get("candidate_commit_count")
                tot_c = cm.get("total_commit_count", 0)
                if cand_c is not None and tot_c > 5 and cand_c == 0:
                    return {
                        "verdict": "CONTRADICTED",
                        "confidence": 0.95,
                        "reasoning": f"Repository '{chunk.title}' has {tot_c} commits, but candidate authored 0 of them.",
                        "evidence_ids": [chunk.evidence_id],
                        "verified_by": "system_1_cross_encoder",
                    }

        # 1. Fast Anchor Reflex Check (Direct project/URL evidence corroboration)
        if claim_meta is not None:
            attached_url = (claim_meta.get("attached_url") or "").lower().strip()
            project_name = (claim_meta.get("project_name") or "").lower().strip()
            p_clean = re.sub(r'[\s_\-]', '', project_name)

            for chunk in retrieved_chunks:
                c_url = (chunk.url or "").lower()
                c_title = (chunk.title or "").lower()
                t_clean = re.sub(r'[\s_\-]', '', c_title)
                u_clean = re.sub(r'[\s_\-]', '', c_url)
                cm = chunk.meta or {}
                cand_commits = cm.get("candidate_commit_count", 1)

                url_match = bool(attached_url and (attached_url in c_url or c_url in attached_url))
                name_match = bool(len(p_clean) >= 3 and (p_clean in t_clean or p_clean in u_clean))

                if (url_match or name_match) and cand_commits > 0:
                    has_private = any(
                        re.search(p, claim_text, re.IGNORECASE)
                        for p in [r'\b\d+%\b', r'\b\d+\+\s*users\b', r'<\s*\d+']
                    )
                    verdict = "PARTIALLY_SUPPORTED" if has_private else "SUPPORTED"
                    return {
                        "verdict": verdict,
                        "confidence": 0.88,
                        "reasoning": f"Directly substantiated by candidate project artifact '{chunk.title}' in System 1 reflex triage.",
                        "evidence_ids": [chunk.evidence_id],
                        "verified_by": "system_1_cross_encoder",
                    }

        # 2. Fast NLI Cross-Encoder (Title + Excerpt)
        candidate_chunks = [c for c in retrieved_chunks[:3] if c.content and c.content.strip()]
        if not candidate_chunks:
            return None

        pairs = [
            (f"{c.title}\n{c.content[:800]}", claim_text)
            for c in candidate_chunks
        ]

        predictions = self.predict_batch(pairs)

        # Check for highest entailment or contradiction
        best_entailment_chunk = None
        max_entailment = 0.0

        best_contradiction_chunk = None
        max_contradiction = 0.0

        for chunk, pred in zip(candidate_chunks, predictions):
            if not pred:
                continue

            p_ent = pred.get("entailment", 0.0)
            p_contra = pred.get("contradiction", 0.0)

            if p_ent > max_entailment:
                max_entailment = p_ent
                best_entailment_chunk = chunk

            if p_contra > max_contradiction:
                max_contradiction = p_contra
                best_contradiction_chunk = chunk

        # 1. Clear Entailment (High Confidence)
        if max_entailment >= self.entailment_threshold and best_entailment_chunk:
            return {
                "verdict": "SUPPORTED",
                "confidence": round(max_entailment, 2),
                "reasoning": (
                    f"Corroborated by verified receipt in '{best_entailment_chunk.title}' "
                    f"(System 1 Cross-Encoder P(Entailment) = {max_entailment:.2f})."
                ),
                "evidence_ids": [best_entailment_chunk.evidence_id],
                "verified_by": "system_1_cross_encoder",
            }

        # 2. Strict Contradiction Guardrail (Only if allow_contradiction is enabled):
        # By default, System 1 acts strictly as a positive reflex filter (SUPPORTED).
        # Claims that are not confirmed by a partial chunk are NEVER marked as CONTRADICTED
        # here; they escalate safely to System 2 (deliberative evaluation) to avoid false negatives.
        can_contradict = self.allow_contradiction if allow_contradiction is None else allow_contradiction
        if can_contradict and max_contradiction >= self.contradiction_threshold and best_contradiction_chunk:
            is_valid_contradiction = True

            if claim_meta is not None:
                attached_url = claim_meta.get("attached_url")
                project_name = claim_meta.get("project_name")
                c_url = (best_contradiction_chunk.url or "").lower()
                c_title = (best_contradiction_chunk.title or "").lower()

                if attached_url:
                    u_clean = attached_url.rstrip("/").lower()
                    if u_clean not in c_url and c_url not in u_clean:
                        is_valid_contradiction = False
                elif project_name and len(project_name.strip()) >= 3:
                    p_stem = project_name.lower().strip().split()[0]
                    if len(p_stem) >= 3 and p_stem not in c_title and p_stem not in c_url:
                        is_valid_contradiction = False
                else:
                    # Unanchored claim with empty project/url: cannot be contradicted by arbitrary chunk
                    is_valid_contradiction = False

            # Require high retrieval relevance and low entailment across candidate chunks
            chunk_score = getattr(best_contradiction_chunk, "score", 1.0)
            if (chunk_score is not None and chunk_score < 0.70) or max_entailment >= 0.15:
                is_valid_contradiction = False

            if is_valid_contradiction:
                return {
                    "verdict": "CONTRADICTED",
                    "confidence": round(max_contradiction, 2),
                    "reasoning": (
                        f"Receipt in '{best_contradiction_chunk.title}' directly refutes claim "
                        f"(System 1 Cross-Encoder P(Contradiction) = {max_contradiction:.2f})."
                    ),
                    "evidence_ids": [best_contradiction_chunk.evidence_id],
                    "verified_by": "system_1_cross_encoder",
                }

        # Inconclusive / Ambiguous -> Route to System 2 (Deliberative LLM)
        return None
