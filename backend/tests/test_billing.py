import json
import os
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from ninja_jwt.tokens import AccessToken

from accounts.models import AccessEntitlement, Institution, Membership, User
from billing.models import ProcessedStripeEvent, Subscription
from billing.services import sync_subscription


class BillingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("billing@example.test", "correct-horse")
        self.admin = User.objects.create_user("admin@example.test", "correct-horse")
        self.institution = Institution.objects.create(name="Billing tenant")
        Membership.objects.create(user=self.admin, institution=self.institution, role=Membership.Role.INSTITUTION_ADMIN)
        self.token = str(AccessToken.for_user(self.user))

    def test_individual_checkout_is_unavailable_without_configuration(self):
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "", "STRIPE_PLUS_PRICE_ID": ""}, clear=False):
            response = self.client.post("/api/mobile/billing/plus/checkout", HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(response.status_code, 503)
        self.assertIn("not configured", response.json()["detail"])

    @patch("billing.services.stripe.checkout.Session.create")
    @patch("billing.services.stripe.Customer.create")
    def test_individual_checkout_returns_hosted_url(self, customer_create, session_create):
        customer_create.return_value.id = "cus_test"
        session_create.return_value.id = "cs_test"
        session_create.return_value.url = "https://checkout.stripe.test/session"
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test", "STRIPE_PLUS_PRICE_ID": "price_plus"}, clear=False):
            response = self.client.post("/api/mobile/billing/plus/checkout", HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checkout_url"], "https://checkout.stripe.test/session")

    def test_enterprise_checkout_requires_active_admin_membership(self):
        Membership.objects.create(user=self.user, institution=self.institution, role=Membership.Role.OPERATOR)
        self.client.force_login(self.user)
        response = self.client.post(f"/api/billing/enterprise/{self.institution.id}/checkout")
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.admin)
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "", "STRIPE_ENTERPRISE_PRICE_ID": ""}, clear=False):
            response = self.client.post(f"/api/billing/enterprise/{self.institution.id}/checkout")
        self.assertEqual(response.status_code, 503)

    def test_cross_tenant_status_is_denied(self):
        other = Institution.objects.create(name="Other tenant")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/api/billing/enterprise/{other.id}/status").status_code, 404)

    def test_enterprise_status_is_scoped_to_selected_institution(self):
        AccessEntitlement.objects.create(institution=self.institution, origin=AccessEntitlement.Origin.ENTERPRISE_ACCESS)
        self.client.force_login(self.admin)
        response = self.client.get(f"/api/billing/enterprise/{self.institution.id}/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["origin"], "enterprise_access")

    def test_invalid_signature_does_not_process_event(self):
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False):
            response = self.client.post("/api/billing/webhook", b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="bad")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ProcessedStripeEvent.objects.count(), 0)

    @patch("billing.services.stripe.Subscription.retrieve")
    @patch("billing.webhooks.stripe.Webhook.construct_event")
    def test_verified_event_is_idempotent_and_activates_plus(self, construct_event, subscription_retrieve):
        construct_event.return_value = {"id": "evt_test", "type": "checkout.session.completed", "data": {"object": {"subscription": "sub_test", "customer": "cus_test", "metadata": {"plan": "plus", "owner_type": "user", "user_id": str(self.user.id)}}}}
        subscription_retrieve.return_value = {"id": "sub_test", "customer": "cus_test", "status": "active", "items": {"data": [{"price": {"id": "price_plus"}}]}}
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test", "STRIPE_PLUS_PRICE_ID": "price_plus"}, clear=False):
            first = self.client.post("/api/billing/webhook", b"verified", content_type="application/json", HTTP_STRIPE_SIGNATURE="valid")
            second = self.client.post("/api/billing/webhook", b"verified", content_type="application/json", HTTP_STRIPE_SIGNATURE="valid")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(ProcessedStripeEvent.objects.count(), 1)
        self.assertEqual(AccessEntitlement.objects.get(user=self.user).origin, AccessEntitlement.Origin.PLUS)

    @patch("billing.services.sync_subscription", side_effect=ValueError("temporary failure"))
    @patch("billing.webhooks.stripe.Webhook.construct_event")
    def test_failed_webhook_is_retryable(self, construct_event, sync):
        construct_event.return_value = {"id": "evt_retry", "type": "checkout.session.completed", "data": {"object": {"subscription": "sub_retry", "customer": "cus_test", "metadata": {}}}}
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False):
            response = self.client.post("/api/billing/webhook", b"verified", content_type="application/json", HTTP_STRIPE_SIGNATURE="valid")
        self.assertEqual(response.status_code, 500)
        self.assertFalse(ProcessedStripeEvent.objects.filter(event_id="evt_retry").exists())

    def test_newer_active_subscription_wins_over_old_past_due(self):
        old = Subscription.objects.create(user=self.user, plan=Subscription.Plan.PLUS, stripe_subscription_id="sub_old", status=Subscription.Status.PAST_DUE)
        AccessEntitlement.objects.create(user=self.user, origin=AccessEntitlement.Origin.PLUS)
        Subscription.objects.create(user=self.user, plan=Subscription.Plan.PLUS, stripe_subscription_id="sub_new", status=Subscription.Status.ACTIVE)
        from billing.services import sync_entitlement
        sync_entitlement(old)
        self.assertEqual(AccessEntitlement.objects.get(user=self.user).origin, AccessEntitlement.Origin.PLUS)

    def test_wrong_price_and_owner_metadata_are_rejected(self):
        with patch.dict(os.environ, {"STRIPE_PLUS_PRICE_ID": "price_plus"}, clear=False):
            with self.assertRaises(ValueError):
                sync_subscription("sub_wrong_price", "cus_test", {"plan": "plus", "owner_type": "user", "user_id": str(self.user.id)}, {"customer": "cus_test", "status": "active", "items": {"data": [{"price": {"id": "price_other"}}]}})
            with self.assertRaises(ValueError):
                sync_subscription("sub_wrong_owner", "cus_test", {"plan": "enterprise", "owner_type": "user", "user_id": str(self.user.id)}, {"customer": "cus_test", "status": "active", "items": {"data": [{"price": {"id": "price_plus"}}]}})

    def test_capability_json_cannot_override_server_derived_access(self):
        entitlement = AccessEntitlement.objects.create(user=self.user, origin=AccessEntitlement.Origin.FREE, capabilities={"plus_features": True, "enterprise_features": True})
        self.client.force_login(self.user)
        response = self.client.get("/api/mobile/me", HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertFalse(response.json()["entitlement"]["capabilities"]["plus_features"])
        self.assertFalse(response.json()["entitlement"]["capabilities"]["enterprise_features"])

    def test_inactive_institution_is_not_billable(self):
        self.institution.is_active = False
        self.institution.save(update_fields=("is_active",))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/api/billing/enterprise/{self.institution.id}/status").status_code, 404)

    def test_enterprise_checkout_rejects_duplicate_active_subscription(self):
        Subscription.objects.create(institution=self.institution, plan=Subscription.Plan.ENTERPRISE, stripe_subscription_id="sub_existing", status=Subscription.Status.ACTIVE)
        self.client.force_login(self.admin)
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test", "STRIPE_ENTERPRISE_PRICE_ID": "price_enterprise"}, clear=False):
            response = self.client.post(f"/api/billing/enterprise/{self.institution.id}/checkout")
        self.assertEqual(response.status_code, 409)

    @patch("billing.webhooks.stripe.Webhook.construct_event")
    def test_payment_failure_revokes_plus_access(self, construct_event):
        subscription = Subscription.objects.create(user=self.user, plan=Subscription.Plan.PLUS, stripe_subscription_id="sub_failed", status=Subscription.Status.ACTIVE)
        AccessEntitlement.objects.create(user=self.user, origin=AccessEntitlement.Origin.PLUS)
        construct_event.return_value = {"id": "evt_failed", "type": "invoice.payment_failed", "data": {"object": {"subscription": subscription.stripe_subscription_id}}}
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}, clear=False):
            response = self.client.post("/api/billing/webhook", b"verified", content_type="application/json", HTTP_STRIPE_SIGNATURE="valid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AccessEntitlement.objects.get(user=self.user).origin, AccessEntitlement.Origin.FREE)

    def test_status_does_not_accept_client_plan(self):
        response = self.client.get("/api/mobile/billing/status", HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["origin"], "free")
