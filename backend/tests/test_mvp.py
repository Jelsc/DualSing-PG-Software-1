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
        sign = Sign.objects.create(institution=self.institution, concept=concept, sign_id="greet-v1", gloss="HELLO", status=ReviewStatus.VALIDATED)
        plan = SignPlan.objects.create(institution=self.institution, concept=concept, code="greeting-plan", status=ReviewStatus.VALIDATED)
        SignPlanItem.objects.create(institution=self.institution, plan=plan, sign=sign, position=0)
        self.activity = PracticeActivity.objects.create(institution=self.institution, plan=plan, sign=sign)

    def test_resolution_contract_distinguishes_unsupported_input_and_missing_plan(self):
        path = f"/api/mobile/mvp/{self.institution.id}/communication/resolve"
        unsupported = self.client.post(path, {"input": "not controlled"}, content_type="application/json", **self.headers)
        self.assertEqual(unsupported.status_code, 200)
        self.assertEqual(unsupported.json()["status"], "unsupported_input")

        plan = self.activity.plan
        plan.status = ReviewStatus.DRAFT
        plan.save(update_fields=("status",))
        missing_plan = self.client.post(path, {"input": "hello there"}, content_type="application/json", **self.headers)
        self.assertEqual(missing_plan.status_code, 200)
        self.assertEqual(missing_plan.json()["status"], "missing_plan")

    def test_resolution_returns_controlled_playback_mapping(self):
        response = self.client.post(
            f"/api/mobile/mvp/{self.institution.id}/communication/resolve",
            {"input": "  HELLO THERE "}, content_type="application/json", **self.headers
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], "missing_clip_mapping")
        self.assertEqual(response.json()["steps"][0]["clip_key"], "sign:greet-v1")
        self.assertFalse(response.json()["steps"][0]["asset_available"])

    def test_practice_requires_consent_and_rejects_cross_tenant_activity(self):
        path = f"/api/mobile/mvp/{self.institution.id}/practice/activities/{self.activity.id}/attempt"
        denied = self.client.post(path, {"result": "unknown"}, content_type="application/json", **self.headers)
        self.assertEqual(denied.status_code, 403)
        ConsentRecord.objects.create(user=self.user, purpose="pilot_practice", policy_version="v1", action="grant")
        accepted = self.client.post(path, {"result": "unknown", "latency_ms": 120}, content_type="application/json", **self.headers)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(accepted.json()["evaluation_mode"], "synthetic_scaffold")

        foreign_concept = SignConcept.objects.create(institution=self.other_institution, code="foreign", label="Foreign")
        foreign_sign = Sign.objects.create(institution=self.other_institution, concept=foreign_concept, sign_id="foreign-v1", gloss="FOREIGN", status=ReviewStatus.VALIDATED)
        foreign_plan = SignPlan.objects.create(institution=self.other_institution, concept=foreign_concept, code="foreign-plan", status=ReviewStatus.VALIDATED)
        foreign_activity = PracticeActivity(institution=self.institution, plan=foreign_plan, sign=foreign_sign)
        PracticeActivity.objects.bulk_create([foreign_activity])
        self.assertEqual(self.client.post(
            f"/api/mobile/mvp/{self.institution.id}/practice/activities/{foreign_activity.id}/attempt",
            {"result": "unknown"}, content_type="application/json", **self.headers
        ).status_code, 404)

    def test_enrollment_requires_membership_and_report_is_tenant_scoped(self):
        cohort = PilotCohort.objects.create(institution=self.institution, name="Cohort", start_date=date.today(), selected_activity_ids=[self.activity.id])
        enrolled = self.client.post(f"/api/mobile/mvp/{self.institution.id}/pilots/{cohort.id}/participants", **self.headers)
        self.assertEqual(enrolled.status_code, 201, enrolled.content)
        ConsentRecord.objects.create(user=self.user, purpose="pilot_practice", policy_version="v1", action="grant")
        PracticeAttempt.objects.create(activity=self.activity, user=self.user, result="unknown", latency_ms=120, consent_status="granted")

        report = self.client.get(f"/api/mobile/mvp/{self.institution.id}/pilots/{cohort.id}/report", **self.headers)
        self.assertEqual(report.status_code, 200, report.content)
        self.assertEqual(report.json()["attempts"]["total"], 1)

        foreign = PilotCohort.objects.create(institution=self.other_institution, name="Foreign", start_date=date.today())
        self.assertEqual(self.client.get(f"/api/mobile/mvp/{self.other_institution.id}/pilots/{foreign.id}/report", **self.headers).status_code, 404)

        Membership.objects.filter(user=self.user, institution=self.institution).update(is_active=False)
        self.assertEqual(self.client.post(f"/api/mobile/mvp/{self.institution.id}/pilots/{cohort.id}/participants", **self.headers).status_code, 404)

    def test_member_lists_only_visible_open_cohorts_and_safe_metadata(self):
        open_cohort = PilotCohort.objects.create(
            institution=self.institution,
            name="Open cohort",
            start_date=date.today(),
            selected_plan_ids=[999],
            selected_activity_ids=[self.activity.id],
        )
        closed = PilotCohort.objects.create(
            institution=self.institution,
            name="Closed cohort",
            start_date=date.today(),
            status=PilotCohort.Status.CLOSED,
        )
        foreign = PilotCohort.objects.create(
            institution=self.other_institution,
            name="Foreign cohort",
            start_date=date.today(),
        )
        response = self.client.get(
            f"/api/mobile/mvp/{self.institution.id}/pilots/cohorts",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([row["id"] for row in response.json()], [open_cohort.id])
        self.assertNotIn("selected_plan_ids", response.json()[0])
        self.assertNotIn("selected_activity_ids", response.json()[0])
        self.assertNotIn(closed.id, [row["id"] for row in response.json()])
        self.assertNotIn(foreign.id, [row["id"] for row in response.json()])

    def test_cohort_listing_hides_foreign_and_inactive_memberships_or_institutions(self):
        path = f"/api/mobile/mvp/{self.other_institution.id}/pilots/cohorts"
        self.assertEqual(self.client.get(path, **self.headers).status_code, 404)
        Membership.objects.filter(user=self.user, institution=self.institution).update(is_active=False)
        self.assertEqual(
            self.client.get(f"/api/mobile/mvp/{self.institution.id}/pilots/cohorts", **self.headers).status_code,
            404,
        )
        membership = Membership.objects.get(user=self.user, institution=self.institution)
        membership.is_active = True
        membership.save(update_fields=("is_active",))
        self.institution.is_active = False
        self.institution.save(update_fields=("is_active",))
        self.assertEqual(
            self.client.get(f"/api/mobile/mvp/{self.institution.id}/pilots/cohorts", **self.headers).status_code,
            404,
        )

    def test_closed_cohort_rejects_enrollment(self):
        cohort = PilotCohort.objects.create(
            institution=self.institution,
            name="Closed",
            start_date=date.today(),
            status=PilotCohort.Status.CLOSED,
        )
        response = self.client.post(
            f"/api/mobile/mvp/{self.institution.id}/pilots/{cohort.id}/participants",
            **self.headers,
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(PilotParticipant.objects.filter(cohort=cohort, user=self.user).exists())

    def test_portal_cohorts_are_role_and_tenant_scoped(self):
        reviewer = User.objects.create_user("reviewer@example.test", "test-password")
        Membership.objects.create(user=reviewer, institution=self.institution, role=Membership.Role.VOCABULARY_REVIEWER)
        self.client.force_login(reviewer)
        read = self.client.get(f"/api/portal/{self.institution.id}/cohorts")
        self.assertEqual(read.status_code, 200, read.content)
        self.assertEqual(self.client.post(
            f"/api/portal/{self.institution.id}/cohorts",
            {"name": "Reviewer cohort", "start_date": str(date.today())},
            content_type="application/json",
        ).status_code, 403)

        manager = User.objects.create_user("manager@example.test", "test-password")
        Membership.objects.create(user=manager, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        self.client.force_login(manager)
        foreign_plan = SignPlan.objects.create(
            institution=self.other_institution,
            concept=SignConcept.objects.create(institution=self.other_institution, code="foreign", label="Foreign"),
            code="foreign-plan",
            status=ReviewStatus.VALIDATED,
        )
        denied = self.client.post(
            f"/api/portal/{self.institution.id}/cohorts",
            {"name": "Cross tenant", "start_date": str(date.today()), "selected_plan_ids": [foreign_plan.id]},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 422)

    def test_portal_admin_validates_selection_and_lifecycle(self):
        admin = User.objects.create_user("admin@example.test", "test-password")
        Membership.objects.create(user=admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        self.client.force_login(admin)
        create = self.client.post(
            f"/api/portal/{self.institution.id}/cohorts",
            {
                "name": "Spring pilot",
                "start_date": str(date.today()),
                "end_date": str(date.today()),
                "selected_plan_ids": [self.activity.plan_id],
                "selected_activity_ids": [self.activity.id],
            },
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 201, create.content)
        cohort_id = create.json()["id"]
        detail = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort_id}")
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertEqual(detail.json()["report"]["attempts"]["total"], 0)
        active = self.client.patch(
            f"/api/portal/{self.institution.id}/cohorts/{cohort_id}",
            {"status": "active"},
            content_type="application/json",
        )
        self.assertEqual(active.status_code, 200, active.content)
        closed = self.client.patch(
            f"/api/portal/{self.institution.id}/cohorts/{cohort_id}",
            {"status": "closed"},
            content_type="application/json",
        )
        self.assertEqual(closed.status_code, 200, closed.content)
        reopened = self.client.patch(
            f"/api/portal/{self.institution.id}/cohorts/{cohort_id}",
            {"status": "active"},
            content_type="application/json",
        )
        self.assertEqual(reopened.status_code, 409)
        bad_dates = self.client.post(
            f"/api/portal/{self.institution.id}/cohorts",
            {"name": "Invalid dates", "start_date": str(date.today()), "end_date": "2020-01-01"},
            content_type="application/json",
        )
        self.assertEqual(bad_dates.status_code, 422)

    def test_portal_admin_manages_tenant_safe_participant_roster(self):
        admin = User.objects.create_user("roster-admin@example.test", "test-password")
        member = User.objects.create_user("learner@example.test", "test-password")
        foreign_member = User.objects.create_user("foreign-learner@example.test", "test-password")
        Membership.objects.create(user=admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        Membership.objects.create(user=member, institution=self.institution, role=Membership.Role.OPERATOR)
        Membership.objects.create(user=foreign_member, institution=self.other_institution, role=Membership.Role.OPERATOR)
        cohort = PilotCohort.objects.create(institution=self.institution, name="Roster", start_date=date.today())
        self.client.force_login(admin)

        members = self.client.get(f"/api/portal/{self.institution.id}/members")
        self.assertEqual(members.status_code, 200, members.content)
        self.assertEqual(sorted(row["user_id"] for row in members.json()), sorted([admin.id, member.id, self.user.id]))
        self.assertNotIn("password", members.json()[0])

        empty = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), [])

        enrolled = self.client.post(
            f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants",
            {"user_id": member.id}, content_type="application/json",
        )
        self.assertEqual(enrolled.status_code, 201, enrolled.content)
        self.assertEqual(enrolled.json()["enrollment_status"], "active")
        self.assertEqual(enrolled.json()["consent_status"], "not_granted")
        duplicate = self.client.post(
            f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants",
            {"user_id": member.id}, content_type="application/json",
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.content)
        self.assertEqual(PilotParticipant.objects.filter(cohort=cohort, user=member).count(), 1)
        self.assertEqual(self.client.post(
            f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants",
            {"user_id": foreign_member.id}, content_type="application/json",
        ).status_code, 404)

        ConsentRecord.objects.create(user=member, purpose="pilot_practice", policy_version="v1", action="grant")
        roster = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants")
        self.assertEqual(roster.status_code, 200)
        self.assertEqual(roster.json()[0]["consent_status"], "granted")
        deactivated = self.client.post(
            f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants/{member.id}/deactivate",
            content_type="application/json",
        )
        self.assertEqual(deactivated.status_code, 200, deactivated.content)
        self.assertEqual(deactivated.json()["enrollment_status"], "inactive")
        self.assertTrue(PilotParticipant.objects.get(cohort=cohort, user=member).deactivated_at)
        self.assertEqual(cohort.participants.filter(status=PilotParticipant.Status.ACTIVE).count(), 0)

    def test_portal_roster_denies_non_admins_and_closed_mutation(self):
        cohort = PilotCohort.objects.create(institution=self.institution, name="Closed roster", start_date=date.today(), status=PilotCohort.Status.CLOSED)
        for role in (Membership.Role.OPERATOR, Membership.Role.VOCABULARY_REVIEWER):
            caller = User.objects.create_user(f"{role}@example.test", "test-password")
            Membership.objects.create(user=caller, institution=self.institution, role=role)
            self.client.force_login(caller)
            self.assertEqual(self.client.get(f"/api/portal/{self.institution.id}/members").status_code, 403)
            self.assertEqual(self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants").status_code, 403)

        admin = User.objects.create_user("closed-admin@example.test", "test-password")
        Membership.objects.create(user=admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        self.client.force_login(admin)
        self.assertEqual(self.client.post(
            f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/participants",
            {"user_id": self.user.id}, content_type="application/json",
        ).status_code, 409)

    def test_portal_assignment_is_validated_and_progress_is_role_scoped(self):
        admin = User.objects.create_user("progress-admin@example.test", "test-password")
        learner = User.objects.create_user("progress-learner@example.test", "test-password")
        inactive_learner = User.objects.create_user("inactive-learner@example.test", "test-password")
        Membership.objects.create(user=admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        Membership.objects.create(user=learner, institution=self.institution, role=Membership.Role.OPERATOR)
        Membership.objects.create(user=inactive_learner, institution=self.institution, role=Membership.Role.OPERATOR)
        cohort = PilotCohort.objects.create(institution=self.institution, name="Progress", start_date=date.today())
        PilotParticipant.objects.create(cohort=cohort, user=learner)
        inactive = PilotParticipant.objects.create(cohort=cohort, user=inactive_learner, status=PilotParticipant.Status.INACTIVE)
        PracticeAttempt.objects.create(activity=self.activity, user=learner, result=PracticeAttempt.Result.CORRECT, latency_ms=100)
        PracticeAttempt.objects.create(activity=self.activity, user=inactive_learner, result=PracticeAttempt.Result.INCORRECT, latency_ms=900)

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/progress").status_code, 403)

        self.client.force_login(admin)
        assignment = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/assignment")
        self.assertEqual(assignment.status_code, 200, assignment.content)
        self.assertEqual(assignment.json()["selected_activity_ids"], [])
        foreign = PracticeActivity.objects.create(
            institution=self.other_institution,
            plan=SignPlan.objects.create(
                institution=self.other_institution,
                concept=SignConcept.objects.create(institution=self.other_institution, code="other", label="Other"),
                code="other-plan",
                status=ReviewStatus.VALIDATED,
            ),
            sign=Sign.objects.create(
                institution=self.other_institution,
                concept=SignConcept.objects.create(institution=self.other_institution, code="other-sign", label="Other sign"),
                sign_id="other-v1",
                gloss="OTHER",
                status=ReviewStatus.VALIDATED,
            ),
        )
        denied = self.client.put(
            f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/assignment",
            {"selected_activity_ids": [foreign.id], "selected_plan_ids": []},
            content_type="application/json",
        )
        self.assertEqual(denied.status_code, 422, denied.content)

        saved = self.client.put(
            f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/assignment",
            {"selected_activity_ids": [self.activity.id], "selected_plan_ids": [self.activity.plan_id]},
            content_type="application/json",
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertEqual(saved.json()["selected_activity_ids"], [self.activity.id])

        progress = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/progress")
        self.assertEqual(progress.status_code, 200, progress.content)
        body = progress.json()
        self.assertEqual(body["summary"]["enrolled_count"], 2)
        self.assertEqual(body["summary"]["active_count"], 1)
        self.assertEqual(body["summary"]["completed_count"], 1)
        self.assertEqual(body["summary"]["attempts"]["total"], 1)
        self.assertEqual(body["summary"]["attempts"]["correct"], 1)
        self.assertEqual(body["summary"]["completion_rate"], 1.0)
        self.assertEqual(len(body["participants"]), 2)
        self.assertNotIn("raw", body["participants"][0])
        self.assertNotIn("password", body["participants"][0])

    def test_portal_progress_empty_cohort_and_zero_attempt_participant(self):
        admin = User.objects.create_user("empty-progress-admin@example.test", "test-password")
        learner = User.objects.create_user("zero-attempt@example.test", "test-password")
        Membership.objects.create(user=admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        Membership.objects.create(user=learner, institution=self.institution, role=Membership.Role.OPERATOR)
        empty = PilotCohort.objects.create(institution=self.institution, name="Empty", start_date=date.today())
        self.client.force_login(admin)
        response = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{empty.id}/progress")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["summary"]["active_count"], 0)
        self.assertEqual(response.json()["summary"]["completion_rate"], 0.0)
        PilotParticipant.objects.create(cohort=empty, user=learner)
        response = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{empty.id}/progress")
        self.assertEqual(response.json()["summary"]["active_count"], 1)
        self.assertEqual(response.json()["summary"]["attempts"]["total"], 0)
        self.assertFalse(response.json()["participants"][0]["completed"])

    def test_portal_progress_export_is_deterministic_safe_and_role_scoped(self):
        admin = User.objects.create_user("=admin@example.test", "test-password")
        reviewer = User.objects.create_user("reviewer-export@example.test", "test-password")
        operator = User.objects.create_user("operator-export@example.test", "test-password")
        learner = User.objects.create_user("+learner@example.test", "test-password")
        Membership.objects.create(user=admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        Membership.objects.create(user=reviewer, institution=self.institution, role=Membership.Role.VOCABULARY_REVIEWER)
        Membership.objects.create(user=operator, institution=self.institution, role=Membership.Role.OPERATOR)
        Membership.objects.create(user=learner, institution=self.institution, role=Membership.Role.OPERATOR)
        cohort = PilotCohort.objects.create(
            institution=self.institution,
            name="=Cohort formula",
            start_date=date.today(),
            selected_activity_ids=[self.activity.id],
        )
        PilotParticipant.objects.create(cohort=cohort, user=learner)
        PracticeAttempt.objects.create(activity=self.activity, user=learner, result=PracticeAttempt.Result.CORRECT, latency_ms=120)

        self.client.force_login(operator)
        self.assertEqual(self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/progress/export").status_code, 403)

        self.client.force_login(reviewer)
        response = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/progress/export")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertEqual(response["Content-Disposition"], f'attachment; filename="cohort-{cohort.id}-progress.csv"')
        lines = response.content.decode().splitlines()
        self.assertEqual(lines[0].split(",")[0], "institution_id")
        self.assertIn("participant_identifier", lines[0])
        self.assertIn("'=Cohort formula", lines[1])
        self.assertIn("'+learner@example.test", lines[1])
        self.assertNotIn("password", response.content.decode().lower())
        self.assertNotIn("latency_ms, result", response.content.decode())
        self.assertNotIn("evaluation_mode", response.content.decode())

        other_cohort = PilotCohort.objects.create(institution=self.other_institution, name="Other", start_date=date.today())
        self.assertEqual(self.client.get(f"/api/portal/{self.other_institution.id}/cohorts/{other_cohort.id}/progress/export").status_code, 404)

    def test_portal_progress_export_has_header_and_aggregate_row_for_empty_cohort(self):
        admin = User.objects.create_user("empty-export-admin@example.test", "test-password")
        Membership.objects.create(user=admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        cohort = PilotCohort.objects.create(institution=self.institution, name="Empty", start_date=date.today())
        self.client.force_login(admin)
        response = self.client.get(f"/api/portal/{self.institution.id}/cohorts/{cohort.id}/progress/export")
        self.assertEqual(response.status_code, 200, response.content)
        lines = response.content.decode().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn(",0,0,0,0,0,0.0,0,0,0,0,0.0,,,", lines[1])
