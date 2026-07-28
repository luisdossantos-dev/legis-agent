"""
Risk checklist templates for notarial clause review.

Each clause type has:
  - required_elements: elements that MUST appear
  - common_issues: typical drafting errors
  - risk_patterns: high-risk language patterns
  - legal_references: simplified French legal references
"""

from typing import Any, Dict, List

from app.core.cache import ttl_cache

# ── Clause type registry ───────────────────────────────────────

CLAUSE_TYPES: List[str] = [
    "prix",
    "delai",
    "condition_suspensive",
    "renonciation",
    "garantie",
    "penalite",
    "autre",
]

CLAUSE_TYPE_LABELS: Dict[str, str] = {
    "prix": "Price & Payment Terms",
    "delai": "Deadline & Time Limits",
    "condition_suspensive": "Suspensive Conditions",
    "renonciation": "Waiver of Rights",
    "garantie": "Warranties & Guarantees",
    "penalite": "Penalty Clauses",
    "autre": "Other / General",
}


def _get_checklist(clause_type: str) -> Dict[str, Any]:
    """Return the full checklist for a clause type."""
    base = {
        "required_elements": _REQUIRED.get(clause_type, _REQUIRED["autre"]),
        "common_issues": _ISSUES.get(clause_type, _ISSUES["autre"]),
        "risk_patterns": _RISK_PATTERNS.get(clause_type, _RISK_PATTERNS["autre"]),
        "legal_references": _LEGAL_REFERENCES.get(clause_type, {}),
    }
    # Add global cross-cutting checks
    base["cross_cutting"] = _CROSS_CUTTING
    return base


@ttl_cache(ttl_seconds=300)
def get_all_checklist_types() -> List[Dict[str, Any]]:
    """Return summary of all clause types with their required element counts (cached 5 min)."""
    return [
        {
            "id": t,
            "label": CLAUSE_TYPE_LABELS[t],
            "required_count": len(_REQUIRED.get(t, _REQUIRED["autre"])),
            "issue_count": len(_ISSUES.get(t, _ISSUES["autre"])),
        }
        for t in CLAUSE_TYPES
    ]


@ttl_cache(ttl_seconds=300)
def get_checklist_for(clause_type: str) -> Dict[str, Any]:
    """Get the checklist for a specific clause type (cached 5 min)."""
    if clause_type not in CLAUSE_TYPES:
        clause_type = "autre"
    return _get_checklist(clause_type)


# ── Required elements per clause type ──────────────────────────

_REQUIRED: Dict[str, List[str]] = {
    "prix": [
        "Montant en toutes lettres et en chiffres",
        "Devise (EUR sauf exception)",
        "Date et modalités de paiement",
        "Moyen de paiement (virement, chèque, etc.)",
        "Pénalités de retard explicites",
        "Identité du bénéficiaire du paiement",
    ],
    "delai": [
        "Date de début du délai",
        "Date de fin du délai (ou durée précise)",
        "Conséquence du non-respect du délai",
        "Mécanisme de prorogation éventuelle",
        "Notification en cas de retard",
    ],
    "condition_suspensive": [
        "Description précise de la condition",
        "Délai de réalisation de la condition",
        "Conséquence si la condition n'est pas réalisée",
        "Partie bénéficiaire de la condition",
        "Modalités de notification de la réalisation",
    ],
    "renonciation": [
        "Droit auquel il est renoncé (identification précise)",
        "Portée de la renonciation (totale/partielle)",
        "Caractère irrévocable ou révocable",
        "Délai de réflexion / rétractation le cas échéant",
        "Signature expresse de la partie renonçante",
    ],
    "garantie": [
        "Objet de la garantie",
        "Durée de la garantie",
        "Étendue de la garantie",
        "Exclusions de garantie",
        "Procédure de mise en œuvre",
        "Limitation de responsabilité éventuelle",
    ],
    "penalite": [
        "Montant ou mode de calcul de la pénalité",
        "Déclencheur de la pénalité (retard, inexécution, etc.)",
        "Plafond éventuel de la pénalité",
        "Bénéficiaire de la pénalité",
        "Révision possible (indexation, etc.)",
    ],
    "autre": [
        "Identification des parties concernées",
        "Objet clair et précis",
        "Date d'effet",
        "Durée / échéance",
        "Conséquences juridiques",
        "Signature / acceptation des parties",
    ],
}

