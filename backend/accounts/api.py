from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.contrib.auth.password_validation import validate_password
from django.middleware.csrf import get_token
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth
from ninja_jwt.tokens import RefreshToken
from ninja_jwt.exceptions import TokenError

from .authentication import LiveUserJWTAuth
from .models import AccessEntitlement, AuditRecord, ConsentRecord, Institution
from .policies import (
    active_memberships,
    can_create_institution,
    can_view_institution,
    is_platform_admin,
    require_active_membership,
    require_platform_staff,
)
from .security import require_csrf
from .schemas import (
    ConsentIn,
    ConsentOut,
    CredentialsIn,
    RegistrationIn,
    AccessEntitlementOut,
    InstitutionIn,
    InstitutionOut,
    RefreshIn,
)
from billing.api import status_for

web = Router()
session = Router(auth=django_auth)
mobile = Router()
protected = Router(auth=LiveUserJWTAuth())
institutions = Router()


@web.get("/csrf")
def csrf_token(request):
    return {"csrf_token": get_token(request)}


@web.post("/login")
def web_login(request, payload: CredentialsIn):
    require_csrf(request)
    user = authenticate(request, email=payload.email.strip().lower(), password=payload.password)
    if user is None:
        AuditRecord.objects.create(event_type="auth.web_login_failed")
        raise HttpError(401, "Invalid email or password")
    login(request, user)
    AuditRecord.objects.create(actor=user, event_type="auth.web_login")
    return {"user": {"id": user.id, "email": user.email}}


@web.post("/logout")
def web_logout(request):
    require_csrf(request)
    if request.user.is_authenticated:
        AuditRecord.objects.create(actor=request.user, event_type="auth.web_logout")
    logout(request)
    return {"status": "ok"}


@session.get("/me")
def session_me(request):
    return {
        "user": {"id": request.user.id, "email": request.user.email},
        "memberships": [
            {"institution_id": item.institution_id, "institution_name": item.institution.name, "role": item.role}
            for item in active_memberships(request.user)
        ],
    }


def entitlement_output(user):
    entitlement = AccessEntitlement.objects.filter(user=user).first()
    enterprise = AccessEntitlement.objects.filter(
        institution__memberships__user=user,
        institution__memberships__is_active=True,
        institution__is_active=True,
        origin=AccessEntitlement.Origin.ENTERPRISE_ACCESS,
    ).first()
    if entitlement is None and enterprise is not None:
        entitlement = enterprise
    if entitlement is None:
        return {
            "origin": AccessEntitlement.Origin.FREE,
            "capabilities": {"mobile_access": True, "plus_features": False, "enterprise_features": False},
        }
    capabilities = {
        "mobile_access": True,
        "plus_features": entitlement.origin == AccessEntitlement.Origin.PLUS,
        "enterprise_features": entitlement.origin == AccessEntitlement.Origin.ENTERPRISE_ACCESS,
    }
    return {"origin": entitlement.origin, "capabilities": capabilities}


@session.get("/backoffice/boundary")
def backoffice_boundary(request):
    if not require_platform_staff(request.user):
        raise HttpError(403, "DualSign platform staff required")
    return {"audience": "dualsign_backoffice", "entitlement": entitlement_output(request.user), "billing": status_for(request.user)}


@session.get("/portal/{institution_id}/boundary", response=AccessEntitlementOut)
def portal_boundary(request, institution_id: int):
    if not require_active_membership(request.user, institution_id):
        raise HttpError(404, "Institution not found")
    return entitlement_output(request.user)


@mobile.post("/token")
def issue_mobile_token(request, payload: CredentialsIn):
    user = authenticate(request, email=payload.email.strip().lower(), password=payload.password)
    if user is None:
        AuditRecord.objects.create(event_type="auth.mobile_login_failed")
        raise HttpError(401, "Invalid email or password")
    refresh = RefreshToken.for_user(user)
    AuditRecord.objects.create(actor=user, event_type="auth.mobile_token_issued")
    return {"access": str(refresh.access_token), "refresh": str(refresh), "token_type": "Bearer"}


