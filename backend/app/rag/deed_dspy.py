"""
DSPy-optimized clause drafting for notarial deeds.

Uses DSPy (Declarative Self-improving Python) to define
a structured signature for legal clause drafting, then
optionally optimizes the prompt with BootstrapFewShot.

Architecture:
  1. RedactionClause signature — DSPy InputField/OutputField
  2. DeedDraftingModule — wraps the signature with LM config
  3. optimize_prompt() — BootstrapFewShot compilation
  4. draft_clause() — inference with (optionally) optimized module
"""

import logging
import os
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.runtime_config import get_active_api_key, get_active_model, get_active_api_base, get_active_provider

logger = logging.getLogger(__name__)

# Lazy DSPy import — slow to load
_dspy_available = False
try:
    import dspy
    _dspy_available = True
except ImportError:
    logger.warning("dspy-ai not installed. Use: pip install 'dspy-ai>=2.6'")


def _init_dspy_lm() -> None:
    """Configure DSPy to use the same LiteLLM provider as the rest of the app."""
    if not _dspy_available:
        return

    api_key = get_active_api_key()
    model = get_active_model()  # e.g. "openai/deepseek-v4-flash"
    api_base = get_active_api_base()

    if not api_key:
        logger.warning("No API key configured for DSPy")
        return

    # DSPy expects OpenAI-compatible format
    # Strip the provider prefix from model name
    if "/" in model:
        bare_model = model.split("/", 1)[1]
    else:
        bare_model = model

    lm_kwargs: Dict[str, Any] = {
        "model": bare_model,
        "api_key": api_key,
        "model_type": "chat",
    }

    if api_base:
        lm_kwargs["api_base"] = api_base

    try:
        lm = dspy.LM(**lm_kwargs)
        dspy.configure(lm=lm)
        logger.info("DSPy configured: model=%s, api_base=%s", bare_model, api_base or "default")
    except Exception as e:
        logger.warning("DSPy LM configuration failed: %s", e)


# ── DSPy Signature ────────────────────────────────────────────
# Defines the input/output schema for clause drafting.
# DSPy uses this to automatically optimize the prompt.

if _dspy_available:

    class RedactionClause(dspy.Signature):
        """Draft a legal clause in formal French notarial style.

        Given the clause type and context, produce a properly
        formatted legal clause suitable for a notarial deed.
        """
        type_clause: str = dspy.InputField(desc="Type: prix, delai, condition_suspensive, renonciation, garantie, autre")
        contexte: str = dspy.InputField(desc="Context of the notarial act (parties, property, amounts, dates)")
        references: str = dspy.InputField(desc="Previous similar clauses as reference (optional)")
        clause: str = dspy.OutputField(desc="Drafted clause in formal French notarial language")

    class DeedDraftingModule(dspy.Module):
        """DSPy module for deed clause drafting."""

        def __init__(self):
            super().__init__()
            self.redaction = dspy.ChainOfThought(RedactionClause)

        def forward(self, type_clause: str, contexte: str, references: str = "") -> Dict[str, str]:
            result = self.redaction(
                type_clause=type_clause,
                contexte=contexte,
                references=references or "No previous examples available.",
            )
            return {"clause": result.clause}

else:
    # Fallback when DSPy is not installed
    class RedactionClause:
        pass

    class DeedDraftingModule:
        def __init__(self):
            self.optimized = False

        def forward(self, type_clause: str, contexte: str, references: str = "") -> Dict[str, str]:
            return {"clause": "DSPy not available. Install dspy-ai for optimized drafting."}


# ── Optimizer ─────────────────────────────────────────────────

_optimized_module: Optional[DeedDraftingModule] = None