# ── Common issues per clause type ──────────────────────────────

_ISSUES: Dict[str, List[Dict[str, str]]] = {
    "prix": [
        {"pattern": "Montant en chiffres seulement", "severity": "high",
         "description": "Le montant doit être écrit en toutes lettres ET en chiffres (art. 1326 C. civ.)"},
        {"pattern": "Pas de devise spécifiée", "severity": "medium",
         "description": "Indiquer la devise pour éviter toute ambiguïté"},
        {"pattern": "Délai de paiement imprécis", "severity": "high",
         "description": "Le délai de paiement doit être déterminé ou déterminable"},
        {"pattern": "Absence de pénalités de retard", "severity": "medium",
         "description": "Les pénalités de retard sont recommandées (L. 441-10 C. com.)"},
    ],
    "delai": [
        {"pattern": "Date de début absente", "severity": "high",
         "description": "Le point de départ du délai doit être explicitement mentionné"},
        {"pattern": "Délai non quantifié", "severity": "high",
         "description": "Utiliser un nombre de jours ou une date précise — 'dans un délai raisonnable' est trop vague"},
        {"pattern": "Absence de sanction", "severity": "medium",
         "description": "Prévoir les conséquences du non-respect du délai"},
    ],
    "condition_suspensive": [
        {"pattern": "Condition potestative", "severity": "high",
         "description": "Une condition purement potestative est nulle (art. 1304-2 C. civ.)"},
        {"pattern": "Délai non précisé", "severity": "high",
         "description": "La condition doit être réalisée dans un délai déterminé"},
        {"pattern": "Partie bénéficiaire non identifiée", "severity": "medium",
         "description": "Préciser quelle partie bénéficie de la condition"},
    ],
    "renonciation": [
        {"pattern": "Droit non identifié", "severity": "high",
         "description": "Le droit auquel il est renoncé doit être précisément identifié"},
        {"pattern": "Renonciation générale", "severity": "high",
         "description": "Une renonciation générale est nulle — elle doit être spécifique (art. 1170 C. civ.)"},
        {"pattern": "Absence de délai de rétractation", "severity": "medium",
         "description": "Prévoir un délai de rétractation si requis par la loi"},
    ],
    "garantie": [
        {"pattern": "Étendue non définie", "severity": "high",
         "description": "L'étendue de la garantie doit être précisément décrite"},
        {"pattern": "Exclusions absentes", "severity": "medium",
         "description": "Les exclusions doivent être clairement listées"},
        {"pattern": "Durée indéterminée", "severity": "high",
         "description": "La garantie doit avoir une durée déterminée ou déterminable"},
    ],
    "penalite": [
        {"pattern": "Montant non spécifié", "severity": "high",
         "description": "Le montant ou le mode de calcul doit être précisé"},
        {"pattern": "Pénalité manifestement excessive", "severity": "high",
         "description": "Une pénalité excessive peut être réduite par le juge (art. 1231-5 C. civ.)"},
        {"pattern": "Déclencheur imprécis", "severity": "medium",
         "description": "Préciser clairement ce qui déclenche la pénalité"},
    ],
    "autre": [
        {"pattern": "Parties non identifiées", "severity": "high",
         "description": "Toutes les parties doivent être clairement identifiées"},
        {"pattern": "Objet vague", "severity": "high",
         "description": "L'objet de la clause doit être déterminé ou déterminable"},
        {"pattern": "Absence de date", "severity": "medium",
         "description": "La date d'effet doit être mentionnée"},
    ],
}

# ── High-risk language patterns ─────────────────────────────────

