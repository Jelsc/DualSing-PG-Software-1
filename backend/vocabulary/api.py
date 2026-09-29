from django.db import IntegrityError, transaction
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from accounts.authentication import LiveUserJWTAuth
from accounts.models import AuditRecord
from accounts.policies import can_manage_vocabulary, can_view_institution
from accounts.security import require_csrf

from .models import ConceptAlias, ReviewStatus, Sign, SignConcept, SignPlan, SignPlanItem, SignVariant
from .schemas import (
    AliasIn,
    AliasOut,
    AliasPatch,
    ConceptIn,
    ConceptOut,
    ConceptPatch,
    PlanIn,
    PlanOut,
    PlanPatch,
    SignIn,
    SignOut,
    SignPatch,
    VariantIn,
    VariantOut,
    VariantPatch,
)

admin_vocabulary = Router(auth=django_auth)
mobile_vocabulary = Router(auth=LiveUserJWTAuth())


def require_manager(request, institution_id):
    institution = can_view_institution(request.user, institution_id)
    if institution is None:
        raise HttpError(404, "Institution not found")
    if not can_manage_vocabulary(request.user, institution_id):
        raise HttpError(403, "Vocabulary reviewer or institution administrator required")
    return institution


def require_mobile_member(request, institution_id):
    if can_view_institution(request.auth, institution_id) is None:
        raise HttpError(404, "Institution not found")


def get_scoped(queryset, institution_id, object_id, message):
    item = queryset.filter(institution_id=institution_id, pk=object_id).first()
    if item is None:
        raise HttpError(404, message)
    return item


def audit(request, institution, event, subject, obj):
    AuditRecord.objects.create(
        actor=request.user,
        institution=institution,
        event_type=f"vocabulary.{subject}.{event}",
        subject_type=subject,
        subject_id=str(obj.pk),
        metadata={"status": getattr(obj, "status", "")},
    )


def create_catalog_record(callback):
    try:
        with transaction.atomic():
            return callback()
    except IntegrityError:
        raise HttpError(409, "A catalog identifier or tenant relationship conflicts with an existing record")


def plan_output(plan):
    return {
        "id": plan.id,
        "code": plan.code,
        "concept_id": plan.concept_id,
        "language": plan.language,
        "variant": plan.variant,
        "non_manual_markers": plan.non_manual_markers,
        "status": plan.status,
        "items": [
            {
                "position": item.position,
                "sign_id": item.sign_id,
                "stable_sign_id": item.sign.sign_id,
                "gloss": item.sign.gloss,
                "variant_id": item.variant_id,
            }
            for item in plan.items.select_related("sign").all()
        ],
    }


def set_plan_items(plan, institution_id, items):
    resolved = []
    for position, payload in enumerate(items):
        sign = Sign.objects.filter(pk=payload.sign_id, institution_id=institution_id).first()
        if sign is None:
            raise HttpError(422, "Every plan sign must belong to the active institution")
        variant = None
        if payload.variant_id is not None:
            variant = SignVariant.objects.filter(
                pk=payload.variant_id, institution_id=institution_id, sign=sign
            ).first()
            if variant is None:
                raise HttpError(422, "Every plan variant must belong to its referenced sign")
        resolved.append(SignPlanItem(
            institution_id=institution_id,
            plan=plan,
            sign=sign,
            variant=variant,
            position=position,
        ))
    plan.items.all().delete()
    SignPlanItem.objects.bulk_create(resolved)


def validate_plan(plan):
    if not plan.items.exists():
        raise HttpError(422, "A plan must contain at least one sign before validation")
    if not SignConcept.objects.filter(pk=plan.concept_id, institution_id=plan.institution_id).exists():
        raise HttpError(422, "Plan concept must belong to its institution")
    items = list(plan.items.select_related("sign", "variant"))
    if any(item.sign.status != ReviewStatus.VALIDATED for item in items):
        raise HttpError(422, "Every referenced sign must be validated before plan validation")
    if any(item.variant_id and item.variant.sign_id != item.sign_id for item in items):
        raise HttpError(422, "Every plan variant must belong to its referenced sign")
    for marker in plan.non_manual_markers:
        start = marker.get("start_position", -1)
        end = marker.get("end_position", -1)
        if start < 0 or end < start or end >= len(items):
            raise HttpError(422, "Non-manual marker positions must fall within the ordered plan items")


