from django.urls import path

from .api import api
from billing.webhooks import stripe_webhook

urlpatterns = [path("api/billing/webhook", stripe_webhook), path("api/", api.urls)]
