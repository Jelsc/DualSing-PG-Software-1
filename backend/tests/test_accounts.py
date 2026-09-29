from django.test import Client, TestCase
from ninja_jwt.tokens import AccessToken

from accounts.models import AuditRecord, ConsentRecord, Institution, Membership, User


class IdentityAndTenantTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.member = User.objects.create_user("member@example.test", "correct-horse")
        self.other = User.objects.create_user("other@example.test", "correct-horse")
        self.institution_a = Institution.objects.create(name="Institution A")
        self.institution_b = Institution.objects.create(name="Institution B")
        Membership.objects.create(
            user=self.member,
            institution=self.institution_a,
            role=Membership.Role.OPERATOR,
        )

    def get_access_token(self, user=None):
        return str(AccessToken.for_user(user or self.member))

    def test_custom_email_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user("USER@Example.Test", "plain-test-password")

        self.assertEqual(user.email, "user@example.test")
        self.assertNotEqual(user.password, "plain-test-password")
        self.assertTrue(user.check_password("plain-test-password"))

    def test_web_api_denies_unauthenticated_and_enforces_csrf_on_login(self):
        denied = self.client.get("/api/web/me")
        self.assertEqual(denied.status_code, 401)

        csrf = Client(enforce_csrf_checks=True)
        token = csrf.get("/api/web/csrf").json()["csrf_token"]
        payload = {"email": self.member.email, "password": "correct-horse"}
        missing = csrf.post("/api/web/login", payload, content_type="application/json")
        self.assertEqual(missing.status_code, 403)
        accepted = csrf.post(
            "/api/web/login",
            payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(accepted.status_code, 200)

    def test_web_login_failure_does_not_disclose_email_existence(self):
        existing = self.client.post(
            "/api/web/login",
            {"email": self.member.email, "password": "wrong"},
            content_type="application/json",
        )
        missing = self.client.post(
            "/api/web/login",
            {"email": "missing@example.test", "password": "wrong"},
            content_type="application/json",
        )

        self.assertEqual(existing.status_code, missing.status_code)
        self.assertEqual(existing.json(), missing.json())

    def test_login_failure_audit_contains_no_supplied_email_or_password(self):
        self.client.post(
            "/api/mobile/token",
            {"email": "private@example.test", "password": "never-store-this"},
            content_type="application/json",
        )
        event = AuditRecord.objects.get(event_type="auth.mobile_login_failed")
        self.assertEqual(event.actor, None)
        self.assertEqual(event.metadata, {})

    def test_mobile_refresh_rotates_and_revokes_old_refresh_token(self):
        issued = self.client.post(
            "/api/mobile/token",
            {"email": self.member.email, "password": "correct-horse"},
            content_type="application/json",
        )
        self.assertEqual(issued.status_code, 200)
        first = issued.json()
        self.assertEqual(
            self.client.get("/api/mobile/me", HTTP_AUTHORIZATION=f"Bearer {first['access']}").status_code,
            200,
        )

        rotated = self.client.post(
            "/api/mobile/token/refresh",
            {"refresh": first["refresh"]},
            content_type="application/json",
        )
        self.assertEqual(rotated.status_code, 200)
        rejected = self.client.post(
            "/api/mobile/token/refresh",
            {"refresh": first["refresh"]},
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 401)

        revoked = self.client.post(
            "/api/mobile/token/revoke",
            {"refresh": rotated.json()["refresh"]},
            content_type="application/json",
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/mobile/token/refresh",
                {"refresh": rotated.json()["refresh"]},
                content_type="application/json",
            ).status_code,
            401,
        )

    def test_expired_jwt_and_inactive_users_are_denied(self):
        token = AccessToken.for_user(self.member)
        token["exp"] = 0
        expired_response = self.client.get(
            "/api/mobile/me", HTTP_AUTHORIZATION=f"Bearer {token}"
        )
        self.assertEqual(expired_response.status_code, 401)

        self.member.is_active = False
        self.member.save(update_fields=("is_active",))
        inactive_response = self.client.get(
            "/api/mobile/me", HTTP_AUTHORIZATION=f"Bearer {self.get_access_token()}"
        )
        self.assertEqual(inactive_response.status_code, 401)

    def test_membership_scope_denies_cross_tenant_and_exposes_live_role(self):
        token = self.get_access_token()
        own = self.client.get(
            f"/api/institutions/{self.institution_a.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        foreign = self.client.get(
            f"/api/institutions/{self.institution_b.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        current = self.client.get("/api/mobile/me", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(own.status_code, 200)
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(current.json()["memberships"][0]["role"], Membership.Role.OPERATOR)

        Membership.objects.filter(user=self.member, institution=self.institution_a).update(is_active=False)
        self.assertEqual(
            self.client.get(
                f"/api/institutions/{self.institution_a.id}",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ).status_code,
            404,
        )

    def test_platform_superuser_bypasses_tenant_scope_and_can_create_institution(self):
        root = User.objects.create_superuser("root@example.test", "root-test-password")
        token = self.get_access_token(root)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        self.assertEqual(self.client.get("/api/institutions", **headers).status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/institutions/{self.institution_b.id}", **headers).status_code,
            200,
        )
        created = self.client.post(
            "/api/institutions",
            {"name": "New Institution"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(created.status_code, 201, created.content)

        member_create = self.client.post(
            "/api/institutions",
            {"name": "Forbidden Institution"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.get_access_token()}",
        )
        self.assertEqual(member_create.status_code, 403)

    def test_consent_and_audit_records_are_append_only_and_do_not_store_credentials(self):
        response = self.client.post(
            "/api/mobile/consents",
            {"purpose": "service", "policy_version": "v1", "action": "grant"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.get_access_token()}",
        )
        self.assertEqual(response.status_code, 201)
        consent = ConsentRecord.objects.get(pk=response.json()["id"])
        audit = AuditRecord.objects.get(subject_id=str(consent.id))
        self.assertEqual(consent.action, ConsentRecord.Action.GRANT)
        self.assertNotIn("password", str(audit.metadata).lower())
        with self.assertRaises(ValueError):
            consent.delete()
        with self.assertRaises(ValueError):
            audit.delete()
