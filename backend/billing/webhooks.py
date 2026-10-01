import os

import stripe
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .services import process_event


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST" or not os.environ.get("STRIPE_WEBHOOK_SECRET"):
        return JsonResponse({"detail": "Webhook unavailable"}, status=503)
    try:
        event = stripe.Webhook.construct_event(request.body, request.headers.get("Stripe-Signature", ""), os.environ["STRIPE_WEBHOOK_SECRET"])
    except (ValueError, stripe.error.SignatureVerificationError):
        return JsonResponse({"detail": "Invalid webhook signature"}, status=400)
    try:
        process_event(event)
    except Exception:
        return JsonResponse({"detail": "Webhook processing failed"}, status=500)
    return JsonResponse({"received": True})
