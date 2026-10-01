from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from ninja_jwt.tokens import AccessToken

from accounts.models import AuditRecord, Institution, Membership, User
from vocabulary.models import (
    ConceptAlias,
    ReviewStatus,
    Sign,
    SignConcept,
    SignPlan,
    SignPlanItem,
    SignVariant,
)


class VocabularyApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.institution = Institution.objects.create(name="Institution A")
        self.other_institution = Institution.objects.create(name="Institution B")
        self.reviewer = User.objects.create_user("reviewer@example.test", "test-password")
        self.mobile_user = User.objects.create_user("member@example.test", "test-password")
        self.operator = User.objects.create_user("operator@example.test", "test-password")
        Membership.objects.create(
            user=self.reviewer,
            institution=self.institution,
            role=Membership.Role.VOCABULARY_REVIEWER,
        )
        Membership.objects.create(
            user=self.mobile_user,
            institution=self.institution,
            role=Membership.Role.OPERATOR,
        )
        Membership.objects.create(
            user=self.operator,
            institution=self.institution,
            role=Membership.Role.OPERATOR,
        )
        Membership.objects.create(
            user=self.operator,
            institution=self.other_institution,
            role=Membership.Role.OPERATOR,
        )
        self.client.force_login(self.reviewer)
        self.root = f"/api/vocabulary/{self.institution.id}"

    def post(self, path, payload=None, client=None):
        return (client or self.client).post(
            path,
            payload or {},
            content_type="application/json",
        )

    def create_concept(self, code="concept-one"):
        response = self.post(f"{self.root}/concepts", {"code": code, "label": "Example concept"})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def create_sign(self, concept_id, sign_id="sign-one"):
        response = self.post(
            f"{self.root}/signs",
            {"sign_id": sign_id, "concept_id": concept_id, "gloss": "Example gloss"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def validate_sign(self, sign_pk):
        reviewed = self.post(f"{self.root}/signs/{sign_pk}/review")
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        validated = self.post(f"{self.root}/signs/{sign_pk}/validate")
        self.assertEqual(validated.status_code, 200, validated.content)
        return validated.json()

    def test_csrf_is_required_for_session_vocabulary_writes(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.reviewer)
        token = csrf_client.get("/api/web/csrf").json()["csrf_token"]

        missing = self.post(
            f"{self.root}/concepts",
            {"code": "no-csrf", "label": "No CSRF"},
            client=csrf_client,
        )
        accepted = csrf_client.post(
            f"{self.root}/concepts",
            {"code": "with-csrf", "label": "With CSRF"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(accepted.status_code, 201, accepted.content)

    def test_role_and_tenant_scope_cover_catalog_crud_and_references(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get(f"{self.root}/concepts").status_code, 403)
        denied_write = self.post(
            f"{self.root}/concepts",
            {"code": "operator-write", "label": "Denied"},
        )
        self.assertEqual(denied_write.status_code, 403)
        foreign_root = f"/api/vocabulary/{self.other_institution.id}"
        self.assertEqual(self.client.get(foreign_root + "/concepts").status_code, 403)

        self.client.force_login(self.reviewer)
        concept = self.create_concept()
        foreign_concept = SignConcept.objects.create(
            institution=self.other_institution,
            code="foreign-concept",
            label="Foreign concept",
        )
        foreign_sign = Sign.objects.create(
            institution=self.other_institution,
            concept=foreign_concept,
            sign_id="foreign-sign",
            gloss="Foreign gloss",
        )

        self.assertEqual(
            self.client.get(f"{self.root}/concepts/{foreign_concept.id}").status_code,
            404,
        )

        sign_response = self.client.post(
            f"{self.root}/signs",
            {"sign_id": "cross-concept", "concept_id": foreign_concept.id, "gloss": "No cross tenant"},
            content_type="application/json",
        )
        alias_response = self.client.post(
            f"{self.root}/concepts/{foreign_concept.id}/aliases",
            {"alias": "foreign alias"},
            content_type="application/json",
        )
        plan_response = self.client.post(
            f"{self.root}/plans",
            {
                "code": "cross-reference",
                "concept_id": concept["id"],
                "items": [{"sign_id": foreign_sign.id}],
            },
            content_type="application/json",
        )

        self.assertEqual(sign_response.status_code, 404)
        self.assertEqual(alias_response.status_code, 404)
        self.assertEqual(plan_response.status_code, 422)
        foreign_plan_concept = self.post(
            f"{self.root}/plans",
            {"code": "foreign-concept-plan", "concept_id": foreign_concept.id},
        )
        self.assertEqual(foreign_plan_concept.status_code, 404)
        self.assertFalse(ConceptAlias.objects.filter(institution=self.institution).exists())
        self.assertFalse(SignPlan.objects.filter(institution=self.institution).exists())

    def test_institution_admin_and_platform_superuser_can_manage_and_publish(self):
        institution_admin = User.objects.create_user("admin@example.test", "test-password")
        Membership.objects.create(
            user=institution_admin,
            institution=self.institution,
            role=Membership.Role.INSTITUTION_ADMIN,
        )
        self.client.force_login(institution_admin)
        concept = self.create_concept("admin-concept")
        sign = self.create_sign(concept["id"], "admin-sign")
        approved = self.validate_sign(sign["id"])
        self.assertEqual(approved["status"], ReviewStatus.VALIDATED)

        platform_admin = User.objects.create_superuser("root@example.test", "test-password")
        self.client.force_login(platform_admin)
        self.assertEqual(self.client.get(f"/api/vocabulary/{self.other_institution.id}/concepts").status_code, 200)

    def test_composite_database_constraints_reject_cross_tenant_foreign_keys(self):
        concept = SignConcept.objects.create(
            institution=self.institution,
            code="local-concept",
            label="Local concept",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Sign.objects.create(
                institution=self.other_institution,
                concept=concept,
                sign_id="invalid-sign",
                gloss="Invalid",
            )

    def test_lifecycle_requires_review_and_plan_validation_and_mobile_is_approved_only(self):
        concept = self.create_concept()
        sign = self.create_sign(concept["id"])
        invalid_transition = self.post(f"{self.root}/signs/{sign['id']}/validate")
        self.assertEqual(invalid_transition.status_code, 409)

        empty_plan = self.post(
            f"{self.root}/plans",
            {"code": "empty-plan", "concept_id": concept["id"]},
        )
        self.assertEqual(empty_plan.status_code, 201, empty_plan.content)
        plan_id = empty_plan.json()["id"]
        self.assertEqual(self.post(f"{self.root}/plans/{plan_id}/review").status_code, 200)
        invalid_plan = self.post(f"{self.root}/plans/{plan_id}/validate")
        self.assertEqual(invalid_plan.status_code, 422)
        self.assertEqual(SignPlan.objects.get(pk=plan_id).status, ReviewStatus.IN_REVIEW)

        unvalidated_plan = self.post(
            f"{self.root}/plans",
            {
                "code": "unvalidated-reference",
                "concept_id": concept["id"],
                "items": [{"sign_id": sign["id"]}],
            },
        )
        self.assertEqual(unvalidated_plan.status_code, 201, unvalidated_plan.content)
        unvalidated_plan_id = unvalidated_plan.json()["id"]
        self.post(f"{self.root}/plans/{unvalidated_plan_id}/review")
        self.assertEqual(self.post(f"{self.root}/plans/{unvalidated_plan_id}/validate").status_code, 422)

        self.validate_sign(sign["id"])

        valid_plan = self.post(
            f"{self.root}/plans",
            {
                "code": "approved-plan",
                "concept_id": concept["id"],
                "language": "lsb",
                "variant": "regional-a",
                "non_manual_markers": [{
                    "kind": "brow",
                    "value": "raised",
                    "start_position": 0,
                    "end_position": 0,
                }],
                "items": [{"sign_id": sign["id"]}],
            },
        )
        self.assertEqual(valid_plan.status_code, 201, valid_plan.content)
        valid_plan_id = valid_plan.json()["id"]
        self.assertEqual(self.post(f"{self.root}/plans/{valid_plan_id}/review").status_code, 200)
        published = self.post(f"{self.root}/plans/{valid_plan_id}/validate")
        self.assertEqual(published.status_code, 200, published.content)
        self.assertEqual(published.json()["status"], ReviewStatus.VALIDATED)
        self.assertEqual(published.json()["items"][0]["stable_sign_id"], "sign-one")

        rejected_sign = self.create_sign(concept["id"], "rejected-sign")
        self.post(f"{self.root}/signs/{rejected_sign['id']}/review")
        self.post(f"{self.root}/signs/{rejected_sign['id']}/reject")

        mobile_headers = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(self.mobile_user)}"}
        mobile_signs = self.client.get(
            f"/api/mobile/vocabulary/{self.institution.id}/signs", **mobile_headers
        )
        mobile_plans = self.client.get(
            f"/api/mobile/vocabulary/{self.institution.id}/plans", **mobile_headers
        )
        self.assertEqual(mobile_signs.status_code, 200)
        self.assertEqual([item["sign_id"] for item in mobile_signs.json()], ["sign-one"])
        self.assertEqual(mobile_plans.status_code, 200)
        self.assertEqual([item["code"] for item in mobile_plans.json()], ["approved-plan"])
        self.assertEqual(
            self.client.get(
                f"/api/mobile/vocabulary/{self.institution.id}/aliases", **mobile_headers
            ).status_code,
            200,
        )
        denied_tenant = self.client.get(
            f"/api/mobile/vocabulary/{self.other_institution.id}/plans", **mobile_headers
        )
        self.assertEqual(denied_tenant.status_code, 404)

    def test_alias_normalization_and_audit_events_are_scoped(self):
        concept = self.create_concept()
        created = self.post(
            f"{self.root}/concepts/{concept['id']}/aliases",
            {"alias": "  Example   Phrase "},
        )
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(ConceptAlias.objects.get(pk=created.json()["id"]).normalized_alias, "example phrase")
        duplicate = self.post(
            f"{self.root}/concepts/{concept['id']}/aliases",
            {"alias": "example phrase"},
        )
        self.assertEqual(duplicate.status_code, 409)

        self.create_sign(concept["id"])
        self.assertTrue(AuditRecord.objects.filter(
            institution=self.institution,
            event_type="vocabulary.concept.created",
            subject_id=str(concept["id"]),
        ).exists())
        alias_audit = AuditRecord.objects.get(event_type="vocabulary.alias.created")
        self.assertEqual(alias_audit.metadata, {"status": ""})
        self.assertNotIn("alias", str(alias_audit.metadata))

    def test_admin_variant_listing_delete_constraints_and_tenant_scope(self):
        concept = self.create_concept()
        sign = self.create_sign(concept["id"])
        variant = SignVariant.objects.create(
            institution=self.institution,
            sign_id=sign["id"],
            variant_code="regional-a",
            label="Regional form",
            hamnosys="opaque notation",
        )
        list_path = f"{self.root}/signs/{sign['id']}/variants"
        listed = self.client.get(list_path)
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertEqual(listed.json(), [{
            "id": variant.id,
            "sign_id": sign["id"],
            "variant_code": "regional-a",
            "label": "Regional form",
            "hamnosys": "opaque notation",
        }])

        plan = SignPlan.objects.create(
            institution=self.institution,
            concept_id=concept["id"],
            code="variant-reference",
        )
        SignPlanItem.objects.create(
            institution=self.institution,
            plan=plan,
            sign_id=sign["id"],
            variant=variant,
            position=0,
        )
        blocked = self.client.delete(f"{self.root}/variants/{variant.id}")
        self.assertEqual(blocked.status_code, 409, blocked.content)

        SignPlanItem.objects.filter(plan=plan, variant=variant).delete()
        deleted = self.client.delete(f"{self.root}/variants/{variant.id}")
        self.assertEqual(deleted.status_code, 204, deleted.content)
        self.assertFalse(SignVariant.objects.filter(pk=variant.id).exists())
        self.assertTrue(AuditRecord.objects.filter(
            institution=self.institution,
            event_type="vocabulary.variant.deleted",
            subject_id=str(variant.id),
        ).exists())

        foreign_concept = SignConcept.objects.create(
            institution=self.other_institution,
            code="foreign-variant-concept",
            label="Foreign variant concept",
        )
        foreign_sign = Sign.objects.create(
            institution=self.other_institution,
            concept=foreign_concept,
            sign_id="foreign-variant-sign",
            gloss="Foreign variant sign",
        )
        foreign_variant = SignVariant.objects.create(
            institution=self.other_institution,
            sign=foreign_sign,
            variant_code="foreign",
        )
        foreign_sign_list = self.client.get(f"{self.root}/signs/{foreign_sign.id}/variants")
        foreign_delete = self.client.delete(f"{self.root}/variants/{foreign_variant.id}")
        self.assertEqual(foreign_sign_list.status_code, 404)
        self.assertEqual(foreign_delete.status_code, 404)
        self.assertTrue(SignVariant.objects.filter(pk=foreign_variant.id).exists())

    def test_review_and_publish_append_status_only_audit_events(self):
        concept = self.create_concept()
        sign = self.create_sign(concept["id"])
        self.validate_sign(sign["id"])
        event_types = list(AuditRecord.objects.filter(
            subject_type="sign",
            subject_id=str(sign["id"]),
        ).order_by("id").values_list("event_type", flat=True))
        self.assertEqual(event_types, [
            "vocabulary.sign.created",
            "vocabulary.sign.review",
            "vocabulary.sign.validate",
        ])
        self.assertEqual(
            AuditRecord.objects.filter(subject_id=str(sign["id"])).last().metadata,
            {"status": ReviewStatus.VALIDATED},
        )
