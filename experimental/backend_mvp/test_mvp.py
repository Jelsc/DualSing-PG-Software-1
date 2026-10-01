from datetime import date

from django.test import Client, TestCase
from ninja_jwt.tokens import AccessToken

from accounts.models import ConsentRecord, Institution, Membership, User
from mvp.models import PilotCohort, PilotParticipant, PracticeActivity, PracticeAttempt
from vocabulary.models import ConceptAlias, ReviewStatus, Sign, SignConcept, SignPlan, SignPlanItem


class MvpApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.institution = Institution.objects.create(name="Pilot institution")
        self.other_institution = Institution.objects.create(name="Other institution")
        self.user = User.objects.create_user("member@example.test", "test-password")
        Membership.objects.create(user=self.user, institution=self.institution, role=Membership.Role.OPERATOR)
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {AccessToken.for_user(self.user)}"}
        concept = SignConcept.objects.create(institution=self.institution, code="greeting", label="Greeting")
        ConceptAlias.objects.create(institution=self.institution, concept=concept, alias="hello there")
        sign = Sign.objects.create(
            institution=self.institution, concept=concept, sign_id="greet-v1", gloss="HELLO", status=ReviewStatus.VALIDATED
        )
        plan = SignPlan.objects.create(
            institution=self.institution, concept=concept, code="greeting-plan", status=ReviewStatus.VALIDATED
        )
        SignPlanItem.objects.create(institution=self.institution, plan=plan, sign=sign, position=0)
        self.activity = PracticeActivity.objects.create(institution=self.institution, plan=plan, sign=sign)

    def test_resolution_is_exactly_controlled_and_never_claims_asset(self):
        path = f"/api/mobile/mvp/{self.institution.id}/communication/resolve"
        unsupported = self.client.post(path, {"input": "hello there plus free translation"}, content_type="application/json", **self.headers)
        self.assertEqual(unsupported.status_code, 200)
        self.assertEqual(unsupported.json()["status"], "unsupported_input")

        resolved = self.client.post(path, {"input": "  HELLO THERE "}, content_type="application/json", **self.headers)
        self.assertEqual(resolved.status_code, 200, resolved.content)
        self.assertEqual(resolved.json()["status"], "missing_clip_mapping")
        self.assertEqual(resolved.json()["steps"], [{
            "position": 0, "stable_sign_id": "greet-v1", "clip_key": "sign:greet-v1",
            "asset_available": False, "gloss": "HELLO",
        }])

    def test_practice_requires_consent_and_records_unknown_without_video(self):
        path = f"/api/mobile/mvp/{self.institution.id}/practice/activities/{self.activity.id}/attempt"
        denied = self.client.post(path, {"result": "unknown"}, content_type="application/json", **self.headers)
        self.assertEqual(denied.status_code, 403)
        ConsentRecord.objects.create(user=self.user, purpose="pilot_practice", policy_version="v1", action="grant")
        accepted = self.client.post(path, {"result": "unknown", "latency_ms": 120}, content_type="application/json", **self.headers)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(accepted.json()["evaluation_mode"], "synthetic_scaffold")
        self.assertEqual(accepted.json()["inference_source"], "controlled_client")
        self.assertNotIn("video", PracticeAttempt._meta.fields_map)

    def test_report_is_tenant_scoped_and_aggregates_deterministically(self):
        excluded_activity = PracticeActivity.objects.create(
            institution=self.institution, plan=self.activity.plan, sign=self.activity.sign
        )
        cohort = PilotCohort.objects.create(
            institution=self.institution, name="Cohort", start_date=date.today(), selected_activity_ids=[self.activity.id]
        )
        PilotParticipant.objects.create(cohort=cohort, user=self.user)
        ConsentRecord.objects.create(user=self.user, purpose="pilot_practice", policy_version="v1", action="grant")
        PracticeAttempt.objects.create(activity=self.activity, user=self.user, result="unknown", latency_ms=120, consent_status="granted")
        PracticeAttempt.objects.create(activity=excluded_activity, user=self.user, result="correct", latency_ms=80, consent_status="granted")
        path = f"/api/mobile/mvp/{self.institution.id}/pilots/{cohort.id}/report"
        report = self.client.get(path, **self.headers)
        self.assertEqual(report.status_code, 200, report.content)
        self.assertEqual(report.json()["attempts"]["total"], 1)
        self.assertEqual(report.json()["attempts"]["unknown"], 1)
        foreign = PilotCohort.objects.create(institution=self.other_institution, name="Foreign", start_date=date.today())
        denied = self.client.get(f"/api/mobile/mvp/{self.other_institution.id}/pilots/{foreign.id}/report", **self.headers)
        self.assertEqual(denied.status_code, 404)