async def optimize_prompt(
    train_examples: Optional[List[Dict[str, str]]] = None,
    num_fewshot: int = 5,
) -> Dict[str, Any]:
    """
    Optimize the clause drafting prompt using DSPy's BootstrapFewShot.

    Args:
        train_examples: List of {"type_clause": ..., "contexte": ..., "clause": ...}
        num_fewshot: Number of few-shot examples to use

    Returns:
        Dict with optimization status
    """
    global _optimized_module

    if not _dspy_available:
        return {"status": "error", "message": "dspy-ai not installed"}

    _init_dspy_lm()

    # Use default training examples if none provided
    if train_examples is None:
        train_examples = _DEFAULT_TRAIN_EXAMPLES

    # Create DSPy examples
    examples = []
    for ex in train_examples[:50]:  # Max 50 examples
        examples.append(dspy.Example(
            type_clause=ex.get("type_clause", "general"),
            contexte=ex.get("contexte", ""),
            references=ex.get("references", ""),
            clause=ex.get("clause", ""),
        ).with_inputs("type_clause", "contexte", "references"))

    if not examples:
        return {"status": "error", "message": "No training examples provided"}

    try:
        from dspy.teleprompt import BootstrapFewShot

        # Define a simple metric: exact match (placeholder — in production use semantic similarity)
        def legal_accuracy(gold, pred, trace=None) -> float:
            if not pred or not pred.clause:
                return 0.0
            # Simple length + keyword heuristic
            gold_len = len(gold.clause)
            pred_len = len(pred.clause)
            length_score = 1.0 - min(abs(gold_len - pred_len) / max(gold_len, 1), 1.0)
            # Keyword overlap
            gold_words = set(gold.clause.lower().split()[:50])
            pred_words = set(pred.clause.lower().split()[:50])
            overlap = len(gold_words & pred_words) / max(len(gold_words | pred_words), 1)
            return 0.3 * length_score + 0.7 * overlap

        teleprompter = BootstrapFewShot(
            metric=legal_accuracy,
            max_bootstrapped_demos=num_fewshot,
            max_labeled_demos=num_fewshot,
        )

        module = DeedDraftingModule()
        _optimized_module = teleprompter.compile(module, trainset=examples)

        logger.info("DSPy optimization complete: %d examples, %d few-shot", len(examples), num_fewshot)
        return {
            "status": "success",
            "examples": len(examples),
            "fewshot": num_fewshot,
        }

    except Exception as e:
        logger.error("DSPy optimization failed: %s", e)
        return {"status": "error", "message": str(e)}


# ── Inference ─────────────────────────────────────────────────


async def draft_clause(
    type_clause: str,
    contexte: str,
    references: str = "",
    use_optimized: bool = True,
) -> Dict[str, Any]:
    """
    Draft a legal clause using DSPy (optimized or base module).

    Args:
        type_clause: Type of clause (prix, delai, condition_suspensive, etc.)
        contexte: Context of the notarial act
        references: Previous similar clauses as reference
        use_optimized: Whether to use the optimized module

    Returns:
        Dict with clause and metadata
    """
    if not _dspy_available:
        return {
            "clause": "DSPy not available. Install dspy-ai for optimized drafting.",
            "optimized": False,
            "model": "none",
        }

    _init_dspy_lm()

    module = _optimized_module if (use_optimized and _optimized_module is not None) else DeedDraftingModule()
    result = module.forward(
        type_clause=type_clause,
        contexte=contexte,
        references=references,
    )

    return {
        "clause": result.get("clause", ""),
        "optimized": use_optimized and _optimized_module is not None,
        "model": get_active_model(),
    }


# ── Default training examples ─────────────────────────────────

_DEFAULT_TRAIN_EXAMPLES: List[Dict[str, str]] = [
    {
        "type_clause": "prix",
        "contexte": "Vente appartement Paris 5e, 75m2, vendeur Martin, acheteur Dubois",
        "clause": "Le prix de vente est fixé à la somme de [MONTANT] euros, que l'acquéreur s'oblige à payer au vendeur à la date de la signature de l'acte authentique, par chèque de banque ou virement bancaire.",
        "references": "Clause de prix standard pour vente immobilière",
    },
    {
        "type_clause": "delai",
        "contexte": "Signature acte prévue dans 30 jours",
        "clause": "La signature de l'acte authentique devra intervenir dans un délai de [NOMBRE] jours à compter de la présente promesse, sauf prorogation expresse convenue entre les parties.",
        "references": "Délai standard de réalisation",
    },
    {
        "type_clause": "condition_suspensive",
        "contexte": "Achat avec prêt immobilier",
        "clause": "La présente promesse de vente est conclue sous la condition suspensive de l'obtention par l'acquéreur d'un prêt d'un montant de [MONTANT] euros, remboursable sur [DUREE] ans au taux nominal de [TAUX]%. À défaut d'obtention de ce prêt, la promesse sera nulle et non avenue.",
        "references": "Condition suspensive standard d'obtention de prêt",
    },
    {
        "type_clause": "renonciation",
        "contexte": "Vendeur souhaite renoncer au délai de rétractation",
        "clause": "Le vendeur renonce expressément au bénéfice du délai de rétractation prévu par l'article L. 271-1 du Code de la construction et de l'habitation, et demande la réitération de la présente vente par acte authentique dans les plus brefs délais.",
        "references": "Renonciation au délai de rétractation",
    },
    {
        "type_clause": "garantie",
        "contexte": "Vente avec garantie des vices cachés",
        "clause": "Le vendeur garantit l'acquéreur contre tous vices cachés affectant le bien vendu, conformément aux dispositions des articles 1641 et suivants du Code civil. Cette garantie s'applique pendant un délai de [NOMBRE] ans à compter de la signature de l'acte.",
        "references": "Garantie légale des vices cachés",
    },
]
