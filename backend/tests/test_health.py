from django.test import Client, SimpleTestCase


class HealthEndpointTests(SimpleTestCase):
    def test_health_endpoint_is_routed_and_returns_ok(self):
        response = Client().get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
