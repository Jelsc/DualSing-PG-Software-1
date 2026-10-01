import os

from django.contrib.auth.decorators import login_required
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from accounts.authentication import LiveUserJWTAuth
from accounts.models import AccessEntitlement, Institution
from accounts.policies import require_active_membership
from .models import Subscription
from .services import ExistingSubscriptionError, create_checkout, stripe_configured

web = Router(auth=django_auth)
mobile = Router(auth=LiveUserJWTAuth())


def status_for(user, institution_id=None):
    entitlement = AccessEntitlement.objects.filter(user=user).first() if institution_id is None else None
    enterprise = AccessEntitlement.objects.filter(institution_id=institution_id, institution__is_active=True, institution__memberships__user=user, institution__memberships__is_active=True, origin=AccessEntitlement.Origin.ENTERPRISE_ACCESS).first() if institution_id else None
    subscriptions = Subscription.objects.filter(user=user) if institution_id is None else Subscription.objects.filter(institution_id=institution_id, institution__is_active=True)
    current = subscriptions.filter(status=Subscription.Status.ACTIVE).order_by("-updated_at").first()
    current = current or subscriptions.filter(status=Subscription.Status.INCOMPLETE).order_by("-updated_at").first()
    current = current or subscriptions.order_by("-updated_at").first()
    return {"origin": (enterprise or entitlement).origin if (enterprise or entitlement) else "free", "subscription_status": current.status if current else None, "current_period_end": current.current_period_end.isoformat() if current and current.current_period_end else None, "cancel_at_period_end": current.cancel_at_period_end if current else False}


def checkout_or_unavailable(user, plan, institution=None):
    try:
        result = create_checkout(user=user, plan=plan, institution=institution)
    except ExistingSubscriptionError as error:
        raise HttpError(409, str(error))
    if result is None:
        raise HttpError(503, "Stripe billing is not configured for this environment")
    return result


@mobile.post("/plus/checkout")
def mobile_plus_checkout(request):
    return checkout_or_unavailable(request.auth, Subscription.Plan.PLUS)


@mobile.get("/status")
def mobile_status(request):
    return status_for(request.auth)


@web.get("/status")
def web_status(request):
    return status_for(request.user)


@web.post("/enterprise/{institution_id}/checkout")
def enterprise_checkout(request, institution_id: int):
    if not require_active_membership(request.user, institution_id):
        raise HttpError(404, "Institution not found")
    institution = Institution.objects.get(pk=institution_id)
    membership = institution.memberships.filter(user=request.user, is_active=True).first()
    if membership is None:
        raise HttpError(404, "Institution not found")
    if membership.role != "institution_admin":
        raise HttpError(403, "Institution administrator required")
    return checkout_or_unavailable(request.user, Subscription.Plan.ENTERPRISE, institution)


@web.get("/enterprise/{institution_id}/status")
def enterprise_status(request, institution_id: int):
    if not require_active_membership(request.user, institution_id):
        raise HttpError(404, "Institution not found")
    return status_for(request.user, institution_id)
