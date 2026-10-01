from django.db.models import Q

from accounts.models import ConsentRecord
from vocabulary.models import ConceptAlias, ReviewStatus, SignConcept

from .models import PracticeActivity, PracticeAttempt


def normalized(value):
    return " ".join(value.casefold().split())


def has_consent(user, purpose="pilot_practice"):
    latest = ConsentRecord.objects.filter(user=user, purpose=purpose).order_by("-recorded_at", "-id").first()
    return latest is not None and latest.action == ConsentRecord.Action.GRANT


def find_controlled_concept(institution_id, value):
    token = normalized(value)
    return SignConcept.objects.filter(
        Q(code__iexact=token) | Q(aliases__normalized_alias=token),
        institution_id=institution_id,
    ).distinct().first()


def playback_steps(plan):
    return [
        {
            "position": item.position,
            "stable_sign_id": item.sign.sign_id,
            "clip_key": f"sign:{item.sign.sign_id}",
            "asset_available": False,
            "gloss": item.sign.gloss,
        }
        for item in plan.items.select_related("sign").all()
    ]


def percentile(values, percentile):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((percentile / 100) * len(ordered) + 0.5) - 1))
    return ordered[index]
