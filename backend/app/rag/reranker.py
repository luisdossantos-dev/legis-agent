"""
Cross-encoder reranker for improving retrieval precision.

After the initial retrieval (semantic + BM25), a cross-encoder model
re-ranks the top-N candidates by computing query-document relevance
scores. This typically improves precision by 20-30%.

The cross-encoder is a small Transformer model (≈80 MB) that runs
locally. It is loaded lazily on the first reranking call.

Graceful degradation:
  - If torch/transformers are not installed → returns results as-is
  - If the model fails to load → returns results as-is (logs a warning)
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default model: small, fast, good quality
_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# How many candidates to fetch before reranking
_RERANK_CANDIDATES = 20


class Reranker:
    """Cross-encoder reranker with automatic fallback.

    Usage:
        reranker = Reranker()
        # After initial search with top_k=RERANK_CANDIDATES
        reranked = await reranker.rerank(query, results)
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
        self._device = None
        self._available = False
        self._init_error: Optional[str] = None

    def _load_model(self) -> None:
        """Lazy-load the cross-encoder model on first use."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            logger.info(
                "Loading cross-encoder reranker: %s (this may take a few seconds)",
                self.model_name,
            )

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            )
            self._model.eval()
            self._model.to(self._device)

            self._available = True
            logger.info(
                "Reranker loaded: %s (device=%s)",
                self.model_name,
                self._device,
            )

        except ImportError:
            self._init_error = (
                "torch/transformers not installed. "
                "Install with: pip install torch transformers"
            )
            logger.warning(self._init_error)

        except Exception as e:
            self._init_error = f"Failed to load reranker: {e}"
            logger.warning(self._init_error)

    async def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Re-rank search results using a cross-encoder.

        Args:
            query: The original search query.
            results: Candidate results from the initial retrieval.
            top_k: Number of results to return after reranking.

        Returns:
            Re-ranked results with updated scores.
        """
        if not results:
            return results

        # Load model on first call
        if self._model is None:
            self._load_model()

        # If model isn't available, return results as-is
        if not self._available:
            for r in results:
                r["reranked"] = False
            return results[:top_k]

        import torch

        try:
            # Prepare query-document pairs
            pairs = [[query, r["text"]] for r in results]

            # Tokenize and score
            inputs = self._tokenizer(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512,
            ).to(self._device)

            with torch.no_grad():
                logits = self._model(**inputs).logits
                scores = logits.squeeze(-1).tolist()

            # Handle single-result edge case
            if isinstance(scores, float):
                scores = [scores]

            # Update scores and sort
            for r, score in zip(results, scores):
                r["score"] = round(float(score), 4)
                r["reranked"] = True

            results.sort(key=lambda x: x["score"], reverse=True)

            logger.debug(
                "Reranked %d candidates → top-%d",
                len(results),
                top_k,
            )

            return results[:top_k]

        except Exception as e:
            logger.warning("Reranking failed (non-critical): %s", e)
            for r in results:
                r["reranked"] = False
            return results[:top_k]


# Singleton
reranker = Reranker()
