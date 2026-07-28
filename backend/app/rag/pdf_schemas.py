"""
Pydantic schemas for PDF data extraction.

Each French notarial document type has a schema that defines
what fields to extract. The LLM uses these schemas to validate
extracted data before returning it.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Shared sub-models ─────────────────────────────────────────


class PersonnePhysique(BaseModel):
    """Natural person (individual)."""
    nom: str = ""
    prenom: str = ""
    date_naissance: Optional[str] = None
    nationalite: str = ""
    adresse: str = ""
    profession: str = ""


class PersonneMorale(BaseModel):
    """Legal entity (company)."""
    raison_sociale: str = ""
    siret: str = ""
    forme_juridique: str = ""
    siege_social: str = ""
    representant: str = ""


class BienImmobilier(BaseModel):
    """Property asset."""
    adresse: str = ""
    type_bien: str = ""  # appartement, maison, terrain, local_commercial
    surface_m2: Optional[float] = None
    lot_copropriete: Optional[str] = None
    reference_cadastrale: str = ""
    description: str = ""


class Montant(BaseModel):
    """Monetary amount."""
    montant: float = 0.0
    devise: str = "EUR"
    montant_lettres: str = ""


class DateInfo(BaseModel):
    """A date with context."""
    label: str = ""
    date: str = ""
    description: str = ""


# ── Document-type schemas ─────────────────────────────────────


class ActeVenteSchema(BaseModel):
    """Schema for deed of sale (acte de vente)."""
    type_acte: str = "vente"
    date_acte: Optional[str] = None
    notaire: str = ""
    vendeur: PersonnePhysique = Field(default_factory=PersonnePhysique)
    acheteur: PersonnePhysique = Field(default_factory=PersonnePhysique)
    bien: BienImmobilier = Field(default_factory=BienImmobilier)
    montant: Montant = Field(default_factory=Montant)
    conditions_suspensives: List[str] = []
    dates_importantes: List[DateInfo] = []
    clauses_speciales: List[str] = []
    frais_notaire: Optional[float] = None
    diagnostiques: List[str] = []


class PouvoirSchema(BaseModel):
    """Schema for power of attorney (procuration / pouvoir)."""
    type_acte: str = "pouvoir"
    date_acte: Optional[str] = None
    notaire: str = ""
    mandant: PersonnePhysique = Field(default_factory=PersonnePhysique)
    mandataire: PersonnePhysique = Field(default_factory=PersonnePhysique)
    etendue_pouvoir: str = ""
    duree: Optional[str] = None
    date_expiration: Optional[str] = None
    revocation_possible: bool = True
    clauses_speciales: List[str] = []


class TestamentSchema(BaseModel):
    """Schema for last will and testament (testament)."""
    type_acte: str = "testament"
    date_acte: Optional[str] = None
    notaire: str = ""
    testateur: PersonnePhysique = Field(default_factory=PersonnePhysique)
    legataires: List[PersonnePhysique] = []
    biens: List[str] = []
    legataire_universel: Optional[str] = None
    executeur_testamentaire: Optional[str] = None
    clauses_speciales: List[str] = []


class ContratSchema(BaseModel):
    """Schema for general contracts."""
    type_acte: str = "contrat"
    date_acte: Optional[str] = None
    parties: List[PersonnePhysique] = []
    parties_morales: List[PersonneMorale] = []
    objet: str = ""
    duree: Optional[str] = None
    montant: Montant = Field(default_factory=Montant)
    clauses_principales: List[str] = []
    dates_importantes: List[DateInfo] = []
    lieu_signature: str = ""


class ActeSocieteSchema(BaseModel):
    """Schema for corporate acts."""
    type_acte: str = "acte_societe"
    date_acte: Optional[str] = None
    notaire: str = ""
    societe: PersonneMorale = Field(default_factory=PersonneMorale)
    associes: List[PersonnePhysique] = []
    capital_social: Montant = Field(default_factory=Montant)
    objet_social: str = ""
    duree_societe: Optional[str] = None
    gerant: Optional[str] = None
    clauses_statutaires: List[str] = []


class AutreDocumentSchema(BaseModel):
    """Fallback schema for unidentified document types."""
    type_acte: str = "autre"
    date_acte: Optional[str] = None
    parties_principales: List[str] = []
    objet: str = ""
    montants: List[Montant] = []
    dates_importantes: List[DateInfo] = []
    clauses: List[str] = []
    resume: str = ""


# ── Registry ───────────────────────────────────────────────────


EXTRACTION_SCHEMAS: Dict[str, Any] = {
    "vente": ActeVenteSchema,
    "pouvoir": PouvoirSchema,
    "testament": TestamentSchema,
    "contrat": ContratSchema,
    "acte_societe": ActeSocieteSchema,
    "autre": AutreDocumentSchema,
}

SCHEMA_LABELS: Dict[str, str] = {
    "vente": "Deed of Sale (Acte de Vente)",
    "pouvoir": "Power of Attorney (Procuration)",
    "testament": "Last Will & Testament",
    "contrat": "General Contract",
    "acte_societe": "Corporate Act (Acte de Société)",
    "autre": "Other / Unidentified",
}


def get_schema(doc_type: str) -> Any:
    """Get the Pydantic schema class for a document type."""
    return EXTRACTION_SCHEMAS.get(doc_type, AutreDocumentSchema)


def get_all_schema_info() -> List[Dict[str, Any]]:
    """Return metadata about all available schemas."""
    result = []
    for doc_type, schema_cls in EXTRACTION_SCHEMAS.items():
        fields = {}
        for name, field in schema_cls.model_fields.items():
            fields[name] = {
                "type": str(field.annotation.__name__ if hasattr(field.annotation, '__name__') else str(field.annotation)),
                "required": field.is_required(),
                "description": field.description or "",
            }
        result.append({
            "id": doc_type,
            "label": SCHEMA_LABELS.get(doc_type, doc_type),
            "fields": fields,
        })
    return result
