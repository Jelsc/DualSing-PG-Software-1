from django.test import Client, TestCase

from accounts.models import AuditRecord, Institution, Membership, User
from vocabulary.models import ReviewStatus, Sign, SignConcept, SignPlan
from .models import PracticeActivity


class ActivityAuthoringTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(name="Authoring test")
        self.other = Institution.objects.create(name="Other test")
        self.admin = User.objects.create_user("author@example.test", "test-password")
        self.membership = Membership.objects.create(user=self.admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        concept = SignConcept.objects.create(institution=self.institution, code="hello", label="Hello")
        self.plan = SignPlan.objects.create(institution=self.institution, concept=concept, code="hello", status=ReviewStatus.VALIDATED)
        self.sign = Sign.objects.create(institution=self.institution, concept=concept, sign_id="hello", gloss="HELLO", status=ReviewStatus.VALIDATED)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.admin)
        self.csrf = self.client.get("/api/web/csrf").json()["csrf_token"]
        self.path = f"/api/portal/{self.institution.id}/activities"

    def create(self, **payload):
        return self.client.post(self.path, {"plan_id": self.plan.id, "sign_id": self.sign.id, **payload}, content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf)

    def test_admin_creates_audited_consent_required_scaffold(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.content)
        activity = PracticeActivity.objects.get(pk=response.json()["id"])
        self.assertTrue(activity.requires_consent)
        self.assertEqual(activity.model_version, "synthetic-gru-v1")
        self.assertTrue(AuditRecord.objects.filter(event_type="mvp.practice_activity_created", actor=self.admin, institution=self.institution, subject_id=str(activity.id)).exists())

    def test_reviewer_cannot_author(self):
        self.membership.role = Membership.Role.VOCABULARY_REVIEWER
        self.membership.save()
        self.assertEqual(self.create().status_code, 403)
        self.assertFalse(PracticeActivity.objects.exists())

    def test_foreign_sign_and_plan_are_rejected(self):
        concept = SignConcept.objects.create(institution=self.other, code="foreign", label="Foreign")
        plan = SignPlan.objects.create(institution=self.other, concept=concept, code="foreign", status=ReviewStatus.VALIDATED)
        sign = Sign.objects.create(institution=self.other, concept=concept, sign_id="foreign", gloss="FOREIGN", status=ReviewStatus.VALIDATED)
        self.assertEqual(self.create(plan_id=plan.id).status_code, 422)
        self.assertEqual(self.create(sign_id=sign.id).status_code, 422)
        self.assertFalse(PracticeActivity.objects.exists())

    def test_unvalidated_vocabulary_and_missing_csrf_are_rejected(self):
        self.sign.status = ReviewStatus.DRAFT
        self.sign.save()
        self.assertEqual(self.create().status_code, 422)
        self.assertEqual(self.client.post(self.path, {"plan_id": self.plan.id, "sign_id": self.sign.id}, content_type="application/json").status_code, 403)
        self.assertFalse(PracticeActivity.objects.exists())

    def test_other_institution_boundary_is_not_visible(self):
        self.path = f"/api/portal/{self.other.id}/activities"
        self.assertEqual(self.create().status_code, 404)
