"""
Pydantic schemas for notarial act types.

Each act type defines its required fields with types, formats,
and validation. The schemas are used by the template engine to
validate input BEFORE rendering, preventing invalid documents.

Reusable sub-types:
  - PersonnePhysique: Individual person
  - PersonneMorale: Legal entity (company)
  - BienImmobilier: Real estate property
  - Euro: Money amount with validation
"""

from datetime import date as _date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Date = _date


# ── Reusable sub-types ────────────────────────────────────────


class PersonnePhysique(BaseModel):
    """Individual person (physical person)."""
    nom: str = Field(..., min_length=1, max_length=100, description="Last name / surname")
    prenom: str = Field(..., min_length=1, max_length=100, description="First name")
    date_naissance: Date = Field(..., description="Date of birth (YYYY-MM-DD)")
    nationalite: str = Field(default="Française", max_length=50, description="Nationality")
    adresse: str = Field(..., min_length=5, max_length=300, description="Full address")
    profession: Optional[str] = Field(default=None, max_length=100, description="Occupation")


class PersonneMorale(BaseModel):
    """Legal entity (company, association, etc.)."""
    raison_sociale: str = Field(..., min_length=1, max_length=200, description="Company name")
    siret: str = Field(..., pattern=r"^\d{14}$", description="SIRET number (14 digits)")
    adresse_siege: str = Field(..., min_length=5, max_length=300, description="Registered office address")
    representant: PersonnePhysique = Field(..., description="Legal representative")
    forme_juridique: str = Field(default="SARL", max_length=50, description="Legal form (SARL, SAS, SA, etc.)")


class BienImmobilier(BaseModel):
    """Real estate property."""
    adresse: str = Field(..., min_length=5, max_length=300, description="Property address")
    type_bien: Literal["appartement", "maison", "terrain", "local_commercial"] = Field(
        ..., description="Property type (appartement, maison, terrain, local_commercial)"
    )
    surface_m2: float = Field(..., gt=0, le=100000, description="Surface area in m²")
    lot_copropriete: Optional[str] = Field(default=None, max_length=100, description="Co-ownership lot number")
    description_cadastrale: Optional[str] = Field(default=None, max_length=500, description="Cadastral reference")


class Euro(BaseModel):
    """Money amount in Euros with validation."""
    montant: Decimal = Field(..., gt=0, le=1000000000, description="Amount in Euros")
    lettres: Optional[str] = Field(default=None, max_length=500, description="Amount in words")


# ── Act types ─────────────────────────────────────────────────


class ActeVente(BaseModel):
    """Deed of sale for real estate."""
    type_acte: Literal["vente"] = "vente"
    acte_date: Date = Field(..., description="Date of the act")
    notaire: str = Field(..., min_length=1, max_length=200, description="Notary name and office")
    vendeur: PersonnePhysique = Field(..., description="Seller")
    acheteur: PersonnePhysique = Field(..., description="Buyer")
    bien: BienImmobilier = Field(..., description="Property being sold")
    montant: Euro = Field(..., description="Sale price")
    conditions_suspensives: List[str] = Field(default_factory=list, description="Suspensive conditions")
    clauses_particulieres: List[str] = Field(default_factory=list, description="Special clauses")
    date_entree_jouissance: Optional[Date] = Field(default=None, description="Date of possession")


class ActePouvoir(BaseModel):
    """Power of attorney."""
    type_acte: Literal["pouvoir"] = "pouvoir"
    acte_date: Date = Field(..., description="Date of the act")
    notaire: str = Field(..., min_length=1, max_length=200, description="Notary name and office")
    mandant: PersonnePhysique = Field(..., description="Principal (grantor)")
    mandataire: PersonnePhysique = Field(..., description="Agent (attorney-in-fact)")
    etendue_pouvoirs: str = Field(..., min_length=10, max_length=2000, description="Scope of powers granted")
    duree: str = Field(default="1 an", max_length=100, description="Duration of the power")
    specialite: Optional[str] = Field(default=None, max_length=500, description="Specific limitations")


class ActeTestament(BaseModel):
    """Last will and testament."""
    type_acte: Literal["testament"] = "testament"
    acte_date: Date = Field(..., description="Date of the will")
    notaire: str = Field(..., min_length=1, max_length=200, description="Notary name and office")
    testateur: PersonnePhysique = Field(..., description="Testator")
    legataires: List[PersonnePhysique] = Field(..., min_length=1, max_length=20, description="Beneficiaries")
    biens: List[str] = Field(..., min_length=1, max_length=50, description="Description of assets")
    executeur_testamentaire: Optional[PersonnePhysique] = Field(default=None, description="Executor")
    clauses_speciales: List[str] = Field(default_factory=list, description="Special clauses")


class ActeMariage(BaseModel):
    """Civil marriage contract."""
    type_acte: Literal["mariage"] = "mariage"
    acte_date: Date = Field(..., description="Date of the ceremony")
    notaire: str = Field(..., min_length=1, max_length=200, description="Notary name and office")
    conjoint1: PersonnePhysique = Field(..., description="First spouse")
    conjoint2: PersonnePhysique = Field(..., description="Second spouse")
    regime_matrimonial: Literal[
        "communaute_reduite", "communaute_universelle", "separation_biens", "participation_acquests"
    ] = Field(..., description="Matrimonial property regime")
    apports_conjoint1: List[str] = Field(default_factory=list, description="Assets brought by spouse 1")
    apports_conjoint2: List[str] = Field(default_factory=list, description="Assets brought by spouse 2")
    clauses_particulieres: List[str] = Field(default_factory=list, description="Special clauses")


class ActeGeneral(BaseModel):
    """Generic notarial act (fallback)."""
    type_acte: Literal["general"] = "general"
    acte_date: Date = Field(..., description="Date of the act")
    notaire: str = Field(..., min_length=1, max_length=200, description="Notary name and office")
    parties: List[PersonnePhysique] = Field(..., min_length=1, max_length=20, description="Involved parties")
    objet: str = Field(..., min_length=10, max_length=3000, description="Purpose of the act")
    montant: Optional[Euro] = Field(default=None, description="Associated amount if applicable")


# ── Schema registry ───────────────────────────────────────────

ACT_SCHEMA_REGISTRY = {
    "vente": ActeVente,
    "pouvoir": ActePouvoir,
    "testament": ActeTestament,
    "mariage": ActeMariage,
    "general": ActeGeneral,
}

ACT_TYPE_LABELS = {
    "vente": "Deed of Sale (Vente)",
    "pouvoir": "Power of Attorney (Pouvoir)",
    "testament": "Last Will & Testament",
    "mariage": "Marriage Contract",
    "general": "General Notarial Act",
}