def transition(request, institution, obj, action, subject):
    allowed = {
        "review": (ReviewStatus.DRAFT, ReviewStatus.IN_REVIEW),
        "validate": (ReviewStatus.IN_REVIEW, ReviewStatus.VALIDATED),
        "reject": (ReviewStatus.IN_REVIEW, ReviewStatus.REJECTED),
        "reopen": (ReviewStatus.REJECTED, ReviewStatus.DRAFT),
    }
    expected, new_status = allowed[action]
    if obj.status != expected:
        raise HttpError(409, f"Cannot {action} an item in {obj.status} status")
    if action == "validate" and isinstance(obj, SignPlan):
        validate_plan(obj)
    obj.status = new_status
    obj.save(update_fields=("status", "updated_at"))
    audit(request, institution, action, subject, obj)
    return obj


@admin_vocabulary.get("/{institution_id}/concepts", response=list[ConceptOut])
def list_concepts(request, institution_id: int):
    require_manager(request, institution_id)
    return SignConcept.objects.filter(institution_id=institution_id)


@admin_vocabulary.get("/{institution_id}/concepts/{concept_id}", response=ConceptOut)
def get_concept(request, institution_id: int, concept_id: int):
    require_manager(request, institution_id)
    return get_scoped(SignConcept.objects, institution_id, concept_id, "Concept not found")


@admin_vocabulary.post("/{institution_id}/concepts", response={201: ConceptOut})
def create_concept(request, institution_id: int, payload: ConceptIn):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    concept = create_catalog_record(lambda: SignConcept.objects.create(institution=institution, **payload.dict()))
    audit(request, institution, "created", "concept", concept)
    return 201, concept


