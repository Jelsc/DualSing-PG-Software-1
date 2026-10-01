from .models import Institution, Membership


def is_platform_admin(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser and user.is_staff)


def require_platform_staff(user):
    return is_platform_admin(user)


def active_memberships(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Membership.objects.none()
    return Membership.objects.filter(user=user, is_active=True, institution__is_active=True).select_related("institution")


def active_membership(user, institution_id=None):
    memberships = active_memberships(user)
    if institution_id is not None:
        memberships = memberships.filter(institution_id=institution_id)
    return memberships.first()


def require_active_membership(user, institution_id=None):
    return active_membership(user, institution_id) is not None


def can_view_institution(user, institution_id):
    if is_platform_admin(user):
        return Institution.objects.filter(pk=institution_id, is_active=True).first()
    membership = active_memberships(user).filter(institution_id=institution_id).first()
    return membership.institution if membership else None


def can_create_institution(user):
    return is_platform_admin(user)


def can_manage_vocabulary(user, institution_id):
    if is_platform_admin(user):
        return Institution.objects.filter(pk=institution_id, is_active=True).exists()
    return active_memberships(user).filter(
        institution_id=institution_id,
        role__in=(Membership.Role.INSTITUTION_ADMIN, Membership.Role.VOCABULARY_REVIEWER),
    ).exists()


def can_review_vocabulary(user, institution_id):
    return can_manage_vocabulary(user, institution_id)


def can_manage_pilots(user, institution_id):
    if is_platform_admin(user):
        return Institution.objects.filter(pk=institution_id, is_active=True).exists()
    return active_memberships(user).filter(
        institution_id=institution_id,
        role=Membership.Role.INSTITUTION_ADMIN,
    ).exists()
