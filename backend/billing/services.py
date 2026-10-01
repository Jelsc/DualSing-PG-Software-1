import os
from datetime import datetime, timezone

import stripe
from django.db import transaction

from accounts.models import AccessEntitlement, AuditRecord, Institution, User
from .models import ProcessedStripeEvent, Subscription


def stripe_configured():
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


class ExistingSubscriptionError(Exception):
    pass


def _price_id(plan):
    return os.environ.get("STRIPE_PLUS_PRICE_ID" if plan == Subscription.Plan.PLUS else "STRIPE_ENTERPRISE_PRICE_ID")


def _owner_subscription_query(user, institution):
    return Subscription.objects.filter(
        user=user if institution is None else None,
        institution=institution,
        status__in=(Subscription.Status.ACTIVE, Subscription.Status.INCOMPLETE),
    )


def create_checkout(*, user, plan, institution=None):
    if not stripe_configured():
        return None
    price_id = os.environ.get("STRIPE_PLUS_PRICE_ID" if plan == Subscription.Plan.PLUS else "STRIPE_ENTERPRISE_PRICE_ID")
    if not price_id:
        return None
    if _owner_subscription_query(user, institution).filter(plan=plan).exists():
        raise ExistingSubscriptionError("An active or incomplete subscription already exists for this owner")
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    previous = Subscription.objects.filter(
        user=user if institution is None else None,
        institution=institution,
        stripe_customer_id__gt="",
    ).order_by("-updated_at").first()
    customer = stripe.Customer.retrieve(previous.stripe_customer_id) if previous else stripe.Customer.create(
        email=user.email,
        metadata={"dualsign_user_id": str(user.id), **({"dualsign_institution_id": str(institution.id)} if institution else {})},
    )
    owner_type = "institution" if institution else "user"
    owner_metadata = {"owner_type": owner_type, "user_id": str(user.id), **({"institution_id": str(institution.id)} if institution else {})}
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer.id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=os.environ.get("STRIPE_SUCCESS_URL", "http://localhost:3000/billing/success"),
        cancel_url=os.environ.get("STRIPE_CANCEL_URL", "http://localhost:3000/billing/cancel"),
        metadata={"plan": plan, **owner_metadata},
        subscription_data={"metadata": {"plan": plan, **owner_metadata}},
    )
    subscription_id = session.get("subscription")
    if isinstance(subscription_id, str) and subscription_id:
        Subscription.objects.create(
            user=user if institution is None else None,
            institution=institution,
            plan=plan,
            stripe_customer_id=customer.id,
            stripe_subscription_id=subscription_id,
            status=Subscription.Status.INCOMPLETE,
        )
    return {"checkout_url": session.url, "session_id": session.id}


def _dt(value):
    return datetime.fromtimestamp(value, tz=timezone.utc) if value else None


@transaction.atomic
def process_event(event):
    event_id = event["id"]
    if ProcessedStripeEvent.objects.filter(event_id=event_id).exists():
        return False
    event_type = event["type"]
    obj = event["data"]["object"]
    if event_type == "checkout.session.completed":
        subscription_id = obj.get("subscription")
        if subscription_id:
            sync_subscription(subscription_id, obj.get("customer"), obj.get("metadata", {}), {"status": Subscription.Status.ACTIVE})
    elif event_type in {"invoice.paid", "invoice.payment_failed"}:
        subscription_id = obj.get("subscription")
        if subscription_id:
            sub = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
            if sub:
                sub.status = Subscription.Status.ACTIVE if event_type == "invoice.paid" else Subscription.Status.PAST_DUE
                sub.save(update_fields=("status", "updated_at"))
                sync_entitlement(sub)
    elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
        metadata = obj.get("metadata", {})
        sub = sync_subscription(obj["id"], obj.get("customer"), metadata, obj)
        if event_type == "customer.subscription.deleted":
            sub.status = Subscription.Status.CANCELED
            sub.save(update_fields=("status", "updated_at"))
            sync_entitlement(sub)
    ProcessedStripeEvent.objects.create(event_id=event_id, event_type=event_type)
    return True


def sync_subscription(subscription_id, customer_id, metadata, stripe_object=None):
    if not stripe_object or not stripe_object.get("items", {}).get("data"):
        stripe_object = _retrieve_subscription(subscription_id)
    existing = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
    plan = metadata.get("plan")
    owner_type = metadata.get("owner_type")
    user = User.objects.filter(pk=metadata.get("user_id"), is_active=True).first()
    institution = Institution.objects.filter(pk=metadata.get("institution_id"), is_active=True).first()
    expected_price = _price_id(plan)
    item_prices = [item.get("price", {}).get("id") for item in stripe_object.get("items", {}).get("data", [])]
    if plan not in Subscription.Plan.values or owner_type not in {"user", "institution"} or not expected_price:
        raise ValueError("Stripe subscription metadata is invalid")
    if expected_price not in item_prices or stripe_object.get("customer") != customer_id:
        raise ValueError("Stripe subscription does not match configured owner or price")
    if owner_type == "user" and (plan != Subscription.Plan.PLUS or user is None or institution is not None):
        raise ValueError("Stripe subscription owner is invalid")
    if owner_type == "institution" and (plan != Subscription.Plan.ENTERPRISE or institution is None or user is None):
        raise ValueError("Stripe subscription owner is invalid")
    if existing and existing.stripe_customer_id and existing.stripe_customer_id != customer_id:
        raise ValueError("Stripe customer changed for subscription")
    sub, _ = Subscription.objects.update_or_create(
        stripe_subscription_id=subscription_id,
        defaults={"user": user, "institution": institution, "plan": plan, "stripe_customer_id": customer_id or "", "status": stripe_object.get("status", Subscription.Status.ACTIVE), "current_period_start": _dt(stripe_object.get("current_period_start")), "current_period_end": _dt(stripe_object.get("current_period_end")), "cancel_at_period_end": bool(stripe_object.get("cancel_at_period_end"))},
    )
    sync_entitlement(sub)
    return sub


def _retrieve_subscription(subscription_id):
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    return stripe.Subscription.retrieve(subscription_id)


def sync_entitlement(subscription):
    lookup = {"user": subscription.user} if subscription.user_id else {"institution": subscription.institution}
    owner_subscriptions = Subscription.objects.filter(**lookup)
    if subscription.institution_id:
        owner_subscriptions = owner_subscriptions.filter(institution__is_active=True)
    active = owner_subscriptions.filter(status=Subscription.Status.ACTIVE).exists()
    origin = AccessEntitlement.Origin.PLUS if subscription.user_id and active else AccessEntitlement.Origin.ENTERPRISE_ACCESS if subscription.institution_id and active else AccessEntitlement.Origin.FREE
    entitlement, _ = AccessEntitlement.objects.update_or_create(defaults={"origin": origin}, **lookup)
    return entitlement