@mobile.post("/register")
def register_mobile_user(request, payload: RegistrationIn):
    email = payload.email.strip().lower()
    if not email:
        raise HttpError(422, "A valid email address is required")
    try:
        validate_email(email)
    except ValidationError:
        raise HttpError(422, "A valid email address is required")
    if payload.password != payload.password_confirmation:
        raise HttpError(422, "Passwords do not match")
    try:
        validate_password(payload.password)
    except ValidationError as error:
        raise HttpError(422, " ".join(error.messages))
    if get_user_model().objects.filter(email=email).exists():
        raise HttpError(409, "An account with that email already exists")
    try:
        with transaction.atomic():
            user = get_user_model().objects.create_user(email=email, password=payload.password)
    except IntegrityError:
        raise HttpError(409, "An account with that email already exists")
    refresh = RefreshToken.for_user(user)
    AuditRecord.objects.create(actor=user, event_type="auth.mobile_registered")
    return {"access": str(refresh.access_token), "refresh": str(refresh), "token_type": "Bearer"}


@mobile.post("/token/refresh")
def refresh_mobile_token(request, payload: RefreshIn):
    try:
        old_refresh = RefreshToken(payload.refresh)
        user = get_user_model().objects.get(pk=old_refresh["user_id"], is_active=True)
        old_refresh.blacklist()
        replacement = RefreshToken.for_user(user)
        return {"access": str(replacement.access_token), "refresh": str(replacement), "token_type": "Bearer"}
    except (TokenError, ObjectDoesNotExist, KeyError):
        raise HttpError(401, "Invalid or revoked refresh token")


@mobile.post("/token/revoke")
def revoke_mobile_token(request, payload: RefreshIn):
    try:
        token = RefreshToken(payload.refresh)
        token.blacklist()
    except (TokenError, ObjectDoesNotExist, KeyError):
        raise HttpError(401, "Invalid refresh token")
    return {"status": "revoked"}


@protected.get("/me")
def mobile_me(request):
    user = request.auth
    return {
        "user": {"id": user.id, "email": user.email},
        "entitlement": entitlement_output(user),
        "memberships": [
            {"institution_id": item.institution_id, "institution_name": item.institution.name, "role": item.role}
            for item in active_memberships(user)
        ],
    }


@protected.post("/consents", response={201: ConsentOut})
def record_consent(request, payload: ConsentIn):
    if payload.action not in ConsentRecord.Action.values:
        raise HttpError(422, "Invalid consent action")
    consent = ConsentRecord.objects.create(
        user=request.auth,
        purpose=payload.purpose,
        policy_version=payload.policy_version,
        action=payload.action,
    )
    AuditRecord.objects.create(actor=request.auth, event_type="consent.recorded", subject_type="consent", subject_id=str(consent.id))
    return 201, consent


@institutions.get("")
def list_institutions(request):
    if is_platform_admin(request.auth):
        rows = Institution.objects.filter(is_active=True)
    else:
        rows = Institution.objects.filter(
            memberships__in=active_memberships(request.auth), is_active=True
        ).distinct()
    return list(rows.values("id", "name"))


@institutions.get("/{institution_id}", response=InstitutionOut)
def institution_detail(request, institution_id: int):
    institution = can_view_institution(request.auth, institution_id)
    if institution is None:
        raise HttpError(404, "Institution not found")
    return institution


@institutions.post("", response={201: InstitutionOut})
def create_institution(request, payload: InstitutionIn):
    if not can_create_institution(request.auth):
        raise HttpError(403, "Platform administrator required")
    institution = Institution.objects.create(name=payload.name.strip())
    AuditRecord.objects.create(
        actor=request.auth,
        institution=institution,
        event_type="institution.created",
        subject_type="institution",
        subject_id=str(institution.id),
    )
    return 201, institution
