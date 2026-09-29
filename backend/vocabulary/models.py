from django.db import models


class ReviewStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    IN_REVIEW = "in_review", "In review"
    VALIDATED = "validated", "Validated"
    REJECTED = "rejected", "Rejected"


class SignConcept(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="sign_concepts")
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code", "id")
        constraints = [
            models.UniqueConstraint(fields=("institution", "code"), name="vocab_concept_code_per_institution"),
            models.UniqueConstraint(fields=("id", "institution"), name="vocab_concept_id_tenant"),
            models.CheckConstraint(condition=~models.Q(code=""), name="vocab_concept_code_not_empty"),
        ]


class Sign(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="signs")
    sign_id = models.CharField(max_length=80)
    concept = models.ForeignKey(SignConcept, on_delete=models.PROTECT, related_name="signs")
    gloss = models.CharField(max_length=200)
    language = models.CharField(max_length=16, default="lsb")
    status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sign_id", "id")
        constraints = [
            models.UniqueConstraint(fields=("institution", "sign_id"), name="vocab_sign_id_per_institution"),
            models.UniqueConstraint(fields=("id", "institution"), name="vocab_sign_id_tenant"),
            models.CheckConstraint(condition=models.Q(status__in=ReviewStatus.values), name="vocab_sign_status_valid"),
            models.CheckConstraint(condition=~models.Q(sign_id=""), name="vocab_sign_stable_id_not_empty"),
        ]


class SignVariant(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="sign_variants")
    sign = models.ForeignKey(Sign, on_delete=models.PROTECT, related_name="variants")
    variant_code = models.CharField(max_length=80)
    label = models.CharField(max_length=200, blank=True)
    hamnosys = models.TextField(blank=True, help_text="Optional opaque notation; not asserted to be an LSB standard.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("variant_code", "id")
        constraints = [
            models.UniqueConstraint(fields=("sign", "variant_code"), name="vocab_variant_code_per_sign"),
            models.UniqueConstraint(fields=("id", "institution"), name="vocab_variant_id_tenant"),
            models.CheckConstraint(condition=~models.Q(variant_code=""), name="vocab_variant_code_not_empty"),
        ]


class ConceptAlias(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="concept_aliases")
    concept = models.ForeignKey(SignConcept, on_delete=models.PROTECT, related_name="aliases")
    alias = models.CharField(max_length=200)
    normalized_alias = models.CharField(max_length=200, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("normalized_alias", "id")
        constraints = [
            models.UniqueConstraint(fields=("institution", "normalized_alias"), name="vocab_alias_per_institution"),
            models.UniqueConstraint(fields=("id", "institution"), name="vocab_alias_id_tenant"),
            models.CheckConstraint(condition=~models.Q(normalized_alias=""), name="vocab_alias_not_empty"),
        ]

    def save(self, *args, **kwargs):
        self.normalized_alias = " ".join(self.alias.casefold().split())
        super().save(*args, **kwargs)


class SignPlan(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="sign_plans")
    code = models.CharField(max_length=80)
    concept = models.ForeignKey(SignConcept, on_delete=models.PROTECT, related_name="sign_plans")
    language = models.CharField(max_length=16, default="lsb")
    variant = models.CharField(max_length=80, blank=True)
    non_manual_markers = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code", "id")
        constraints = [
            models.UniqueConstraint(fields=("institution", "code"), name="vocab_plan_code_per_institution"),
            models.UniqueConstraint(fields=("id", "institution"), name="vocab_plan_id_tenant"),
            models.CheckConstraint(condition=models.Q(status__in=ReviewStatus.values), name="vocab_plan_status_valid"),
            models.CheckConstraint(condition=~models.Q(code=""), name="vocab_plan_code_not_empty"),
        ]


class SignPlanItem(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="sign_plan_items")
    plan = models.ForeignKey(SignPlan, on_delete=models.CASCADE, related_name="items")
    sign = models.ForeignKey(Sign, on_delete=models.PROTECT, related_name="plan_items")
    variant = models.ForeignKey(SignVariant, null=True, blank=True, on_delete=models.PROTECT, related_name="plan_items")
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=("plan", "position"), name="vocab_plan_position_unique"),
        ]
