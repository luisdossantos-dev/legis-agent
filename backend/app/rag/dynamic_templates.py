"""
Dynamic template library for notarial acts.

Each template has placeholders matching the fields in the
corresponding Pydantic schema from act_schemas.py.

Templates use {field_name} or {nested.field} syntax for
hydration. The template engine resolves these from the
validated Pydantic model.
"""

from typing import Any, Dict, List, Optional

from app.models.act_schemas import ACT_TYPE_LABELS, ACT_SCHEMA_REGISTRY

# ── Template definitions ──────────────────────────────────────
# Each entry maps an act_type to its template(s).
# {placeholders} are resolved from the validated Pydantic model.

DYNAMIC_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "vente": [
        {
            "name": "acte_vente_standard",
            "description": "Standard deed of sale for real estate property",
            "language": "fr",
            "subject": "Acte de Vente — {bien.adresse}",
            "body": """ACTE DE VENTE

Par devant Maître {notaire}, notaire à la résidence de [Ville], soussigné,

A comparu :

{vendeur.prenom} {vendeur.nom}, né(e) le {vendeur.date_naissance}, de nationalité {vendeur.nationalite},
demeurant {vendeur.adresse}, ci-après dénommé(e) "le VENDEUR",

D'une part ;

ET

{acheteur.prenom} {acheteur.nom}, né(e) le {acheteur.date_naissance}, de nationalité {acheteur.nationalite},
demeurant {acheteur.adresse}, ci-après dénommé(e) "l'ACHETEUR",

D'autre part ;

IL A ETE EXPOSE ET CONVENU CE QUI SUIT :

Article 1 — Désignation du bien
Le VENDEUR vend à l'ACHETEUR, qui accepte, le bien immobilier situé
{bien.adresse}, consistant en un {bien.type_bien} d'une surface de {bien.surface_m2} m².
{bien.description_cadastrale}

Article 2 — Prix
Le prix de vente est fixé à la somme de {montant.montant} EUR.
{montant.lettres}

Article 3 — Conditions suspensives
{conditions_suspensives}

Article 4 — Clauses particulières
{clauses_particulieres}

Fait à [Ville], le {acte_date}
Maître {notaire}""",
            "required_fields": [
                "vendeur.nom", "vendeur.prenom", "acheteur.nom", "acheteur.prenom",
                "bien.adresse", "bien.type_bien", "bien.surface_m2", "montant.montant",
            ],
        },
    ],
    "pouvoir": [
        {
            "name": "acte_pouvoir_standard",
            "description": "Standard power of attorney",
            "language": "fr",
            "subject": "Pouvoir — {mandant.prenom} {mandant.nom} à {mandataire.prenom} {mandataire.nom}",
            "body": """POUVOIR

Par devant Maître {notaire}, notaire à la résidence de [Ville], soussigné,

A comparu :

{mandant.prenom} {mandant.nom}, né(e) le {mandant.date_naissance}, de nationalité {mandant.nationalite},
demeurant {mandant.adresse}, ci-après dénommé(e) "le MANDANT",

Lequel a par les présentes constitué pour son mandataire :

{mandataire.prenom} {mandataire.nom}, né(e) le {mandataire.date_naissance}, de nationalité {mandataire.nationalite},
demeurant {mandataire.adresse}, ci-après dénommé(e) "le MANDATAIRE",

Auxquels il confère les pouvoirs suivants :

{etendue_pouvoirs}

Le présent pouvoir est donné pour une durée de {duree}.
{specialite}

Fait à [Ville], le {acte_date}
Maître {notaire}""",
            "required_fields": [
                "mandant.nom", "mandant.prenom", "mandataire.nom", "mandataire.prenom",
                "etendue_pouvoirs",
            ],
        },
    ],
    "testament": [
        {
            "name": "acte_testament_standard",
            "description": "Standard last will and testament",
            "language": "fr",
            "subject": "Testament — {testateur.prenom} {testateur.nom}",
            "body": """TESTAMENT

Par devant Maître {notaire}, notaire à la résidence de [Ville], soussigné,

A comparu :

{testateur.prenom} {testateur.nom}, né(e) le {testateur.date_naissance}, de nationalité {testateur.nationalite},
demeurant {testateur.adresse}, ci-après dénommé(e) "le TESTATEUR",

Lequel a dicté son testament en la forme authentique ainsi qu'il suit :

Article 1 — Révocation
Je révoque expressément tous testaments et codicilles antérieurs.

Article 2 — Legs
Je lègue à :
{legataires}

Article 3 — Biens
{biens}

{clauses_speciales}

Fait à [Ville], le {acte_date}
Maître {notaire}""",
            "required_fields": [
                "testateur.nom", "testateur.prenom",
                "legataires", "biens",
            ],
        },
    ],
    "mariage": [
        {
            "name": "acte_mariage_standard",
            "description": "Standard marriage contract",
            "language": "fr",
            "subject": "Contrat de Mariage — {conjoint1.prenom} {conjoint1.nom} et {conjoint2.prenom} {conjoint2.nom}",
            "body": """CONTRAT DE MARIAGE

Par devant Maître {notaire}, notaire à la résidence de [Ville], soussigné,

Ont comparu :

{conjoint1.prenom} {conjoint1.nom}, né(e) le {conjoint1.date_naissance}, de nationalité {conjoint1.nationalite},
{conjoint1.adresse}

ET

{conjoint2.prenom} {conjoint2.nom}, né(e) le {conjoint2.date_naissance}, de nationalité {conjoint2.nationalite},
{conjoint2.adresse}

Lesquels ont arrêté le régime matrimonial suivant :

Régime choisi : {regime_matrimonial}

Apports du conjoint 1 :
{apports_conjoint1}

Apports du conjoint 2 :
{apports_conjoint2}

{clauses_particulieres}

Fait à [Ville], le {acte_date}
Maître {notaire}""",
            "required_fields": [
                "conjoint1.nom", "conjoint1.prenom", "conjoint2.nom", "conjoint2.prenom",
                "regime_matrimonial",
            ],
        },
    ],
    "general": [
        {
            "name": "acte_general_standard",
            "description": "Generic notarial act",
            "language": "fr",
            "subject": "Acte — {objet}",
            "body": """ACTE NOTARIAL

Par devant Maître {notaire}, notaire à la résidence de [Ville], soussigné,

Ont comparu :

{parties}

Objet : {objet}

{montant.montant}

Fait à [Ville], le {acte_date}
Maître {notaire}""",
            "required_fields": [
                "objet",
            ],
        },
    ],
}


def get_templates_for_act(act_type: str) -> List[Dict[str, Any]]:
    """Get available templates for an act type."""
    return DYNAMIC_TEMPLATES.get(act_type, DYNAMIC_TEMPLATES.get("general", []))


def get_all_template_info() -> List[Dict[str, Any]]:
    """Return metadata about all available templates."""
    result = []
    for act_type, templates in DYNAMIC_TEMPLATES.items():
        for t in templates:
            result.append({
                "act_type": act_type,
                "act_label": ACT_TYPE_LABELS.get(act_type, act_type),
                "name": t["name"],
                "description": t["description"],
                "language": t["language"],
                "required_fields": t["required_fields"],
                "schema_fields": list(ACT_SCHEMA_REGISTRY.get(act_type, {}).model_fields.keys())
                    if act_type in ACT_SCHEMA_REGISTRY else [],
            })
    return result