_RISK_PATTERNS: Dict[str, List[Dict[str, Any]]] = {
    "prix": [
        {"name": "prix_approximatif", "risk_level": "red",
         "description": "Termes vagues comme 'environ', 'approximativement' pour le prix"},
        {"name": "indexation_manquante", "risk_level": "yellow",
         "description": "Paiement échelonné sans clause d'indexation"},
    ],
    "delai": [
        {"name": "delai_raisonnable", "risk_level": "red",
         "description": "'Délai raisonnable' sans précision — source de litige"},
        {"name": "prorogation_unilaterale", "risk_level": "yellow",
         "description": "Prorogation laissée à la discrétion d'une seule partie"},
    ],
    "condition_suspensive": [
        {"name": "condition_potestative", "risk_level": "red",
         "description": "Condition dépendant de la volonté d'une seule partie — nulle"},
        {"name": "condition_impossible", "risk_level": "red",
         "description": "Condition impossible à réaliser — réputée non écrite"},
    ],
    "renonciation": [
        {"name": "renonciation_globale", "risk_level": "red",
         "description": "Renonciation à tous droits sans spécification"},
        {"name": "absence_signature_expresse", "risk_level": "red",
         "description": "Renonciation sans signature expresse de la partie renonçante"},
    ],
    "garantie": [
        {"name": "garantie_illimitee", "risk_level": "yellow",
         "description": "Garantie sans plafond ni limitation dans le temps"},
        {"name": "exclusion_cachee", "risk_level": "red",
         "description": "Exclusion non apparente dans une clause de garantie"},
    ],
    "penalite": [
        {"name": "penalite_excessive", "risk_level": "yellow",
         "description": "Pénalité > 10% du montant — risque de réduction judiciaire"},
        {"name": "penalite_sans_plafond", "risk_level": "yellow",
         "description": "Pénalités cumulatives sans plafond"},
    ],
    "autre": [
        {"name": "langage_ambigu", "risk_level": "yellow",
         "description": "Termes ambigus pouvant donner lieu à interprétation contradictoire"},
        {"name": "contradiction_interne", "risk_level": "red",
         "description": "Clause en contradiction avec d'autres clauses du document"},
    ],
}

# ── Legal references (simplified French civil code) ────────────

_LEGAL_REFERENCES: Dict[str, Dict[str, str]] = {
    "prix": {
        "art_1326": "Art. 1326 C. civ. — Mentions manuscrites pour les actes sous signature privée",
        "art_1343": "Art. 1343 C. civ. — Modalités de paiement",
        "L_441_10": "L. 441-10 C. com. — Pénalités de retard",
    },
    "delai": {
        "art_1304": "Art. 1304-1 C. civ. — Délai pour l'exécution de l'obligation",
        "art_1217": "Art. 1217 C. civ. — Sanctions de l'inexécution",
    },
    "condition_suspensive": {
        "art_1304_2": "Art. 1304-2 C. civ. — Nullité de la condition potestative",
        "art_1304_3": "Art. 1304-3 C. civ. — Condition réputée accomplie",
        "art_1304_6": "Art. 1304-6 C. civ. — Rétroactivité de la condition",
    },
    "renonciation": {
        "art_1170": "Art. 1170 C. civ. — Renonciation générale nulle",
        "art_1171": "Art. 1171 C. civ. — Clause abusive",
    },
    "garantie": {
        "art_1641": "Art. 1641 C. civ. — Garantie des vices cachés",
        "art_1648": "Art. 1648 C. civ. — Délai pour agir en garantie",
    },
    "penalite": {
        "art_1231_5": "Art. 1231-5 C. civ. — Réduction des pénalités excessives",
        "art_1231_6": "Art. 1231-6 C. civ. — Intérêts moratoires",
    },
    "autre": {},
}

# ── Cross-cutting checks (apply to all clause types) ───────────

_CROSS_CUTTING: List[Dict[str, Any]] = [
    {
        "id": "langue_claire",
        "description": "Le langage utilisé est clair et compréhensible",
        "risk_if_missing": "yellow",
    },
    {
        "id": "aucune_contradiction",
        "description": "La clause n'est pas en contradiction avec le reste du document",
        "risk_if_missing": "red",
    },
    {
        "id": "parties_identifiees",
        "description": "Les parties concernées sont identifiables",
        "risk_if_missing": "red",
    },
    {
        "id": "date_effet",
        "description": "La date d'effet est précisée",
        "risk_if_missing": "yellow",
    },
    {
        "id": "conforme_ordre_public",
        "description": "La clause respecte l'ordre public (n'est pas abusive)",
        "risk_if_missing": "red",
    },
]
