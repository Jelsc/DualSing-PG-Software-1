from datetime import datetime

from ninja import Schema
from pydantic import Field


class ConceptIn(Schema):
    code: str
    label: str
    description: str = ""


class ConceptPatch(Schema):
    label: str | None = None
    description: str | None = None


class ConceptOut(Schema):
    id: int
    code: str
    label: str
    description: str
    created_at: datetime
    updated_at: datetime


class SignIn(Schema):
    sign_id: str
    concept_id: int
    gloss: str
    language: str = "lsb"


class SignPatch(Schema):
    concept_id: int | None = None
    gloss: str | None = None
    language: str | None = None


class SignOut(Schema):
    id: int
    sign_id: str
    concept_id: int
    gloss: str
    language: str
    status: str


class VariantIn(Schema):
    variant_code: str
    label: str = ""
    hamnosys: str = ""


class VariantPatch(Schema):
    variant_code: str | None = None
    label: str | None = None
    hamnosys: str | None = None


class VariantOut(Schema):
    id: int
    sign_id: int
    variant_code: str
    label: str
    hamnosys: str


class AliasIn(Schema):
    alias: str = Field(min_length=1, max_length=200)


class AliasPatch(Schema):
    alias: str = Field(min_length=1, max_length=200)


class NonManualMarker(Schema):
    kind: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=200)
    start_position: int = Field(ge=0)
    end_position: int = Field(ge=0)


class AliasOut(Schema):
    id: int
    concept_id: int
    alias: str


class PlanItemIn(Schema):
    sign_id: int
    variant_id: int | None = None


class PlanItemOut(Schema):
    position: int
    sign_id: int
    stable_sign_id: str
    gloss: str
    variant_id: int | None


class PlanIn(Schema):
    code: str
    concept_id: int
    language: str = "lsb"
    variant: str = ""
    non_manual_markers: list[NonManualMarker] = Field(default_factory=list)
    items: list[PlanItemIn] = Field(default_factory=list)


class PlanPatch(Schema):
    concept_id: int | None = None
    language: str | None = None
    variant: str | None = None
    non_manual_markers: list[NonManualMarker] | None = None
    items: list[PlanItemIn] | None = None


class PlanOut(Schema):
    id: int
    code: str
    concept_id: int
    language: str
    variant: str
    non_manual_markers: list[dict]
    status: str
    items: list[PlanItemOut]