@admin_vocabulary.patch("/{institution_id}/concepts/{concept_id}", response=ConceptOut)
def update_concept(request, institution_id: int, concept_id: int, payload: ConceptPatch):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    concept = get_scoped(SignConcept.objects, institution_id, concept_id, "Concept not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(concept, field, value)
    concept.save()
    audit(request, institution, "edited", "concept", concept)
    return concept


@admin_vocabulary.delete("/{institution_id}/concepts/{concept_id}", response={204: None})
def delete_concept(request, institution_id: int, concept_id: int):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    concept = get_scoped(SignConcept.objects, institution_id, concept_id, "Concept not found")
    if concept.signs.exists() or concept.aliases.exists() or concept.sign_plans.exists():
        raise HttpError(409, "Concepts referenced by vocabulary records cannot be deleted")
    audit(request, institution, "deleted", "concept", concept)
    concept.delete()
    return 204, None


@admin_vocabulary.post("/{institution_id}/concepts/{concept_id}/aliases", response={201: AliasOut})
def create_alias(request, institution_id: int, concept_id: int, payload: AliasIn):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    concept = get_scoped(SignConcept.objects, institution_id, concept_id, "Concept not found")
    alias = create_catalog_record(lambda: ConceptAlias.objects.create(
        institution=institution, concept=concept, alias=payload.alias
    ))
    audit(request, institution, "created", "alias", alias)
    return 201, alias


@admin_vocabulary.patch("/{institution_id}/aliases/{alias_id}", response=AliasOut)
def update_alias(request, institution_id: int, alias_id: int, payload: AliasPatch):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    alias = get_scoped(ConceptAlias.objects, institution_id, alias_id, "Alias not found")
    alias.alias = payload.alias
    alias.normalized_alias = " ".join(payload.alias.casefold().split())
    alias = create_catalog_record(lambda: (alias.save(), alias)[1])
    audit(request, institution, "edited", "alias", alias)
    return alias


@admin_vocabulary.get("/{institution_id}/aliases", response=list[AliasOut])
def list_aliases(request, institution_id: int):
    require_manager(request, institution_id)
    return ConceptAlias.objects.filter(institution_id=institution_id)


@admin_vocabulary.delete("/{institution_id}/aliases/{alias_id}", response={204: None})
def delete_alias(request, institution_id: int, alias_id: int):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    alias = get_scoped(ConceptAlias.objects, institution_id, alias_id, "Alias not found")
    audit(request, institution, "deleted", "alias", alias)
    alias.delete()
    return 204, None


@admin_vocabulary.get("/{institution_id}/signs", response=list[SignOut])
def list_signs(request, institution_id: int):
    require_manager(request, institution_id)
    return Sign.objects.filter(institution_id=institution_id)


@admin_vocabulary.get("/{institution_id}/signs/{sign_pk}", response=SignOut)
def get_sign(request, institution_id: int, sign_pk: int):
    require_manager(request, institution_id)
    return get_scoped(Sign.objects, institution_id, sign_pk, "Sign not found")


@admin_vocabulary.post("/{institution_id}/signs", response={201: SignOut})
def create_sign(request, institution_id: int, payload: SignIn):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    concept = get_scoped(SignConcept.objects, institution_id, payload.concept_id, "Concept not found")
    sign = create_catalog_record(lambda: Sign.objects.create(
        institution=institution,
        concept=concept,
        sign_id=payload.sign_id,
        gloss=payload.gloss,
        language=payload.language,
    ))
    audit(request, institution, "created", "sign", sign)
    return 201, sign


@admin_vocabulary.patch("/{institution_id}/signs/{sign_pk}", response=SignOut)
def update_sign(request, institution_id: int, sign_pk: int, payload: SignPatch):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    with transaction.atomic():
        sign = get_scoped(Sign.objects.select_for_update(), institution_id, sign_pk, "Sign not found")
        if sign.status not in (ReviewStatus.DRAFT, ReviewStatus.REJECTED):
            raise HttpError(409, "Only draft or rejected signs can be edited")
        updates = payload.dict(exclude_unset=True)
        if "concept_id" in updates:
            sign.concept = get_scoped(SignConcept.objects, institution_id, updates.pop("concept_id"), "Concept not found")
        for field, value in updates.items():
            setattr(sign, field, value)
        sign.save()
    audit(request, institution, "edited", "sign", sign)
    return sign


@admin_vocabulary.delete("/{institution_id}/signs/{sign_pk}", response={204: None})
def delete_sign(request, institution_id: int, sign_pk: int):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    sign = get_scoped(Sign.objects, institution_id, sign_pk, "Sign not found")
    if sign.status == ReviewStatus.VALIDATED:
        raise HttpError(409, "Validated signs cannot be deleted")
    sign_id_value = sign.pk
    try:
        with transaction.atomic():
            sign.delete()
            AuditRecord.objects.create(
                actor=request.user,
                institution=institution,
                event_type="vocabulary.sign.deleted",
                subject_type="sign",
                subject_id=str(sign_id_value),
                metadata={"status": sign.status},
            )
    except IntegrityError:
        raise HttpError(409, "Signs referenced by plans or variants cannot be deleted")
    return 204, None


@admin_vocabulary.post("/{institution_id}/signs/{sign_pk}/variants", response={201: VariantOut})
def create_variant(request, institution_id: int, sign_pk: int, payload: VariantIn):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    sign = get_scoped(Sign.objects, institution_id, sign_pk, "Sign not found")
    variant = create_catalog_record(lambda: SignVariant.objects.create(
        institution=institution, sign=sign, **payload.dict()
    ))
    audit(request, institution, "created", "variant", variant)
    return 201, variant


@admin_vocabulary.patch("/{institution_id}/variants/{variant_id}", response=VariantOut)
def update_variant(request, institution_id: int, variant_id: int, payload: VariantPatch):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    variant = get_scoped(SignVariant.objects, institution_id, variant_id, "Variant not found")
    variant_pk = variant.pk
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(variant, field, value)
    variant = create_catalog_record(lambda: (variant.save(), variant)[1])
    audit(request, institution, "edited", "variant", variant)
    return variant


@admin_vocabulary.delete("/{institution_id}/variants/{variant_id}", response={204: None})
def delete_variant(request, institution_id: int, variant_id: int):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    variant = get_scoped(SignVariant.objects, institution_id, variant_id, "Variant not found")
    try:
        with transaction.atomic():
            variant.delete()
            AuditRecord.objects.create(
                actor=request.user,
                institution=institution,
                event_type="vocabulary.variant.deleted",
                subject_type="variant",
                subject_id=str(variant_pk),
                metadata={},
            )
    except IntegrityError:
        raise HttpError(409, "Variants referenced by plans cannot be deleted")
    return 204, None


@admin_vocabulary.get("/{institution_id}/plans", response=list[PlanOut])
def list_plans(request, institution_id: int):
    require_manager(request, institution_id)
    return [plan_output(plan) for plan in SignPlan.objects.filter(institution_id=institution_id)]


@admin_vocabulary.get("/{institution_id}/plans/{plan_id}", response=PlanOut)
def get_plan(request, institution_id: int, plan_id: int):
    require_manager(request, institution_id)
    plan = get_scoped(SignPlan.objects, institution_id, plan_id, "Plan not found")
    return plan_output(plan)


@admin_vocabulary.post("/{institution_id}/plans", response={201: PlanOut})
def create_plan(request, institution_id: int, payload: PlanIn):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    concept = get_scoped(SignConcept.objects, institution_id, payload.concept_id, "Concept not found")
    with transaction.atomic():
        plan = create_catalog_record(lambda: SignPlan.objects.create(
            institution=institution,
            code=payload.code,
            concept=concept,
            language=payload.language,
            variant=payload.variant,
            non_manual_markers=[marker.dict() for marker in payload.non_manual_markers],
        ))
        set_plan_items(plan, institution_id, payload.items)
    audit(request, institution, "created", "plan", plan)
    return 201, plan_output(plan)


@admin_vocabulary.patch("/{institution_id}/plans/{plan_id}", response=PlanOut)
def update_plan(request, institution_id: int, plan_id: int, payload: PlanPatch):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    with transaction.atomic():
        plan = get_scoped(SignPlan.objects.select_for_update(), institution_id, plan_id, "Plan not found")
        if plan.status not in (ReviewStatus.DRAFT, ReviewStatus.REJECTED):
            raise HttpError(409, "Only draft or rejected plans can be edited")
        updates = payload.dict(exclude_unset=True)
        if "concept_id" in updates:
            plan.concept = get_scoped(SignConcept.objects, institution_id, updates.pop("concept_id"), "Concept not found")
        items = updates.pop("items", None)
        for field, value in updates.items():
            if field == "non_manual_markers":
                value = [marker.dict() if hasattr(marker, "dict") else marker for marker in value]
            setattr(plan, field, value)
        plan.save()
        if items is not None:
            set_plan_items(plan, institution_id, items)
    audit(request, institution, "edited", "plan", plan)
    return plan_output(plan)


@admin_vocabulary.delete("/{institution_id}/plans/{plan_id}", response={204: None})
def delete_plan(request, institution_id: int, plan_id: int):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    plan = get_scoped(SignPlan.objects, institution_id, plan_id, "Plan not found")
    if plan.status == ReviewStatus.VALIDATED:
        raise HttpError(409, "Validated plans cannot be deleted")
    audit(request, institution, "deleted", "plan", plan)
    plan.delete()
    return 204, None


def transition_sign(request, institution_id, sign_pk, action):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    with transaction.atomic():
        sign = get_scoped(Sign.objects.select_for_update(), institution_id, sign_pk, "Sign not found")
        transition(request, institution, sign, action, "sign")
    return sign


def transition_plan(request, institution_id, plan_id, action):
    require_csrf(request)
    institution = require_manager(request, institution_id)
    with transaction.atomic():
        plan = get_scoped(SignPlan.objects.select_for_update(), institution_id, plan_id, "Plan not found")
        transition(request, institution, plan, action, "plan")
    return plan_output(plan)


for transition_name in ("review", "validate", "reject", "reopen"):
    def add_transition_routes(action):
        @admin_vocabulary.post("/{institution_id}/signs/{sign_pk}/" + action, response=SignOut)
        def sign_action(request, institution_id: int, sign_pk: int):
            return transition_sign(request, institution_id, sign_pk, action)

        @admin_vocabulary.post("/{institution_id}/plans/{plan_id}/" + action, response=PlanOut)
        def plan_action(request, institution_id: int, plan_id: int):
            return transition_plan(request, institution_id, plan_id, action)

    add_transition_routes(transition_name)


@mobile_vocabulary.get("/{institution_id}/signs", response=list[SignOut])
def mobile_signs(request, institution_id: int):
    require_mobile_member(request, institution_id)
    return Sign.objects.filter(institution_id=institution_id, status=ReviewStatus.VALIDATED)


@mobile_vocabulary.get("/{institution_id}/signs/{sign_pk}/variants", response=list[VariantOut])
def mobile_variants(request, institution_id: int, sign_pk: int):
    require_mobile_member(request, institution_id)
    if not Sign.objects.filter(
        pk=sign_pk, institution_id=institution_id, status=ReviewStatus.VALIDATED
    ).exists():
        raise HttpError(404, "Validated sign not found")
    return SignVariant.objects.filter(institution_id=institution_id, sign_id=sign_pk)


@mobile_vocabulary.get("/{institution_id}/plans", response=list[PlanOut])
def mobile_plans(request, institution_id: int):
    require_mobile_member(request, institution_id)
    plans = SignPlan.objects.filter(institution_id=institution_id, status=ReviewStatus.VALIDATED)
    return [plan_output(plan) for plan in plans]


@mobile_vocabulary.get("/{institution_id}/concepts", response=list[ConceptOut])
def mobile_concepts(request, institution_id: int):
    require_mobile_member(request, institution_id)
    return SignConcept.objects.filter(
        institution_id=institution_id,
        signs__status=ReviewStatus.VALIDATED,
    ).distinct()


@mobile_vocabulary.get("/{institution_id}/aliases", response=list[AliasOut])
def mobile_aliases(request, institution_id: int):
    require_mobile_member(request, institution_id)
    return ConceptAlias.objects.filter(
        institution_id=institution_id,
        concept__signs__status=ReviewStatus.VALIDATED,
    ).distinct()
